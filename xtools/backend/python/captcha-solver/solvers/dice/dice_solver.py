import cv2
import numpy as np
from typing import Any, Dict, Optional, List, Tuple
from core.base_solver import BaseSolver
from models.base import CaptchaType
from models.responses import DiceSolution
from utils.advanced_image_utils import AdvancedImageProcessor
from utils.logger import get_logger
from utils.cache_utils import cache_manager

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = get_logger(__name__)


class AdvancedDiceSolver(BaseSolver):
    """Advanced dice selection CAPTCHA solver using YOLO and computer vision."""
    
    def __init__(self):
        super().__init__("AdvancedDiceSolver", CaptchaType.DICE_SELECTION)
        self.image_processor = AdvancedImageProcessor()
        self.yolo_model = None
        self.confidence_threshold = 0.6
        
    async def _initialize(self) -> None:
        """Initialize advanced dice solver with YOLO if available."""
        try:
            if YOLO_AVAILABLE and TORCH_AVAILABLE:
                self.yolo_model = YOLO('yolov8n.pt')
                logger.info("YOLO model loaded for advanced dice detection")
            else:
                logger.warning("YOLO not available, falling back to traditional CV methods")
        except Exception as e:
            logger.warning(f"Failed to load YOLO model: {e}, using traditional methods")
        
        logger.info("Advanced dice solver initialized successfully")
    
    async def solve(self, captcha_data: Dict[str, Any]) -> Optional[DiceSolution]:
        """
        Solve dice selection CAPTCHA.
        
        Args:
            captcha_data: Dictionary containing:
                - image_data: Base64 encoded image
                - target_sum: Optional target sum for dice
        
        Returns:
            DiceSolution with selected dice indices or None if failed
        """
        try:
            if not self.validate_input(captcha_data):
                return None
            
            cached_result = await cache_manager.get_cached_model_result(
                "dice", captcha_data.get('image_data', '')
            )
            if cached_result:
                logger.debug("Using cached dice result")
                return DiceSolution(**cached_result)
            
            image = self.image_processor.decode_base64_image(captcha_data['image_data'])
            
            dice_values = await self._detect_dice_advanced(image)
            
            if not dice_values:
                dice_regions = self.image_processor.extract_dice_regions(image)
                
                if not dice_regions:
                    logger.warning("No dice found in image")
                    return None
                
                dice_values = []
                for i, (dice_image, bbox) in enumerate(dice_regions):
                    dots = await self._count_dice_dots_advanced(dice_image)
                    dice_values.append((i, dots, bbox))
                    logger.debug(f"Dice {i}: {dots} dots")
            
            target_sum = captcha_data.get('target_sum')
            selected_dice = self._select_dice(dice_values, target_sum)
            
            total_sum = sum(dice_values[i][1] for i in selected_dice)
            
            solution = DiceSolution(
                selected_dice=selected_dice,
                total_sum=total_sum,
                confidence=0.75
            )
            
            await cache_manager.cache_model_result(
                "dice",
                captcha_data.get('image_data', ''),
                solution.dict()
            )
            
            logger.info(f"Dice CAPTCHA solved: selected {len(selected_dice)} dice with sum {total_sum}")
            return solution
            
        except Exception as e:
            logger.error(f"Error solving dice CAPTCHA: {e}")
            return None
    
    def _select_dice(self, dice_values: List[Tuple[int, int, Tuple]], target_sum: Optional[int] = None) -> List[int]:
        """Select dice based on target sum or default strategy."""
        if not dice_values:
            return []
        
        if target_sum is not None:
            return self._find_dice_combination(dice_values, target_sum)
        else:
            sorted_dice = sorted(dice_values, key=lambda x: x[1], reverse=True)
            num_to_select = min(3, len(sorted_dice))
            return [dice[0] for dice in sorted_dice[:num_to_select]]
    
    def _find_dice_combination(self, dice_values: List[Tuple[int, int, Tuple]], target_sum: int) -> List[int]:
        """Find combination of dice that sum to target."""
        from itertools import combinations
        
        for r in range(1, len(dice_values) + 1):
            for combo in combinations(dice_values, r):
                if sum(dice[1] for dice in combo) == target_sum:
                    return [dice[0] for dice in combo]
        
        best_combo = []
        best_diff = float('inf')
        
        for r in range(1, len(dice_values) + 1):
            for combo in combinations(dice_values, r):
                combo_sum = sum(dice[1] for dice in combo)
                diff = abs(combo_sum - target_sum)
                if diff < best_diff:
                    best_diff = diff
                    best_combo = [dice[0] for dice in combo]
        
        return best_combo
    
    async def _detect_dice_advanced(self, image: np.ndarray) -> List[Tuple[int, int, Tuple]]:
        """Advanced dice detection using YOLO if available."""
        if not self.yolo_model:
            return []
        
        try:
            results = self.yolo_model(image, conf=self.confidence_threshold)
            
            dice_values = []
            for i, result in enumerate(results[0].boxes):
                x1, y1, x2, y2 = result.xyxy[0].cpu().numpy()
                bbox = (int(x1), int(y1), int(x2), int(y2))
                
                dice_region = image[int(y1):int(y2), int(x1):int(x2)]
                
                dots = await self._count_dice_dots_advanced(dice_region)
                dice_values.append((i, dots, bbox))
                logger.debug(f"YOLO detected dice {i}: {dots} dots")
            
            return dice_values
            
        except Exception as e:
            logger.debug(f"YOLO detection failed: {e}")
            return []
    
    async def _count_dice_dots_advanced(self, dice_image: np.ndarray) -> int:
        """Advanced dot counting using multiple techniques."""
        try:
            traditional_count = self.image_processor.count_dice_dots(dice_image)
            
            contour_count = await self._count_dots_contours(dice_image)
            
            template_count = await self._count_dots_templates(dice_image)
            
            counts = [traditional_count, contour_count, template_count]
            counts = [c for c in counts if c > 0]
            
            if not counts:
                return 1
            
            from collections import Counter
            count_freq = Counter(counts)
            most_common = count_freq.most_common(1)[0][0]
            
            return most_common
            
        except Exception as e:
            logger.debug(f"Advanced dot counting failed: {e}")
            return self.image_processor.count_dice_dots(dice_image)
    
    async def _count_dots_contours(self, dice_image: np.ndarray) -> int:
        """Count dots using contour detection with advanced filtering."""
        try:
            if len(dice_image.shape) == 3:
                gray = cv2.cvtColor(dice_image, cv2.COLOR_RGB2GRAY)
            else:
                gray = dice_image.copy()
            
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            thresh = cv2.adaptiveThreshold(
                blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY_INV, 11, 2
            )
            
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            dots = []
            h, w = gray.shape
            min_area = (h * w) * 0.005
            max_area = (h * w) * 0.15
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if min_area < area < max_area:
                    perimeter = cv2.arcLength(contour, True)
                    if perimeter > 0:
                        circularity = 4 * np.pi * area / (perimeter * perimeter)
                        if circularity > 0.3:
                            dots.append(contour)
            
            return len(dots)
            
        except Exception as e:
            logger.debug(f"Contour dot counting failed: {e}")
            return 0
    
    async def _count_dots_templates(self, dice_image: np.ndarray) -> int:
        """Count dots using template matching for standard dice patterns."""
        try:
            
            if len(dice_image.shape) == 3:
                gray = cv2.cvtColor(dice_image, cv2.COLOR_RGB2GRAY)
            else:
                gray = dice_image.copy()
            
            h, w = gray.shape
            
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            dark_pixels = np.sum(binary == 255)
            total_pixels = h * w
            dark_ratio = dark_pixels / total_pixels
            
            if dark_ratio < 0.05:
                return 1
            elif dark_ratio < 0.12:
                return 2
            elif dark_ratio < 0.18:
                return 3
            elif dark_ratio < 0.25:
                return 4
            elif dark_ratio < 0.32:
                return 5
            else:
                return 6
                
        except Exception as e:
            logger.debug(f"Template dot counting failed: {e}")
            return 0
    
    def validate_input(self, captcha_data: Dict[str, Any]) -> bool:
        """Validate input data for dice CAPTCHA solving."""
        if not captcha_data.get('image_data'):
            logger.error("No image data provided")
            return False
        return True
    
    async def _cleanup(self) -> None:
        """Clean up dice solver resources."""
        logger.debug("Dice solver resources cleaned up")