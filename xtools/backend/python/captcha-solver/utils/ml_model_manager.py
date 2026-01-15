"""
Advanced ML Model Manager for CAPTCHA Solving
Handles loading, caching, and management of machine learning models.
"""

import os
import asyncio
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Union, List

try:
    import torch
    from transformers import (
        AutoModel, AutoTokenizer, AutoImageProcessor, AutoModelForImageClassification,
        pipeline, WhisperProcessor, WhisperForConditionalGeneration
    )
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False
import cv2
import numpy as np
from .logger import get_logger
from .cache_utils import cache_manager

logger = get_logger(__name__)


class ModelManager:
    """Advanced model manager for CAPTCHA solving with caching and optimization."""
    
    def __init__(self, cache_dir: str = "./models_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.loaded_models: Dict[str, Any] = {}
        self.model_configs = {
            "resnet50": {
                "model_name": "microsoft/resnet-50",
                "type": "image_classification",
                "processor_class": AutoImageProcessor,
                "model_class": AutoModelForImageClassification
            },
            "vit_base": {
                "model_name": "google/vit-base-patch16-224",
                "type": "image_classification", 
                "processor_class": AutoImageProcessor,
                "model_class": AutoModelForImageClassification
            },
            "efficientnet": {
                "model_name": "google/efficientnet-b0",
                "type": "image_classification",
                "processor_class": AutoImageProcessor,
                "model_class": AutoModelForImageClassification
            },
            
            "yolov8n": {
                "model_name": "yolov8n.pt",
                "type": "object_detection",
                "model_class": YOLO
            },
            "yolov8s": {
                "model_name": "yolov8s.pt", 
                "type": "object_detection",
                "model_class": YOLO
            },
            "yolov8m": {
                "model_name": "yolov8m.pt",
                "type": "object_detection",
                "model_class": YOLO
            },
            "yolov10n": {
                "model_name": "yolov10n.pt",
                "type": "object_detection", 
                "model_class": YOLO
            },
            
            "whisper_tiny": {
                "model_name": "openai/whisper-tiny",
                "type": "speech_recognition",
                "processor_class": WhisperProcessor,
                "model_class": WhisperForConditionalGeneration
            },
            "whisper_base": {
                "model_name": "openai/whisper-base",
                "type": "speech_recognition",
                "processor_class": WhisperProcessor,
                "model_class": WhisperForConditionalGeneration
            },
            "whisper_small": {
                "model_name": "openai/whisper-small",
                "type": "speech_recognition",
                "processor_class": WhisperProcessor,
                "model_class": WhisperForConditionalGeneration
            }
        }
        
    async def load_model(self, model_key: str, device: Optional[str] = None) -> Dict[str, Any]:
        """Load and cache a model with its processor."""
        if model_key in self.loaded_models:
            logger.debug(f"Model {model_key} already loaded")
            return self.loaded_models[model_key]
            
        if model_key not in self.model_configs:
            raise ValueError(f"Unknown model key: {model_key}")
            
        config = self.model_configs[model_key]
        
        try:
            logger.info(f"Loading model: {model_key}")
            
            if device is None:
                device = "cuda" if torch.cuda.is_available() else "cpu"
                
            model_data = {"config": config, "device": device}
            
            if config["type"] == "object_detection":
                model = config["model_class"](config["model_name"])
                model_data["model"] = model
                
            elif config["type"] in ["image_classification", "speech_recognition"]:
                processor = config["processor_class"].from_pretrained(config["model_name"])
                model = config["model_class"].from_pretrained(config["model_name"])
                
                if device == "cuda" and torch.cuda.is_available():
                    model = model.to(device)
                    
                model_data["processor"] = processor
                model_data["model"] = model
                
                if config["type"] == "image_classification":
                    pipeline_obj = pipeline(
                        "image-classification",
                        model=model,
                        image_processor=processor,
                        device=0 if device == "cuda" else -1
                    )
                elif config["type"] == "speech_recognition":
                    pipeline_obj = pipeline(
                        "automatic-speech-recognition",
                        model=model,
                        tokenizer=processor.tokenizer,
                        feature_extractor=processor.feature_extractor,
                        device=0 if device == "cuda" else -1
                    )
                    
                model_data["pipeline"] = pipeline_obj
                
            self.loaded_models[model_key] = model_data
            logger.info(f"Successfully loaded model: {model_key}")
            return model_data
            
        except Exception as e:
            logger.error(f"Failed to load model {model_key}: {e}")
            raise
            
    async def get_image_classifier(self, model_key: str = "resnet50") -> Dict[str, Any]:
        """Get an image classification model."""
        return await self.load_model(model_key)
        
    async def get_object_detector(self, model_key: str = "yolov8n") -> Dict[str, Any]:
        """Get an object detection model."""
        return await self.load_model(model_key)
        
    async def get_speech_recognizer(self, model_key: str = "whisper_base") -> Dict[str, Any]:
        """Get a speech recognition model."""
        return await self.load_model(model_key)
        
    async def classify_image(self, image: Union[np.ndarray, str], model_key: str = "resnet50", top_k: int = 5) -> List[Dict[str, Any]]:
        """Classify an image using the specified model."""
        try:
            model_data = await self.get_image_classifier(model_key)
            pipeline_obj = model_data["pipeline"]
            
            if isinstance(image, str):
                from PIL import Image
                image = Image.open(image)
            elif isinstance(image, np.ndarray):
                from PIL import Image
                if len(image.shape) == 2:
                    image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
                image = Image.fromarray(image)
                
            results = pipeline_obj(image, top_k=top_k)
            return results
            
        except Exception as e:
            logger.error(f"Image classification failed: {e}")
            return []
            
    async def detect_objects(self, image: Union[np.ndarray, str], model_key: str = "yolov8n", conf_threshold: float = 0.5) -> List[Dict[str, Any]]:
        """Detect objects in an image using YOLO."""
        try:
            model_data = await self.get_object_detector(model_key)
            model = model_data["model"]
            
            results = model(image, conf=conf_threshold)
            
            detections = []
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for i in range(len(boxes)):
                        detection = {
                            "class_id": int(boxes.cls[i]),
                            "class_name": model.names[int(boxes.cls[i])],
                            "confidence": float(boxes.conf[i]),
                            "bbox": boxes.xyxy[i].tolist(),
                            "center": [(boxes.xyxy[i][0] + boxes.xyxy[i][2]) / 2, 
                                     (boxes.xyxy[i][1] + boxes.xyxy[i][3]) / 2]
                        }
                        detections.append(detection)
                        
            return detections
            
        except Exception as e:
            logger.error(f"Object detection failed: {e}")
            return []
            
    async def transcribe_audio(self, audio_data: Union[np.ndarray, str], model_key: str = "whisper_base", language: str = "en") -> Dict[str, Any]:
        """Transcribe audio using Whisper."""
        try:
            model_data = await self.get_speech_recognizer(model_key)
            pipeline_obj = model_data["pipeline"]
            
            if isinstance(audio_data, str):
                import librosa
                audio_data, sr = librosa.load(audio_data, sr=16000)
            elif isinstance(audio_data, np.ndarray):
                if len(audio_data.shape) > 1:
                    audio_data = audio_data.mean(axis=1)
                    
            result = pipeline_obj(audio_data, return_timestamps=True)
            
            return {
                "text": result["text"],
                "chunks": result.get("chunks", []),
                "confidence": 0.8
            }
            
        except Exception as e:
            logger.error(f"Audio transcription failed: {e}")
            return {"text": "", "chunks": [], "confidence": 0.0}
            
    async def fine_tune_yolo_for_captcha(self, dataset_path: str, model_key: str = "yolov8n", epochs: int = 100) -> str:
        """Fine-tune YOLO model for CAPTCHA-specific object detection."""
        try:
            model_data = await self.get_object_detector(model_key)
            model = model_data["model"]
            
            results = model.train(
                data=dataset_path,
                epochs=epochs,
                imgsz=640,
                batch=16,
                device=model_data["device"]
            )
            
            model_path = self.cache_dir / f"{model_key}_captcha_finetuned.pt"
            model.save(str(model_path))
            
            logger.info(f"Fine-tuned model saved to: {model_path}")
            return str(model_path)
            
        except Exception as e:
            logger.error(f"Fine-tuning failed: {e}")
            raise
            
    def get_model_info(self, model_key: str) -> Dict[str, Any]:
        """Get information about a model."""
        if model_key not in self.model_configs:
            return {}
            
        config = self.model_configs[model_key].copy()
        config["loaded"] = model_key in self.loaded_models
        
        if config["loaded"]:
            config["device"] = self.loaded_models[model_key]["device"]
            
        return config
        
    def list_available_models(self) -> List[str]:
        """List all available model keys."""
        return list(self.model_configs.keys())
        
    def list_loaded_models(self) -> List[str]:
        """List currently loaded model keys."""
        return list(self.loaded_models.keys())
        
    async def unload_model(self, model_key: str) -> None:
        """Unload a model from memory."""
        if model_key in self.loaded_models:
            del self.loaded_models[model_key]
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info(f"Unloaded model: {model_key}")
            
    async def unload_all_models(self) -> None:
        """Unload all models from memory."""
        self.loaded_models.clear()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("Unloaded all models")
        
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage information."""
        info = {
            "loaded_models": len(self.loaded_models),
            "available_models": len(self.model_configs)
        }
        
        if torch.cuda.is_available():
            info["gpu_memory_allocated"] = torch.cuda.memory_allocated()
            info["gpu_memory_reserved"] = torch.cuda.memory_reserved()
            
        return info


if TORCH_AVAILABLE:
    model_manager = ModelManager()
else:
    model_manager = None