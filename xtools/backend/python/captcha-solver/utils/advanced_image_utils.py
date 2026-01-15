"""
Advanced Image Processing Utilities for CAPTCHA Solving
Includes YOLO integration, advanced preprocessing, and computer vision techniques.
"""

import cv2
import numpy as np
import base64
import io
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from typing import List, Dict, Any, Optional, Tuple, Union
from sklearn.cluster import KMeans
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
from .logger import get_logger
try:
    from .ml_model_manager import model_manager
except ImportError:
    model_manager = None

logger = get_logger(__name__)


class AdvancedImageProcessor:
    """Advanced image processing with modern computer vision techniques."""
    
    def __init__(self):
        self.yolo_model = None
        self.classification_model = None
        
    async def initialize(self):
        """Initialize ML models for image processing."""
        try:
            self.yolo_model = await model_manager.get_object_detector("yolov8n")
            
            self.classification_model = await model_manager.get_image_classifier("resnet50")
            
            logger.info("Advanced image processor initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize image processor: {e}")
            
    def decode_base64_image(self, base64_data: str) -> Optional[np.ndarray]:
        """Decode base64 image with enhanced error handling."""
        try:
            if base64_data.startswith('data:image'):
                base64_data = base64_data.split(',')[1]
            
            image_bytes = base64.b64decode(base64_data)
            
            pil_image = Image.open(io.BytesIO(image_bytes))
            
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            rgb_array = np.array(pil_image)
            bgr_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)
            
            return bgr_array
            
        except Exception as e:
            logger.error(f"Failed to decode base64 image: {e}")
            return None
            
    def enhance_image_quality(self, image: np.ndarray, enhancement_level: float = 1.2) -> np.ndarray:
        """Enhance image quality using multiple techniques."""
        try:
            if len(image.shape) == 3:
                pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            else:
                pil_image = Image.fromarray(image)
                
            enhancer = ImageEnhance.Sharpness(pil_image)
            pil_image = enhancer.enhance(enhancement_level)
            
            enhancer = ImageEnhance.Contrast(pil_image)
            pil_image = enhancer.enhance(enhancement_level)
            
            enhancer = ImageEnhance.Brightness(pil_image)
            pil_image = enhancer.enhance(1.1)
            
            if len(image.shape) == 3:
                return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            else:
                return np.array(pil_image)
                
        except Exception as e:
            logger.error(f"Image enhancement failed: {e}")
            return image
            
    def denoise_image(self, image: np.ndarray, method: str = "bilateral") -> np.ndarray:
        """Advanced image denoising."""
        try:
            if method == "bilateral":
                return cv2.bilateralFilter(image, 9, 75, 75)
            elif method == "gaussian":
                return cv2.GaussianBlur(image, (5, 5), 0)
            elif method == "median":
                return cv2.medianBlur(image, 5)
            elif method == "nlm":
                if len(image.shape) == 3:
                    return cv2.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 21)
                else:
                    return cv2.fastNlMeansDenoising(image, None, 10, 7, 21)
            else:
                return image
                
        except Exception as e:
            logger.error(f"Denoising failed: {e}")
            return image
            
    def preprocess_for_ocr(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for better OCR results."""
        try:
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
                
            denoised = self.denoise_image(gray, "nlm")
            
            thresh = cv2.adaptiveThreshold(
                denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
            
            kernel = np.ones((2, 2), np.uint8)
            cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)
            
            return cleaned
            
        except Exception as e:
            logger.error(f"OCR preprocessing failed: {e}")
            return image
            
    async def detect_objects_yolo(self, image: np.ndarray, conf_threshold: float = 0.5, target_classes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Detect objects using YOLO with filtering options."""
        try:
            if self.yolo_model is None:
                await self.initialize()
                
            detections = await model_manager.detect_objects(image, "yolov8n", conf_threshold)
            
            if target_classes:
                filtered_detections = []
                for detection in detections:
                    if any(target_class.lower() in detection["class_name"].lower() for target_class in target_classes):
                        filtered_detections.append(detection)
                detections = filtered_detections
                
            return detections
            
        except Exception as e:
            logger.error(f"YOLO object detection failed: {e}")
            return []
            
    async def classify_image_regions(self, image: np.ndarray, regions: List[Tuple[int, int, int, int]]) -> List[Dict[str, Any]]:
        """Classify specific regions of an image."""
        try:
            if self.classification_model is None:
                await self.initialize()
                
            results = []
            for i, (x1, y1, x2, y2) in enumerate(regions):
                region = image[y1:y2, x1:x2]
                
                classifications = await model_manager.classify_image(region, "resnet50", top_k=3)
                
                results.append({
                    "region_id": i,
                    "bbox": [x1, y1, x2, y2],
                    "classifications": classifications
                })
                
            return results
            
        except Exception as e:
            logger.error(f"Region classification failed: {e}")
            return []
            
    def split_grid_image(self, image: np.ndarray, grid_size: str) -> List[np.ndarray]:
        """Split image into grid cells with improved accuracy."""
        try:
            rows, cols = map(int, grid_size.split('x'))
            height, width = image.shape[:2]
            
            cell_height = height // rows
            cell_width = width // cols
            
            cells = []
            for row in range(rows):
                for col in range(cols):
                    y1 = row * cell_height
                    y2 = (row + 1) * cell_height if row < rows - 1 else height
                    x1 = col * cell_width
                    x2 = (col + 1) * cell_width if col < cols - 1 else width
                    
                    cell = image[y1:y2, x1:x2]
                    
                    cell = self.enhance_image_quality(cell)
                    
                    cells.append(cell)
                    
            return cells
            
        except Exception as e:
            logger.error(f"Grid splitting failed: {e}")
            return []
            
    def detect_puzzle_piece_gap(self, image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """Detect the gap where a puzzle piece should fit."""
        try:
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
                
            edges = cv2.Canny(gray, 50, 150)
            
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            best_contour = None
            max_area = 0
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > max_area and area > 1000:
                    x, y, w, h = cv2.boundingRect(contour)
                    aspect_ratio = w / h if h > 0 else 0
                    
                    if 0.5 <= aspect_ratio <= 2.0:
                        max_area = area
                        best_contour = contour
                        
            if best_contour is not None:
                x, y, w, h = cv2.boundingRect(best_contour)
                return (x, y, x + w, y + h)
                
            return None
            
        except Exception as e:
            logger.error(f"Puzzle gap detection failed: {e}")
            return None
            
    def extract_puzzle_piece(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Extract puzzle piece from image using advanced techniques."""
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
                
                if area < 500 or perimeter < 100:
                    continue
                    
                hull = cv2.convexHull(contour)
                hull_area = cv2.contourArea(hull)
                
                if hull_area > 0:
                    solidity = area / hull_area
                    complexity = perimeter / (2 * np.sqrt(np.pi * area)) if area > 0 else 0
                    
                    score = complexity * (1 - solidity) * area
                    
                    if score > best_score:
                        best_score = score
                        best_contour = contour
                        
            if best_contour is not None:
                x, y, w, h = cv2.boundingRect(best_contour)
                
                padding = 5
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = min(image.shape[1] - x, w + 2 * padding)
                h = min(image.shape[0] - y, h + 2 * padding)
                
                piece = image[y:y+h, x:x+w]
                return piece
                
            return None
            
        except Exception as e:
            logger.error(f"Puzzle piece extraction failed: {e}")
            return None
            
    def template_match_advanced(self, image: np.ndarray, template: np.ndarray, method: str = "multi") -> List[Dict[str, Any]]:
        """Advanced template matching with multiple methods and scales."""
        try:
            if len(image.shape) == 3:
                image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                image_gray = image.copy()
                
            if len(template.shape) == 3:
                template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            else:
                template_gray = template.copy()
                
            matches = []
            
            if method == "multi":
                methods = [cv2.TM_CCOEFF_NORMED, cv2.TM_CCORR_NORMED, cv2.TM_SQDIFF_NORMED]
            else:
                methods = [getattr(cv2, f"TM_{method.upper()}")]
                
            scales = [0.8, 0.9, 1.0, 1.1, 1.2]
            
            for scale in scales:
                if scale != 1.0:
                    new_width = int(template_gray.shape[1] * scale)
                    new_height = int(template_gray.shape[0] * scale)
                    scaled_template = cv2.resize(template_gray, (new_width, new_height))
                else:
                    scaled_template = template_gray
                    
                if scaled_template.shape[0] > image_gray.shape[0] or scaled_template.shape[1] > image_gray.shape[1]:
                    continue
                    
                for cv_method in methods:
                    try:
                        result = cv2.matchTemplate(image_gray, scaled_template, cv_method)
                        
                        if cv_method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
                            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                            match_loc = min_loc
                            confidence = 1.0 - min_val
                        else:
                            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                            match_loc = max_loc
                            confidence = max_val
                            
                        matches.append({
                            "location": match_loc,
                            "confidence": confidence,
                            "scale": scale,
                            "method": cv_method,
                            "template_size": scaled_template.shape
                        })
                        
                    except Exception as e:
                        logger.debug(f"Template matching failed for method {cv_method}: {e}")
                        continue
                        
            matches.sort(key=lambda x: x["confidence"], reverse=True)
            
            return matches
            
        except Exception as e:
            logger.error(f"Advanced template matching failed: {e}")
            return []
            
    def segment_image_kmeans(self, image: np.ndarray, k: int = 3) -> np.ndarray:
        """Segment image using K-means clustering."""
        try:
            data = image.reshape((-1, 3)) if len(image.shape) == 3 else image.reshape((-1, 1))
            data = np.float32(data)
            
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
            _, labels, centers = cv2.kmeans(data, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
            
            centers = np.uint8(centers)
            segmented_data = centers[labels.flatten()]
            segmented_image = segmented_data.reshape(image.shape)
            
            return segmented_image
            
        except Exception as e:
            logger.error(f"K-means segmentation failed: {e}")
            return image
            
    def detect_text_regions(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect text regions in image using EAST or similar method."""
        try:
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
                
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 1))
            dilated = cv2.dilate(gray, kernel, iterations=1)
            
            contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            text_regions = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                
                if w > 20 and h > 10 and w / h > 1.5:
                    text_regions.append((x, y, x + w, y + h))
                    
            return text_regions
            
        except Exception as e:
            logger.error(f"Text region detection failed: {e}")
            return []
            
    def calculate_image_similarity(self, img1: np.ndarray, img2: np.ndarray) -> float:
        """Calculate similarity between two images using multiple metrics."""
        try:
            height, width = min(img1.shape[0], img2.shape[0]), min(img1.shape[1], img2.shape[1])
            img1_resized = cv2.resize(img1, (width, height))
            img2_resized = cv2.resize(img2, (width, height))
            
            if len(img1_resized.shape) == 3:
                img1_gray = cv2.cvtColor(img1_resized, cv2.COLOR_BGR2GRAY)
            else:
                img1_gray = img1_resized
                
            if len(img2_resized.shape) == 3:
                img2_gray = cv2.cvtColor(img2_resized, cv2.COLOR_BGR2GRAY)
            else:
                img2_gray = img2_resized
                
            from skimage.metrics import structural_similarity as ssim
            similarity = ssim(img1_gray, img2_gray)
            
            return similarity
            
        except Exception as e:
            logger.error(f"Image similarity calculation failed: {e}")
            return 0.0
            
    def resize_image(self, image: np.ndarray, target_size: Tuple[int, int], maintain_aspect: bool = True) -> np.ndarray:
        """Resize image with optional aspect ratio maintenance."""
        try:
            if maintain_aspect:
                height, width = image.shape[:2]
                target_width, target_height = target_size
                
                scale = min(target_width / width, target_height / height)
                
                new_width = int(width * scale)
                new_height = int(height * scale)
                
                resized = cv2.resize(image, (new_width, new_height))
                
                canvas = np.zeros((target_height, target_width, image.shape[2] if len(image.shape) == 3 else 1), dtype=image.dtype)
                
                y_offset = (target_height - new_height) // 2
                x_offset = (target_width - new_width) // 2
                
                if len(image.shape) == 3:
                    canvas[y_offset:y_offset + new_height, x_offset:x_offset + new_width] = resized
                else:
                    canvas[y_offset:y_offset + new_height, x_offset:x_offset + new_width, 0] = resized
                    
                return canvas.squeeze() if len(image.shape) == 2 else canvas
            else:
                return cv2.resize(image, target_size)
                
        except Exception as e:
            logger.error(f"Image resizing failed: {e}")
            return image


advanced_image_processor = AdvancedImageProcessor()