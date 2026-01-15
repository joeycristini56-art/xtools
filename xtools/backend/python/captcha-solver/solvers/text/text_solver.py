import cv2
import numpy as np
from typing import Any, Dict, Optional, List
from core.base_solver import BaseSolver
from models.base import CaptchaType
from models.responses import TextSolution
from utils.advanced_image_utils import AdvancedImageProcessor
from utils.logger import get_logger
from utils.cache_utils import cache_manager

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel
    TROCR_AVAILABLE = True
except ImportError:
    TROCR_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = get_logger(__name__)


class AdvancedTextSolver(BaseSolver):
    """Advanced text CAPTCHA solver using multiple OCR engines and preprocessing."""
    
    def __init__(self):
        super().__init__("AdvancedTextSolver", CaptchaType.TEXT)
        self.ocr_reader = None
        self.trocr_processor = None
        self.trocr_model = None
        self.image_processor = AdvancedImageProcessor()
        self.confidence_threshold = 0.6
        self.available_engines = []
    
    async def _initialize(self) -> None:
        """Initialize multiple OCR engines and models."""
        try:
            if EASYOCR_AVAILABLE:
                self.ocr_reader = easyocr.Reader(['en'], gpu=False)
                self.available_engines.append('easyocr')
                logger.info("EasyOCR initialized successfully")
            
            if TROCR_AVAILABLE and TORCH_AVAILABLE:
                try:
                    self.trocr_processor = TrOCRProcessor.from_pretrained('microsoft/trocr-base-printed')
                    self.trocr_model = VisionEncoderDecoderModel.from_pretrained('microsoft/trocr-base-printed')
                    self.available_engines.append('trocr')
                    logger.info("TrOCR initialized successfully")
                except Exception as e:
                    logger.warning(f"Failed to initialize TrOCR: {e}")
            
            if TESSERACT_AVAILABLE:
                try:
                    pytesseract.get_tesseract_version()
                    self.available_engines.append('tesseract')
                    logger.info("Tesseract OCR available")
                except Exception as e:
                    logger.warning(f"Tesseract not properly installed: {e}")
            
            if not self.available_engines:
                logger.warning("No OCR engines available, text solving may be limited")
            else:
                logger.info(f"Available OCR engines: {', '.join(self.available_engines)}")
            
        except Exception as e:
            logger.error(f"Failed to initialize OCR engines: {e}")
    
    async def solve(self, captcha_data: Dict[str, Any]) -> Optional[TextSolution]:
        """
        Solve text-based CAPTCHA.
        
        Args:
            captcha_data: Dictionary containing:
                - image_data: Base64 encoded image
                - case_sensitive: Whether the solution is case sensitive
                - min_length: Minimum expected text length
                - max_length: Maximum expected text length
        
        Returns:
            TextSolution with extracted text or None if failed
        """
        try:
            if not self.validate_input(captcha_data):
                return None
            
            cached_result = await cache_manager.get_cached_model_result(
                "text_ocr", captcha_data.get('image_data', '')
            )
            if cached_result:
                logger.debug("Using cached OCR result")
                return TextSolution(**cached_result)
            
            image = self.image_processor.decode_base64_image(captcha_data['image_data'])
            processed_image = await self._preprocess_image(image)
            
            text_candidates = await self._extract_text_candidates_advanced(processed_image)
            
            best_text = await self._select_best_candidate(
                text_candidates, 
                captcha_data
            )
            
            if not best_text:
                logger.warning("No valid text extracted from CAPTCHA")
                return None
            
            solution = TextSolution(
                text=best_text['text'],
                confidence=best_text['confidence'],
                case_sensitive=captcha_data.get('case_sensitive', False)
            )
            
            await cache_manager.cache_model_result(
                "text_ocr", 
                captcha_data.get('image_data', ''),
                solution.dict()
            )
            
            logger.info(f"Text CAPTCHA solved: '{best_text['text']}' (confidence: {best_text['confidence']:.2f})")
            return solution
            
        except Exception as e:
            logger.error(f"Error solving text CAPTCHA: {e}")
            return None
    
    async def _preprocess_image(self, image: np.ndarray) -> List[np.ndarray]:
        """Preprocess image with multiple techniques."""
        processed_images = []
        
        try:
            processed_images.append(image)
            
            basic_processed = self.image_processor.preprocess_text_captcha(image)
            processed_images.append(basic_processed)
            
            enhanced = self.image_processor.enhance_image_quality(image)
            processed_images.append(enhanced)
            
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
                processed_images.append(gray)
            
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            else:
                gray = image.copy()
            
            _, otsu_thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            processed_images.append(otsu_thresh)
            
            adaptive_thresh = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
            processed_images.append(adaptive_thresh)
            
            kernel = np.ones((2, 2), np.uint8)
            morph_open = cv2.morphologyEx(basic_processed, cv2.MORPH_OPEN, kernel)
            morph_close = cv2.morphologyEx(basic_processed, cv2.MORPH_CLOSE, kernel)
            processed_images.extend([morph_open, morph_close])
            
            denoised = cv2.medianBlur(gray, 3)
            processed_images.append(denoised)
            
            edges = cv2.Canny(gray, 50, 150)
            processed_images.append(edges)
            
            return processed_images
            
        except Exception as e:
            logger.error(f"Error preprocessing image: {e}")
            return [image]
    
    async def _extract_text_candidates_advanced(self, processed_images: List[np.ndarray]) -> List[Dict[str, Any]]:
        """Extract text candidates using all available OCR engines."""
        candidates = []
        
        for i, image in enumerate(processed_images):
            try:
                if 'easyocr' in self.available_engines:
                    easyocr_results = await self._extract_with_easyocr(image)
                    for result in easyocr_results:
                        result['method'] = f'easyocr_variant_{i}'
                        candidates.append(result)
                
                if 'trocr' in self.available_engines:
                    trocr_results = await self._extract_with_trocr(image)
                    for result in trocr_results:
                        result['method'] = f'trocr_variant_{i}'
                        candidates.append(result)
                
                if 'tesseract' in self.available_engines:
                    tesseract_results = await self._extract_with_tesseract(image)
                    for result in tesseract_results:
                        result['method'] = f'tesseract_variant_{i}'
                        candidates.append(result)
                
                template_results = await self._extract_with_templates(image)
                for result in template_results:
                    result['method'] = f'template_variant_{i}'
                    candidates.append(result)
                
            except Exception as e:
                logger.debug(f"Error extracting from image variant {i}: {e}")
                continue
        
        return candidates
    
    async def _extract_text_candidates(self, processed_images: List[np.ndarray]) -> List[Dict[str, Any]]:
        """Extract text candidates from preprocessed images."""
        candidates = []
        
        for i, image in enumerate(processed_images):
            try:
                easyocr_results = await self._extract_with_easyocr(image)
                for result in easyocr_results:
                    result['method'] = f'easyocr_variant_{i}'
                    candidates.append(result)
                
                template_results = await self._extract_with_templates(image)
                for result in template_results:
                    result['method'] = f'template_variant_{i}'
                    candidates.append(result)
                
            except Exception as e:
                logger.debug(f"Error extracting from image variant {i}: {e}")
                continue
        
        return candidates
    
    async def _extract_with_easyocr(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Extract text using EasyOCR."""
        try:
            if len(image.shape) == 2:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            else:
                image_rgb = image
            
            results = self.ocr_reader.readtext(image_rgb, detail=1)
            
            candidates = []
            for (bbox, text, confidence) in results:
                if confidence > 0.1 and text.strip():
                    candidates.append({
                        'text': text.strip(),
                        'confidence': confidence,
                        'bbox': bbox,
                        'method': 'easyocr'
                    })
            
            return candidates
            
        except Exception as e:
            logger.debug(f"EasyOCR extraction failed: {e}")
            return []
    
    async def _extract_with_trocr(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Extract text using TrOCR (Transformer-based OCR)."""
        try:
            if not self.trocr_processor or not self.trocr_model:
                return []
            
            from PIL import Image
            
            if len(image.shape) == 2:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            else:
                image_rgb = image
            
            pil_image = Image.fromarray(image_rgb)
            
            pixel_values = self.trocr_processor(pil_image, return_tensors="pt").pixel_values
            generated_ids = self.trocr_model.generate(pixel_values)
            generated_text = self.trocr_processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            
            if generated_text.strip():
                return [{
                    'text': generated_text.strip(),
                    'confidence': 0.8,
                    'method': 'trocr'
                }]
            
            return []
            
        except Exception as e:
            logger.debug(f"TrOCR extraction failed: {e}")
            return []
    
    async def _extract_with_tesseract(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Extract text using Tesseract OCR."""
        try:
            if 'tesseract' not in self.available_engines:
                return []
            
            if len(image.shape) == 3:
                image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            else:
                image_bgr = image
            
            custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
            
            data = pytesseract.image_to_data(image_bgr, config=custom_config, output_type=pytesseract.Output.DICT)
            
            candidates = []
            for i, text in enumerate(data['text']):
                if text.strip() and int(data['conf'][i]) > 30:
                    candidates.append({
                        'text': text.strip(),
                        'confidence': int(data['conf'][i]) / 100.0,
                        'method': 'tesseract'
                    })
            
            simple_text = pytesseract.image_to_string(image_bgr, config=custom_config).strip()
            if simple_text and simple_text not in [c['text'] for c in candidates]:
                candidates.append({
                    'text': simple_text,
                    'confidence': 0.7,
                    'method': 'tesseract_simple'
                })
            
            return candidates
            
        except Exception as e:
            logger.debug(f"Tesseract extraction failed: {e}")
            return []
    
    async def _extract_with_templates(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Extract text using template matching for common patterns."""
        candidates = []
        
        try:
            
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            else:
                gray = image.copy()
            
            contours, _ = cv2.findContours(gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            char_contours = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                if 10 < w < 100 and 15 < h < 100:
                    char_contours.append((x, y, w, h))
            
            char_contours.sort(key=lambda x: x[0])
            
            characters = []
            for x, y, w, h in char_contours:
                char_image = gray[y:y+h, x:x+w]
                
                char_result = await self._recognize_character(char_image)
                if char_result:
                    characters.append(char_result)
            
            if characters:
                text = ''.join(characters)
                if text:
                    candidates.append({
                        'text': text,
                        'confidence': 0.5,
                        'method': 'template'
                    })
            
        except Exception as e:
            logger.debug(f"Template matching failed: {e}")
        
        return candidates
    
    async def _recognize_character(self, char_image: np.ndarray) -> Optional[str]:
        """Recognize a single character using simple heuristics."""
        try:
            
            height, width = char_image.shape
            
            white_pixels = np.sum(char_image == 255)
            black_pixels = np.sum(char_image == 0)
            
            if white_pixels == 0:
                return None
            
            ratio = black_pixels / (white_pixels + black_pixels)
            
            if ratio < 0.2:
                return '1'
            elif ratio > 0.7:
                return '8'
            elif width > height * 1.5:
                return '-'
            else:
                return 'A'
                
        except Exception as e:
            logger.debug(f"Character recognition failed: {e}")
            return None
    
    async def _select_best_candidate(
        self, 
        candidates: List[Dict[str, Any]], 
        captcha_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Select the best text candidate based on various criteria."""
        if not candidates:
            return None
        
        min_length = captcha_data.get('min_length', 1)
        max_length = captcha_data.get('max_length', 20)
        
        valid_candidates = [
            c for c in candidates 
            if min_length <= len(c['text']) <= max_length
        ]
        
        if not valid_candidates:
            valid_candidates = candidates
        
        scored_candidates = []
        for candidate in valid_candidates:
            score = await self._score_candidate(candidate, captcha_data)
            scored_candidates.append((score, candidate))
        
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        
        best_score, best_candidate = scored_candidates[0]
        if best_candidate['confidence'] >= self.confidence_threshold:
            return best_candidate
        
        return best_candidate if scored_candidates else None
    
    async def _score_candidate(self, candidate: Dict[str, Any], captcha_data: Dict[str, Any]) -> float:
        """Score a text candidate based on various factors."""
        score = candidate['confidence']
        
        if 'easyocr' in candidate.get('method', ''):
            score += 0.2
        
        text_length = len(candidate['text'])
        if text_length < 3:
            score -= 0.1
        elif text_length > 10:
            score -= 0.05
        
        alphanumeric_ratio = sum(c.isalnum() for c in candidate['text']) / len(candidate['text'])
        score += alphanumeric_ratio * 0.1
        
        special_char_ratio = sum(not c.isalnum() for c in candidate['text']) / len(candidate['text'])
        score -= special_char_ratio * 0.2
        
        return max(0.0, min(1.0, score))
    
    def validate_input(self, captcha_data: Dict[str, Any]) -> bool:
        """Validate input data for text CAPTCHA solving."""
        if not captcha_data.get('image_data'):
            logger.error("No image data provided")
            return False
        
        min_length = captcha_data.get('min_length')
        max_length = captcha_data.get('max_length')
        
        if min_length is not None and max_length is not None:
            if min_length > max_length:
                logger.error("min_length cannot be greater than max_length")
                return False
        
        return True
    
    async def _cleanup(self) -> None:
        """Clean up OCR resources."""
        self.ocr_reader = None
        logger.debug("Text solver resources cleaned up")