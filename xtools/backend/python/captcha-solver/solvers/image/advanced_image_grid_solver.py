"""
Advanced Image Grid CAPTCHA Solver with YOLO Integration
Production-grade implementation using state-of-the-art computer vision.
"""

import cv2
import numpy as np
import torch
from typing import Any, Dict, Optional, List, Tuple
from core.base_solver import BaseSolver
from models.base import CaptchaType
from models.responses import ImageGridSolution
from utils.advanced_image_utils import advanced_image_processor
from utils.ml_model_manager import model_manager
from utils.logger import get_logger
from utils.cache_utils import cache_manager

logger = get_logger(__name__)


class AdvancedImageGridSolver(BaseSolver):
    """
    Advanced image grid CAPTCHA solver using YOLO and modern computer vision.
    
    Features:
    - YOLO-based object detection for high accuracy
    - Multi-model ensemble for improved reliability
    - Advanced image preprocessing and enhancement
    - Intelligent instruction parsing
    - Production-grade error handling
    """
    
    def __init__(self):
        super().__init__("AdvancedImageGridSolver", CaptchaType.IMAGE_GRID)
        self.yolo_model = None
        self.classification_model = None
        self.confidence_threshold = 0.5
        
        self.object_mappings = {
            'car': ['car', 'automobile', 'vehicle', 'sedan', 'suv', 'truck', 'van', 'hatchback'],
            'bus': ['bus', 'coach', 'transit', 'minibus'],
            'bicycle': ['bicycle', 'bike', 'cycling', 'mountain bike', 'road bike'],
            'motorcycle': ['motorcycle', 'motorbike', 'scooter', 'moped'],
            'truck': ['truck', 'lorry', 'pickup', 'semi', 'trailer'],
            
            'traffic light': ['traffic light', 'stoplight', 'signal', 'traffic signal'],
            'crosswalk': ['crosswalk', 'zebra crossing', 'pedestrian crossing', 'crossing'],
            'fire hydrant': ['fire hydrant', 'hydrant', 'fire plug'],
            'stop sign': ['stop sign', 'stop', 'octagon sign'],
            'parking meter': ['parking meter', 'meter', 'pay station'],
            'street sign': ['street sign', 'road sign', 'sign'],
            'bridge': ['bridge', 'overpass', 'viaduct'],
            
            'boat': ['boat', 'ship', 'vessel', 'yacht', 'sailboat', 'speedboat', 'ferry'],
            'airplane': ['airplane', 'aircraft', 'plane', 'jet', 'airliner', 'fighter'],
            'train': ['train', 'locomotive', 'railway', 'subway', 'metro'],
            
            'mountain': ['mountain', 'hill', 'peak', 'summit', 'ridge'],
            'tree': ['tree', 'forest', 'woods', 'pine', 'oak', 'palm'],
            'flower': ['flower', 'bloom', 'blossom', 'rose', 'tulip', 'daisy'],
            'grass': ['grass', 'lawn', 'field', 'meadow'],
            'water': ['water', 'lake', 'river', 'ocean', 'sea', 'pond'],
            
            'animal': ['animal', 'dog', 'cat', 'bird', 'horse', 'cow', 'sheep', 'elephant', 'lion', 'tiger'],
            'dog': ['dog', 'puppy', 'canine', 'hound'],
            'cat': ['cat', 'kitten', 'feline'],
            'bird': ['bird', 'eagle', 'pigeon', 'sparrow', 'crow'],
            
            'person': ['person', 'people', 'human', 'man', 'woman', 'child'],
            'building': ['building', 'house', 'structure', 'skyscraper', 'tower'],
            'food': ['food', 'pizza', 'burger', 'sandwich', 'fruit', 'vegetable']
        }
        
        self.instruction_patterns = {
            'select_all': ['select all', 'click all', 'choose all', 'pick all'],
            'select_images_with': ['select all images with', 'click on all images with', 'choose images with'],
            'select_squares_with': ['select all squares with', 'click squares with'],
            'identify': ['identify', 'find', 'locate']
        }
    
    async def _initialize(self) -> None:
        """Initialize computer vision models."""
        try:
            await advanced_image_processor.initialize()
            
            if model_manager is not None:
                try:
                    self.yolo_model = await model_manager.get_object_detector("yolov8n")
                    
                    self.classification_model = await model_manager.get_image_classifier("resnet50")
                    
                    logger.info("Advanced image grid solver initialized with YOLO and ResNet")
                except Exception as e:
                    logger.warning(f"Failed to load advanced models, using basic mode: {e}")
                    self.yolo_model = None
                    self.classification_model = None
            else:
                logger.warning("Model manager not available, using basic mode")
                self.yolo_model = None
                self.classification_model = None
            
            logger.info("Advanced image grid solver initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize advanced image grid solver: {e}")
            self.yolo_model = None
            self.classification_model = None
    
    async def solve(self, captcha_data: Dict[str, Any]) -> Optional[ImageGridSolution]:
        """
        Solve image grid CAPTCHA using advanced computer vision.
        
        Args:
            captcha_data: Dictionary containing:
                - image_data: Base64 encoded image
                - instruction: Instruction text (e.g., "Select all images with cars")
                - grid_size: Grid size (e.g., "3x3", "4x4")
        
        Returns:
            ImageGridSolution with selected grid indices or None if failed
        """
        try:
            if not self.validate_input(captcha_data):
                return None
            
            cache_key = f"{captcha_data.get('image_data', '')}_{captcha_data.get('instruction', '')}"
            cached_result = await cache_manager.get_cached_model_result(
                "advanced_image_grid", cache_key
            )
            if cached_result:
                logger.debug("Using cached advanced image grid result")
                return ImageGridSolution(**cached_result)
            
            image = advanced_image_processor.decode_base64_image(captcha_data['image_data'])
            if image is None:
                logger.error("Failed to decode image data")
                return None
                
            enhanced_image = advanced_image_processor.enhance_image_quality(image)
            
            instruction = captcha_data['instruction'].lower()
            target_objects = await self._parse_instruction_advanced(instruction)
            
            if not target_objects:
                logger.warning(f"Could not parse instruction: {instruction}")
                return None
            
            logger.info(f"Target objects identified: {target_objects}")
            
            grid_size = captcha_data.get('grid_size', '3x3')
            grid_cells = advanced_image_processor.split_grid_image(enhanced_image, grid_size)
            
            if not grid_cells:
                logger.error("Failed to split image into grid cells")
                return None
            
            selected_indices = []
            confidence_scores = []
            
            for i, cell in enumerate(grid_cells):
                try:
                    yolo_result = await self._analyze_cell_with_yolo(cell, target_objects)
                    
                    classification_result = await self._analyze_cell_with_classification(cell, target_objects)
                    
                    combined_score = await self._combine_analysis_results(
                        yolo_result, classification_result, target_objects
                    )
                    
                    if combined_score['should_select']:
                        selected_indices.append(i)
                        confidence_scores.append(combined_score['confidence'])
                        logger.debug(f"Cell {i} selected: {combined_score['reason']} (confidence: {combined_score['confidence']:.2f})")
                    
                except Exception as e:
                    logger.debug(f"Error analyzing cell {i}: {e}")
                    continue
            
            overall_confidence = np.mean(confidence_scores) if confidence_scores else 0.5
            
            solution = ImageGridSolution(
                selected_indices=selected_indices,
                grid_size=grid_size,
                confidence=overall_confidence
            )
            
            await cache_manager.cache_model_result(
                "advanced_image_grid",
                cache_key,
                solution.dict()
            )
            
            logger.info(f"Advanced image grid CAPTCHA solved: selected {len(selected_indices)} cells with confidence {overall_confidence:.2f}")
            return solution
            
        except Exception as e:
            logger.error(f"Error solving advanced image grid CAPTCHA: {e}")
            return None
    
    async def _parse_instruction_advanced(self, instruction: str) -> List[str]:
        """Advanced instruction parsing with better accuracy."""
        target_objects = []
        
        for obj_type, keywords in self.object_mappings.items():
            for keyword in keywords:
                if keyword in instruction:
                    target_objects.append(obj_type)
                    break
        
        if 'vehicle' in instruction or 'vehicles' in instruction:
            target_objects.extend(['car', 'bus', 'motorcycle', 'bicycle', 'truck'])
        
        if 'traffic' in instruction:
            target_objects.extend(['traffic light', 'stop sign', 'street sign'])
        
        if 'transport' in instruction or 'transportation' in instruction:
            target_objects.extend(['car', 'bus', 'train', 'airplane', 'boat'])
        
        if 'nature' in instruction or 'natural' in instruction:
            target_objects.extend(['tree', 'flower', 'mountain', 'water', 'grass'])
        
        return list(set(target_objects))
    
    async def _analyze_cell_with_yolo(self, cell_image: np.ndarray, target_objects: List[str]) -> Dict[str, Any]:
        """Analyze grid cell using YOLO object detection."""
        try:
            enhanced_cell = advanced_image_processor.enhance_image_quality(cell_image, 1.3)
            
            detections = await advanced_image_processor.detect_objects_yolo(
                enhanced_cell, 
                conf_threshold=self.confidence_threshold,
                target_classes=target_objects
            )
            
            best_match = None
            best_confidence = 0.0
            
            for detection in detections:
                detected_class = detection['class_name'].lower()
                confidence = detection['confidence']
                
                for target_obj in target_objects:
                    if target_obj in self.object_mappings:
                        yolo_classes = self.object_mappings[target_obj]
                        
                        for yolo_class in yolo_classes:
                            if (yolo_class.lower() in detected_class or 
                                detected_class in yolo_class.lower() or
                                self._semantic_match(detected_class, yolo_class)):
                                
                                if confidence > best_confidence:
                                    best_confidence = confidence
                                    best_match = {
                                        'target': target_obj,
                                        'detected': detected_class,
                                        'confidence': confidence,
                                        'bbox': detection['bbox']
                                    }
            
            return {
                'method': 'yolo',
                'match': best_match,
                'confidence': best_confidence,
                'detections_count': len(detections)
            }
            
        except Exception as e:
            logger.debug(f"YOLO analysis failed: {e}")
            return {'method': 'yolo', 'match': None, 'confidence': 0.0, 'detections_count': 0}
    
    async def _analyze_cell_with_classification(self, cell_image: np.ndarray, target_objects: List[str]) -> Dict[str, Any]:
        """Analyze grid cell using image classification."""
        try:
            enhanced_cell = advanced_image_processor.resize_image(cell_image, (224, 224))
            
            classifications = await model_manager.classify_image(enhanced_cell, "resnet50", top_k=10)
            
            best_match = None
            best_confidence = 0.0
            
            for classification in classifications:
                label = classification['label'].lower()
                score = classification['score']
                
                for target_obj in target_objects:
                    if target_obj in self.object_mappings:
                        class_keywords = self.object_mappings[target_obj]
                        
                        for keyword in class_keywords:
                            if (keyword.lower() in label or 
                                label in keyword.lower() or
                                self._semantic_match(label, keyword)):
                                
                                if score > best_confidence:
                                    best_confidence = score
                                    best_match = {
                                        'target': target_obj,
                                        'classified': label,
                                        'confidence': score
                                    }
            
            return {
                'method': 'classification',
                'match': best_match,
                'confidence': best_confidence,
                'classifications_count': len(classifications)
            }
            
        except Exception as e:
            logger.debug(f"Classification analysis failed: {e}")
            return {'method': 'classification', 'match': None, 'confidence': 0.0, 'classifications_count': 0}
    
    async def _combine_analysis_results(
        self, 
        yolo_result: Dict[str, Any], 
        classification_result: Dict[str, Any],
        target_objects: List[str]
    ) -> Dict[str, Any]:
        """Combine YOLO and classification results with intelligent weighting."""
        
        yolo_confidence = yolo_result.get('confidence', 0.0)
        classification_confidence = classification_result.get('confidence', 0.0)
        
        yolo_weight = 0.7
        classification_weight = 0.3
        
        if yolo_confidence > 0.8:
            yolo_weight = 0.8
            classification_weight = 0.2
        elif classification_confidence > 0.9:
            yolo_weight = 0.6
            classification_weight = 0.4
        
        combined_confidence = (yolo_confidence * yolo_weight + 
                             classification_confidence * classification_weight)
        
        should_select = False
        reason = "No match found"
        
        if yolo_result.get('match') and yolo_confidence > 0.6:
            should_select = True
            reason = f"YOLO detected {yolo_result['match']['detected']} (conf: {yolo_confidence:.2f})"
        elif classification_result.get('match') and classification_confidence > 0.8:
            should_select = True
            reason = f"Classification found {classification_result['match']['classified']} (conf: {classification_confidence:.2f})"
        elif combined_confidence > 0.7:
            should_select = True
            reason = f"Combined analysis (conf: {combined_confidence:.2f})"
        
        return {
            'should_select': should_select,
            'confidence': combined_confidence,
            'reason': reason,
            'yolo_result': yolo_result,
            'classification_result': classification_result
        }
    
    def _semantic_match(self, term1: str, term2: str) -> bool:
        """Check for semantic similarity between terms."""
        synonyms = {
            'car': ['automobile', 'vehicle', 'sedan', 'suv'],
            'truck': ['lorry', 'pickup', 'semi'],
            'bike': ['bicycle', 'cycling'],
            'plane': ['airplane', 'aircraft', 'jet'],
            'boat': ['ship', 'vessel', 'yacht'],
            'person': ['human', 'people', 'man', 'woman'],
            'building': ['house', 'structure', 'tower']
        }
        
        for base_term, synonym_list in synonyms.items():
            if ((term1 == base_term and term2 in synonym_list) or
                (term2 == base_term and term1 in synonym_list) or
                (term1 in synonym_list and term2 in synonym_list)):
                return True
        
        return False
    
    def validate_input(self, captcha_data: Dict[str, Any]) -> bool:
        """Validate input data for advanced image grid CAPTCHA solving."""
        if not captcha_data.get('image_data'):
            logger.error("No image data provided")
            return False
        
        if not captcha_data.get('instruction'):
            logger.error("No instruction provided")
            return False
        
        grid_size = captcha_data.get('grid_size', '3x3')
        if 'x' not in grid_size:
            logger.error("Invalid grid size format")
            return False
        
        try:
            rows, cols = map(int, grid_size.split('x'))
            if rows < 1 or cols < 1 or rows > 10 or cols > 10:
                logger.error("Grid size out of reasonable range")
                return False
        except ValueError:
            logger.error("Invalid grid size values")
            return False
        
        return True
    
    async def _cleanup(self) -> None:
        """Clean up model resources."""
        self.yolo_model = None
        self.classification_model = None
        logger.debug("Advanced image grid solver resources cleaned up")