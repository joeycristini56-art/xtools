import cv2
import numpy as np
from typing import Any, Dict, Optional, List, Tuple
from core.base_solver import BaseSolver
from models.base import CaptchaType
from models.responses import RotationSolution
from utils.advanced_image_utils import AdvancedImageProcessor
from utils.logger import get_logger
from utils.cache_utils import cache_manager

try:
    from skimage import feature, transform
    SKIMAGE_AVAILABLE = True
except ImportError:
    SKIMAGE_AVAILABLE = False

logger = get_logger(__name__)


class AdvancedRotationSolver(BaseSolver):
    """Image rotation CAPTCHA solver using computer vision."""
    
    def __init__(self):
        super().__init__("AdvancedRotationSolver", CaptchaType.IMAGE_ROTATION)
        self.image_processor = AdvancedImageProcessor()
        self.angle_precision = 1
    
    async def _initialize(self) -> None:
        """Initialize advanced rotation solver."""
        if SKIMAGE_AVAILABLE:
            logger.info("Advanced rotation solver initialized with scikit-image support")
        else:
            logger.info("Advanced rotation solver initialized (basic mode)")
        logger.info("Rotation solver initialized successfully")
    
    async def solve(self, captcha_data: Dict[str, Any]) -> Optional[RotationSolution]:
        """
        Solve image rotation CAPTCHA.
        
        Args:
            captcha_data: Dictionary containing:
                - image_data: Base64 encoded image
                - instruction: Rotation instruction
        
        Returns:
            RotationSolution with rotation angle or None if failed
        """
        try:
            if not self.validate_input(captcha_data):
                return None
            
            cached_result = await cache_manager.get_cached_model_result(
                "rotation", captcha_data.get('image_data', '')
            )
            if cached_result:
                logger.debug("Using cached rotation result")
                return RotationSolution(**cached_result)
            
            image = self.image_processor.decode_base64_image(captcha_data['image_data'])
            
            rotation_angle = await self._detect_rotation_advanced(image)
            
            corrected_angle = -rotation_angle if rotation_angle != 0 else 0
            
            solution = RotationSolution(
                rotation_angle=int(corrected_angle),
                confidence=0.8
            )
            
            await cache_manager.cache_model_result(
                "rotation",
                captcha_data.get('image_data', ''),
                solution.dict()
            )
            
            logger.info(f"Rotation CAPTCHA solved: {corrected_angle} degrees")
            return solution
            
        except Exception as e:
            logger.error(f"Error solving rotation CAPTCHA: {e}")
            return None
    
    async def _detect_rotation_advanced(self, image: np.ndarray) -> float:
        """Advanced rotation detection using multiple techniques."""
        try:
            traditional_angle = self.image_processor.detect_rotation_angle(image)
            
            hough_angle = await self._detect_rotation_hough(image)
            
            pca_angle = await self._detect_rotation_pca(image)
            
            feature_angle = await self._detect_rotation_features(image)
            
            angles = []
            weights = []
            
            if traditional_angle is not None:
                angles.append(traditional_angle)
                weights.append(0.3)
            
            if hough_angle is not None:
                angles.append(hough_angle)
                weights.append(0.3)
            
            if pca_angle is not None:
                angles.append(pca_angle)
                weights.append(0.2)
            
            if feature_angle is not None:
                angles.append(feature_angle)
                weights.append(0.2)
            
            if not angles:
                return 0.0
            
            weighted_angle = sum(a * w for a, w in zip(angles, weights)) / sum(weights)
            
            return round(weighted_angle / self.angle_precision) * self.angle_precision
            
        except Exception as e:
            logger.debug(f"Advanced rotation detection failed: {e}")
            return self.image_processor.detect_rotation_angle(image) or 0.0
    
    async def _detect_rotation_hough(self, image: np.ndarray) -> Optional[float]:
        """Detect rotation using Hough line transform."""
        try:
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            else:
                gray = image.copy()
            
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            
            lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
            
            if lines is None:
                return None
            
            angles = []
            for line in lines:
                rho, theta = line[0]
                angle = np.degrees(theta) - 90
                
                while angle > 90:
                    angle -= 180
                while angle < -90:
                    angle += 180
                
                angles.append(angle)
            
            if not angles:
                return None
            
            return float(np.median(angles))
            
        except Exception as e:
            logger.debug(f"Hough rotation detection failed: {e}")
            return None
    
    async def _detect_rotation_pca(self, image: np.ndarray) -> Optional[float]:
        """Detect rotation using Principal Component Analysis."""
        try:
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            else:
                gray = image.copy()
            
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return None
            
            largest_contour = max(contours, key=cv2.contourArea)
            
            data_pts = np.array([[point[0][0], point[0][1]] for point in largest_contour])
            
            mean = np.mean(data_pts, axis=0)
            
            cov_matrix = np.cov(data_pts.T)
            
            eigenvalues, eigenvectors = np.linalg.eig(cov_matrix)
            
            principal_component = eigenvectors[:, np.argmax(eigenvalues)]
            
            angle = np.degrees(np.arctan2(principal_component[1], principal_component[0]))
            
            while angle > 90:
                angle -= 180
            while angle < -90:
                angle += 180
            
            return float(angle)
            
        except Exception as e:
            logger.debug(f"PCA rotation detection failed: {e}")
            return None
    
    async def _detect_rotation_features(self, image: np.ndarray) -> Optional[float]:
        """Detect rotation using feature-based methods (requires scikit-image)."""
        try:
            if not SKIMAGE_AVAILABLE:
                return None
            
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            else:
                gray = image.copy()
            
            gray = gray.astype(np.float64) / 255.0
            
            corners = feature.corner_harris(gray)
            corner_coords = feature.corner_peaks(corners, min_distance=10)
            
            if len(corner_coords) < 4:
                return None
            
            
            centroid = np.mean(corner_coords, axis=0)
            
            angles = []
            for corner in corner_coords:
                dx = corner[1] - centroid[1]
                dy = corner[0] - centroid[0]
                angle = np.degrees(np.arctan2(dy, dx))
                angles.append(angle)
            
            if not angles:
                return None
            
            angles = np.array(angles)
            
            angles = angles % 180
            
            hist, bins = np.histogram(angles, bins=18, range=(0, 180))
            dominant_bin = np.argmax(hist)
            dominant_angle = (bins[dominant_bin] + bins[dominant_bin + 1]) / 2
            
            rotation_angle = dominant_angle - 90
            
            while rotation_angle > 90:
                rotation_angle -= 180
            while rotation_angle < -90:
                rotation_angle += 180
            
            return float(rotation_angle)
            
        except Exception as e:
            logger.debug(f"Feature-based rotation detection failed: {e}")
            return None
    
    def validate_input(self, captcha_data: Dict[str, Any]) -> bool:
        """Validate input data for rotation CAPTCHA solving."""
        if not captcha_data.get('image_data'):
            logger.error("No image data provided")
            return False
        return True
    
    async def _cleanup(self) -> None:
        """Clean up rotation solver resources."""
        logger.debug("Rotation solver resources cleaned up")