"""
Basic image utilities for CAPTCHA processing.
"""

import base64
import cv2
import numpy as np
from typing import Optional, List, Tuple
from utils.logger import get_logger

logger = get_logger(__name__)


class ImageProcessor:
    """Basic image processing utilities."""
    
    def __init__(self):
        pass
    
    def decode_base64_image(self, base64_data: str) -> Optional[np.ndarray]:
        """Decode base64 image data."""
        try:
            if ',' in base64_data:
                base64_data = base64_data.split(',')[1]
            
            image_data = base64.b64decode(base64_data)
            
            nparr = np.frombuffer(image_data, np.uint8)
            
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                logger.error("Failed to decode image")
                return None
            
            return image
            
        except Exception as e:
            logger.error(f"Error decoding base64 image: {e}")
            return None
    
    def encode_image_to_base64(self, image: np.ndarray, format: str = '.png') -> Optional[str]:
        """Encode image to base64."""
        try:
            _, buffer = cv2.imencode(format, image)
            image_base64 = base64.b64encode(buffer).decode('utf-8')
            return image_base64
        except Exception as e:
            logger.error(f"Error encoding image to base64: {e}")
            return None
    
    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Basic image preprocessing."""
        try:
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            denoised = cv2.medianBlur(gray, 3)
            
            enhanced = cv2.equalizeHist(denoised)
            
            return enhanced
            
        except Exception as e:
            logger.error(f"Error preprocessing image: {e}")
            return image
    
    def detect_rotation_angle(self, image: np.ndarray) -> Optional[float]:
        """Detect rotation angle of image."""
        try:
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            
            lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
            
            if lines is None:
                return 0.0
            
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
                return 0.0
            
            return float(np.median(angles))
            
        except Exception as e:
            logger.debug(f"Rotation detection failed: {e}")
            return 0.0
    
    def resize_image(self, image: np.ndarray, width: int, height: int) -> np.ndarray:
        """Resize image to specified dimensions."""
        try:
            return cv2.resize(image, (width, height))
        except Exception as e:
            logger.error(f"Error resizing image: {e}")
            return image
    
    def crop_image(self, image: np.ndarray, x: int, y: int, width: int, height: int) -> np.ndarray:
        """Crop image to specified region."""
        try:
            return image[y:y+height, x:x+width]
        except Exception as e:
            logger.error(f"Error cropping image: {e}")
            return image
    
    def enhance_image_quality(self, image: np.ndarray, factor: float = 1.2) -> np.ndarray:
        """Enhance image quality."""
        try:
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            sharpened = cv2.filter2D(image, -1, kernel)
            
            enhanced = cv2.addWeighted(image, 1-factor+1, sharpened, factor-1, 0)
            
            return enhanced
            
        except Exception as e:
            logger.error(f"Error enhancing image: {e}")
            return image