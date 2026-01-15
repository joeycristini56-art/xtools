"""
Advanced Slider CAPTCHA Solver with Computer Vision
Production-grade implementation using modern image processing techniques.
"""

import base64
import cv2
import numpy as np
import re
from typing import Any, Dict, Optional, Tuple, List
from core.base_solver import BaseSolver
from models.base import CaptchaType
from models.responses import SliderSolution
from utils.advanced_image_utils import advanced_image_processor
from utils.ml_model_manager import model_manager
from utils.logger import get_logger
from utils.cache_utils import cache_manager

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    
logger = get_logger(__name__)


class AdvancedSliderSolver(BaseSolver):
    """
    Advanced slider CAPTCHA solver using modern computer vision techniques.
    
    Features:
    - Advanced template matching with multiple scales and methods
    - Intelligent puzzle piece extraction using contour analysis
    - Gap detection using edge detection and morphological operations
    - OCR-based instruction parsing for simple sliders
    - Production-grade error handling and fallbacks
    """
    
    def __init__(self):
        super().__init__("AdvancedSliderSolver", CaptchaType.SLIDER_CAPTCHA)
        self.confidence_threshold = 0.7
        self.template_match_methods = [
            cv2.TM_CCOEFF_NORMED,
            cv2.TM_CCORR_NORMED,
            cv2.TM_SQDIFF_NORMED
        ]
        
        self.simple_slider_patterns = [
            r"move.*slider.*right",
            r"slide.*right",
            r"drag.*right",
            r"pull.*right",
            r"swipe.*right",
            r"slider.*all.*way.*right",
            r"complete.*slider",
            r"verify.*human",
            r"slide.*to.*complete",
            r"drag.*to.*verify"
        ]
    
    async def _initialize(self) -> None:
        """Initialize advanced image processor."""
        try:
            await advanced_image_processor.initialize()
            logger.info("Advanced slider solver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize advanced slider solver: {e}")
            raise
    
    async def solve(self, captcha_data: Dict[str, Any]) -> Optional[SliderSolution]:
        """
        Solve slider CAPTCHA using advanced computer vision techniques.
        
        Args:
            captcha_data: Dictionary containing:
                - image_data: Base64 encoded CAPTCHA image
                - puzzle_piece_data: Optional base64 encoded puzzle piece image
                - slider_width: Optional width of the slider track
                - slider_height: Optional height of the slider track
        
        Returns:
            SliderSolution with slider position or None if failed
        """
        try:
            if not self.validate_input(captcha_data):
                return None
            
            cache_key = f"advanced_slider_{captcha_data.get('image_data', '')[:100]}"
            cached_result = await cache_manager.get_cached_model_result(
                "advanced_slider", cache_key
            )
            if cached_result:
                logger.debug("Using cached advanced slider result")
                return SliderSolution(**cached_result)
            
            captcha_image = advanced_image_processor.decode_base64_image(captcha_data['image_data'])
            if captcha_image is None:
                logger.error("Failed to decode CAPTCHA image")
                return None
            
            enhanced_image = advanced_image_processor.enhance_image_quality(captcha_image, 1.2)
            
            is_simple_slider = await self._detect_simple_slider_advanced(enhanced_image)
            
            if is_simple_slider:
                logger.info("Detected simple slider CAPTCHA - moving to 100% position")
                solution = SliderSolution(
                    slider_position=100.0,
                    puzzle_offset_x=0,
                    puzzle_offset_y=0,
                    drag_distance=float(enhanced_image.shape[1]),
                    confidence=0.95
                )
                
                await cache_manager.cache_model_result(
                    "advanced_slider", cache_key, solution.dict()
                )
                
                return solution
            
            puzzle_piece = None
            
            if captcha_data.get('puzzle_piece_data'):
                puzzle_piece = advanced_image_processor.decode_base64_image(
                    captcha_data['puzzle_piece_data']
                )
                if puzzle_piece is not None:
                    puzzle_piece = advanced_image_processor.enhance_image_quality(puzzle_piece, 1.3)
            
            if puzzle_piece is None:
                puzzle_piece = await self._extract_puzzle_piece_advanced(enhanced_image)
            
            if puzzle_piece is None:
                logger.error("Could not extract or decode puzzle piece")
                return None
            
            match_result = await self._find_puzzle_position_advanced(enhanced_image, puzzle_piece)
            
            if match_result is None:
                logger.error("Could not find matching position for puzzle piece")
                return None
            
            position_percentage, offset_x, offset_y, drag_distance, confidence = match_result
            
            solution = SliderSolution(
                slider_position=position_percentage,
                puzzle_offset_x=offset_x,
                puzzle_offset_y=offset_y,
                drag_distance=drag_distance,
                confidence=confidence
            )
            
            await cache_manager.cache_model_result(
                "advanced_slider", cache_key, solution.dict()
            )
            
            logger.info(f"Advanced slider CAPTCHA solved: {position_percentage:.1f}% position (confidence: {confidence:.2f})")
            return solution
            
        except Exception as e:
            logger.error(f"Error solving advanced slider CAPTCHA: {e}")
            return None
    
    async def _detect_simple_slider_advanced(self, captcha_image: np.ndarray) -> bool:
        """Advanced detection of simple slider CAPTCHAs."""
        try:
            if TESSERACT_AVAILABLE:
                text_detected = await self._extract_text_with_preprocessing(captcha_image)
                if self._matches_simple_slider_patterns(text_detected):
                    logger.debug(f"Simple slider detected via OCR: '{text_detected}'")
                    return True
            
            has_slider_track = await self._detect_slider_track(captcha_image)
            has_puzzle_elements = await self._detect_puzzle_elements(captcha_image)
            
            if has_slider_track and not has_puzzle_elements:
                logger.debug("Simple slider detected via visual analysis")
                return True
            
            height, width = captcha_image.shape[:2]
            aspect_ratio = width / height
            
            if aspect_ratio > 3.0 and height < 100:
                logger.debug("Simple slider detected via aspect ratio analysis")
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Simple slider detection failed: {e}")
            return False
    
    async def _extract_text_with_preprocessing(self, image: np.ndarray) -> str:
        """Extract text using OCR with advanced preprocessing."""
        try:
            preprocessed = advanced_image_processor.preprocess_for_ocr(image)
            
            text = pytesseract.image_to_string(preprocessed, config='--psm 8')
            return text.strip().lower()
            
        except Exception as e:
            logger.debug(f"OCR text extraction failed: {e}")
            return ""
    
    def _matches_simple_slider_patterns(self, text: str) -> bool:
        """Check if text matches simple slider patterns."""
        if not text:
            return False
            
        for pattern in self.simple_slider_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    async def _detect_slider_track(self, image: np.ndarray) -> bool:
        """Detect if image contains a slider track."""
        try:
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            edges = cv2.Canny(gray, 50, 150)
            
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1))
            horizontal_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, horizontal_kernel)
            
            horizontal_pixels = np.sum(horizontal_lines > 0)
            total_pixels = horizontal_lines.shape[0] * horizontal_lines.shape[1]
            
            return (horizontal_pixels / total_pixels) > 0.01
            
        except Exception as e:
            logger.debug(f"Slider track detection failed: {e}")
            return False
    
    async def _detect_puzzle_elements(self, image: np.ndarray) -> bool:
        """Detect if image contains puzzle piece elements."""
        try:
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            edges = cv2.Canny(gray, 50, 150)
            
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            complex_contours = 0
            for contour in contours:
                area = cv2.contourArea(contour)
                perimeter = cv2.arcLength(contour, True)
                
                if area > 500 and perimeter > 100:
                    complexity = perimeter / (2 * np.sqrt(np.pi * area)) if area > 0 else 0
                    
                    if complexity > 1.5:
                        complex_contours += 1
            
            return complex_contours > 0
            
        except Exception as e:
            logger.debug(f"Puzzle element detection failed: {e}")
            return False
    
    async def _extract_puzzle_piece_advanced(self, captcha_image: np.ndarray) -> Optional[np.ndarray]:
        """Advanced puzzle piece extraction using multiple techniques."""
        try:
            piece = await self._extract_piece_by_contours(captcha_image)
            if piece is not None:
                return piece
            
            piece = await self._extract_piece_by_edges(captcha_image)
            if piece is not None:
                return piece
            
            piece = await self._extract_piece_by_color(captcha_image)
            if piece is not None:
                return piece
            
            logger.warning("All puzzle piece extraction methods failed")
            return None
            
        except Exception as e:
            logger.error(f"Advanced puzzle piece extraction failed: {e}")
            return None
    
    async def _extract_piece_by_contours(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Extract puzzle piece using contour analysis."""
        try:
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            edges1 = cv2.Canny(gray, 50, 150)
            edges2 = cv2.Canny(gray, 100, 200)
            edges = cv2.bitwise_or(edges1, edges2)
            
            kernel = np.ones((3, 3), np.uint8)
            edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
            
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            best_contour = None
            best_score = 0
            
            for contour in contours:
                area = cv2.contourArea(contour)
                perimeter = cv2.arcLength(contour, True)
                
                if area < 1000 or perimeter < 150:
                    continue
                
                hull = cv2.convexHull(contour)
                hull_area = cv2.contourArea(hull)
                
                if hull_area > 0:
                    solidity = area / hull_area
                    complexity = perimeter / (2 * np.sqrt(np.pi * area)) if area > 0 else 0
                    
                    score = complexity * (1 - solidity) * np.sqrt(area)
                    
                    if score > best_score:
                        best_score = score
                        best_contour = contour
            
            if best_contour is not None:
                x, y, w, h = cv2.boundingRect(best_contour)
                padding = 10
                
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = min(image.shape[1] - x, w + 2 * padding)
                h = min(image.shape[0] - y, h + 2 * padding)
                
                piece = image[y:y+h, x:x+w]
                return piece
            
            return None
            
        except Exception as e:
            logger.debug(f"Contour-based extraction failed: {e}")
            return None
    
    async def _extract_piece_by_edges(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Extract puzzle piece using edge density analysis."""
        try:
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            edges = cv2.Canny(gray, 50, 150)
            
            height, width = edges.shape
            region_size = 50
            max_density = 0
            best_region = None
            
            for y in range(0, height - region_size, region_size // 2):
                for x in range(0, width - region_size, region_size // 2):
                    region = edges[y:y+region_size, x:x+region_size]
                    density = np.sum(region > 0) / (region_size * region_size)
                    
                    if density > max_density:
                        max_density = density
                        best_region = (x, y, region_size, region_size)
            
            if best_region and max_density > 0.1:
                x, y, w, h = best_region
                
                padding = 20
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = min(image.shape[1] - x, w + 2 * padding)
                h = min(image.shape[0] - y, h + 2 * padding)
                
                piece = image[y:y+h, x:x+w]
                return piece
            
            return None
            
        except Exception as e:
            logger.debug(f"Edge-based extraction failed: {e}")
            return None
    
    async def _extract_piece_by_color(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Extract puzzle piece using color segmentation."""
        try:
            segmented = advanced_image_processor.segment_image_kmeans(image, k=4)
            
            
            if len(segmented.shape) == 3:
                gray_seg = cv2.cvtColor(segmented, cv2.COLOR_BGR2GRAY)
            else:
                gray_seg = segmented.copy()
            
            unique_values = np.unique(gray_seg)
            
            best_segment = None
            best_score = 0
            
            for value in unique_values:
                mask = (gray_seg == value).astype(np.uint8) * 255
                
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area > 1000:
                        perimeter = cv2.arcLength(contour, True)
                        complexity = perimeter / (2 * np.sqrt(np.pi * area)) if area > 0 else 0
                        score = area * complexity
                        
                        if score > best_score:
                            best_score = score
                            best_segment = contour
            
            if best_segment is not None:
                x, y, w, h = cv2.boundingRect(best_segment)
                padding = 15
                
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = min(image.shape[1] - x, w + 2 * padding)
                h = min(image.shape[0] - y, h + 2 * padding)
                
                piece = image[y:y+h, x:x+w]
                return piece
            
            return None
            
        except Exception as e:
            logger.debug(f"Color-based extraction failed: {e}")
            return None
    
    async def _find_puzzle_position_advanced(
        self, 
        captcha_image: np.ndarray, 
        puzzle_piece: np.ndarray
    ) -> Optional[Tuple[float, int, int, float, float]]:
        """Find puzzle position using advanced template matching."""
        try:
            matches = advanced_image_processor.template_match_advanced(
                captcha_image, puzzle_piece, method="multi"
            )
            
            if matches:
                best_match = matches[0]
                
                if best_match['confidence'] >= self.confidence_threshold:
                    match_x, match_y = best_match['location']
                    template_h, template_w = best_match['template_size']
                    
                    center_x = match_x + template_w // 2
                    center_y = match_y + template_h // 2
                    
                    slider_width = captcha_image.shape[1]
                    position_percentage = (center_x / slider_width) * 100
                    
                    drag_distance = float(center_x)
                    
                    return (
                        position_percentage,
                        match_x,
                        match_y,
                        drag_distance,
                        best_match['confidence']
                    )
            
            gap_result = await self._find_gap_position(captcha_image, puzzle_piece)
            if gap_result:
                return gap_result
            
            logger.warning("All position finding methods failed")
            return None
            
        except Exception as e:
            logger.error(f"Advanced position finding failed: {e}")
            return None
    
    async def _find_gap_position(
        self, 
        captcha_image: np.ndarray, 
        puzzle_piece: np.ndarray
    ) -> Optional[Tuple[float, int, int, float, float]]:
        """Find gap position using edge analysis."""
        try:
            gap_bbox = advanced_image_processor.detect_puzzle_piece_gap(captcha_image)
            
            if gap_bbox:
                x1, y1, x2, y2 = gap_bbox
                
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                
                slider_width = captcha_image.shape[1]
                position_percentage = (center_x / slider_width) * 100
                
                drag_distance = float(center_x)
                
                gap_area = (x2 - x1) * (y2 - y1)
                piece_area = puzzle_piece.shape[0] * puzzle_piece.shape[1]
                
                size_ratio = min(gap_area, piece_area) / max(gap_area, piece_area)
                confidence = 0.6 + (size_ratio * 0.3)
                
                return (position_percentage, x1, y1, drag_distance, confidence)
            
            return None
            
        except Exception as e:
            logger.debug(f"Gap position finding failed: {e}")
            return None
    
    def validate_input(self, captcha_data: Dict[str, Any]) -> bool:
        """Validate input data for advanced slider CAPTCHA solving."""
        if not captcha_data.get('image_data'):
            logger.error("No image data provided")
            return False
        
        try:
            base64.b64decode(captcha_data['image_data'])
        except Exception:
            logger.error("Invalid base64 image data")
            return False
        
        return True
    
    async def _cleanup(self) -> None:
        """Clean up resources."""
        logger.debug("Advanced slider solver resources cleaned up")