import numpy as np
from typing import Any, Dict, Optional, List
from core.base_solver import BaseSolver
from models.base import CaptchaType
from models.responses import AudioSolution
from utils.advanced_audio_utils import AdvancedAudioProcessor
from utils.logger import get_logger
from utils.cache_utils import cache_manager

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False

try:
    from transformers import pipeline, Wav2Vec2Processor, Wav2Vec2ForCTC
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

try:
    from utils.advanced_audio_utils import advanced_audio_processor
    ADVANCED_AUDIO_AVAILABLE = True
except ImportError:
    ADVANCED_AUDIO_AVAILABLE = False

try:
    from utils.ml_model_manager import model_manager
    MODEL_MANAGER_AVAILABLE = True
except ImportError:
    MODEL_MANAGER_AVAILABLE = False

logger = get_logger(__name__)


class AdvancedAudioSolver(BaseSolver):
    """
    Advanced audio CAPTCHA solver using modern speech recognition.
    
    Features:
    - Whisper integration for state-of-the-art speech recognition
    - Advanced noise reduction and speech enhancement
    - Multiple transcription methods with confidence scoring
    - Production-grade error handling and fallbacks
    """
    
    def __init__(self):
        super().__init__("AdvancedAudioSolver", CaptchaType.AUDIO)
        self.audio_processor = AdvancedAudioProcessor()
        self.whisper_model = None
        self.speech_recognizer = None
        self.wav2vec_processor = None
        self.wav2vec_model = None
        self.confidence_threshold = 0.7
        self.available_engines = []
    
    async def _initialize(self) -> None:
        """Initialize speech recognition models including Whisper."""
        try:
            if ADVANCED_AUDIO_AVAILABLE:
                await advanced_audio_processor.initialize()
                self.available_engines.append('advanced_audio')
            
            if WHISPER_AVAILABLE:
                try:
                    self.whisper_model = whisper.load_model("base")
                    self.available_engines.append('whisper')
                    logger.info("Whisper model loaded successfully")
                except Exception as e:
                    logger.warning(f"Failed to load Whisper model: {e}")
            
            if TRANSFORMERS_AVAILABLE and TORCH_AVAILABLE:
                try:
                    model_name = "facebook/wav2vec2-base-960h"
                    self.wav2vec_processor = Wav2Vec2Processor.from_pretrained(model_name)
                    self.wav2vec_model = Wav2Vec2ForCTC.from_pretrained(model_name)
                    
                    self.speech_recognizer = pipeline(
                        "automatic-speech-recognition",
                        model=self.wav2vec_model,
                        tokenizer=self.wav2vec_processor.tokenizer,
                        feature_extractor=self.wav2vec_processor.feature_extractor,
                        device=0 if torch.cuda.is_available() else -1
                    )
                    self.available_engines.append('wav2vec2')
                    logger.info("Wav2Vec2 model loaded successfully")
                except Exception as e:
                    logger.warning(f"Failed to load Wav2Vec2 model: {e}")
            
            if MODEL_MANAGER_AVAILABLE:
                try:
                    whisper_model = await model_manager.get_speech_recognizer("whisper_base")
                    if whisper_model:
                        self.whisper_model = whisper_model
                        if 'whisper' not in self.available_engines:
                            self.available_engines.append('whisper')
                except Exception as e:
                    logger.debug(f"Model manager initialization failed: {e}")
            
            if not self.available_engines:
                logger.warning("No speech recognition engines available, audio solving may be limited")
            else:
                logger.info(f"Available speech recognition engines: {', '.join(self.available_engines)}")
            
        except Exception as e:
            logger.error(f"Failed to initialize speech recognition models: {e}")
    
    async def solve(self, captcha_data: Dict[str, Any]) -> Optional[AudioSolution]:
        """
        Solve audio CAPTCHA.
        
        Args:
            captcha_data: Dictionary containing:
                - audio_data: Base64 encoded audio data
                - audio_format: Audio format (wav, mp3, etc.)
                - language: Expected language (default: en)
        
        Returns:
            AudioSolution with transcribed text or None if failed
        """
        try:
            if not self.validate_input(captcha_data):
                return None
            
            cached_result = await cache_manager.get_cached_model_result(
                "audio_speech", captcha_data.get('audio_data', '')
            )
            if cached_result:
                logger.debug("Using cached speech recognition result")
                return AudioSolution(**cached_result)
            
            audio_data, sample_rate = advanced_audio_processor.decode_base64_audio(
                captcha_data['audio_data']
            )
            
            processed_audio, processed_sr = advanced_audio_processor.resample_audio(
                audio_data, sample_rate, 16000
            )
            
            enhanced_audio = await self._preprocess_audio_for_captcha(processed_audio, processed_sr)
            
            transcription_candidates = await self._transcribe_audio_multiple_methods(
                enhanced_audio, processed_sr
            )
            
            best_transcription = await self._select_best_transcription(
                transcription_candidates, captcha_data
            )
            
            if not best_transcription:
                logger.warning("No valid transcription found for audio CAPTCHA")
                return None
            
            solution = AudioSolution(
                transcription=best_transcription['text'],
                confidence=best_transcription['confidence'],
                language=captcha_data.get('language', 'en')
            )
            
            await cache_manager.cache_model_result(
                "audio_speech",
                captcha_data.get('audio_data', ''),
                solution.dict()
            )
            
            logger.info(f"Audio CAPTCHA solved: '{best_transcription['text']}' (confidence: {best_transcription['confidence']:.2f})")
            return solution
            
        except Exception as e:
            logger.error(f"Error solving audio CAPTCHA: {e}")
            return None
    
    async def _transcribe_audio_multiple_methods(
        self, 
        audio_data: np.ndarray, 
        sample_rate: int
    ) -> List[Dict[str, Any]]:
        """Transcribe audio using multiple methods including Whisper for better accuracy."""
        candidates = []
        
        try:
            whisper_result = await advanced_audio_processor.transcribe_with_whisper(
                audio_data, language="en"
            )
            if whisper_result and whisper_result['text'].strip():
                candidates.append({
                    'text': whisper_result['text'].strip(),
                    'confidence': whisper_result.get('confidence', 0.9),
                    'method': 'whisper'
                })
        except Exception as e:
            logger.debug(f"Whisper transcription failed: {e}")
        
        try:
            result = self.speech_recognizer(audio_data, sampling_rate=sample_rate)
            if result and 'text' in result:
                candidates.append({
                    'text': result['text'].strip(),
                    'confidence': 0.8,
                    'method': 'wav2vec2_pipeline'
                })
        except Exception as e:
            logger.debug(f"Wav2Vec2 pipeline transcription failed: {e}")
        
        try:
            transcription = await self._transcribe_with_wav2vec2_direct(audio_data, sample_rate)
            if transcription:
                candidates.append(transcription)
        except Exception as e:
            logger.debug(f"Direct Wav2Vec2 transcription failed: {e}")
        
        try:
            enhanced = advanced_audio_processor.enhance_speech_quality(audio_data, sample_rate)
            whisper_enhanced = await advanced_audio_processor.transcribe_with_whisper(
                enhanced, language="en"
            )
            if whisper_enhanced and whisper_enhanced['text'].strip():
                candidates.append({
                    'text': whisper_enhanced['text'].strip(),
                    'confidence': whisper_enhanced.get('confidence', 0.85),
                    'method': 'whisper_enhanced'
                })
        except Exception as e:
            logger.debug(f"Enhanced Whisper transcription failed: {e}")
        
        try:
            segmented_results = await self._transcribe_segmented(audio_data, sample_rate)
            candidates.extend(segmented_results)
        except Exception as e:
            logger.debug(f"Segmented transcription failed: {e}")
        
        return candidates
    
    async def _transcribe_with_wav2vec2_direct(
        self, 
        audio_data: np.ndarray, 
        sample_rate: int
    ) -> Optional[Dict[str, Any]]:
        """Transcribe audio using direct Wav2Vec2 model inference."""
        try:
            input_values = self.wav2vec_processor(
                audio_data, 
                sampling_rate=sample_rate, 
                return_tensors="pt"
            ).input_values
            
            with torch.no_grad():
                logits = self.wav2vec_model(input_values).logits
            
            predicted_ids = torch.argmax(logits, dim=-1)
            transcription = self.wav2vec_processor.decode(predicted_ids[0])
            
            confidence = torch.softmax(logits, dim=-1).max().item()
            
            return {
                'text': transcription.strip(),
                'confidence': confidence,
                'method': 'wav2vec2_direct'
            }
            
        except Exception as e:
            logger.debug(f"Direct Wav2Vec2 inference failed: {e}")
            return None
    
    async def _transcribe_segmented(
        self, 
        audio_data: np.ndarray, 
        sample_rate: int
    ) -> List[Dict[str, Any]]:
        """Transcribe audio by segmenting it into smaller chunks."""
        candidates = []
        
        try:
            speech_segments = self.audio_processor.detect_speech_segments(audio_data, sample_rate)
            
            if not speech_segments:
                return candidates
            
            segment_transcriptions = []
            for start_time, end_time in speech_segments:
                start_sample = int(start_time * sample_rate)
                end_sample = int(end_time * sample_rate)
                
                segment_audio = audio_data[start_sample:end_sample]
                
                if len(segment_audio) > sample_rate * 0.5:
                    try:
                        result = self.speech_recognizer(segment_audio, sampling_rate=sample_rate)
                        if result and 'text' in result and result['text'].strip():
                            segment_transcriptions.append(result['text'].strip())
                    except Exception as e:
                        logger.debug(f"Segment transcription failed: {e}")
                        continue
            
            if segment_transcriptions:
                combined_text = ' '.join(segment_transcriptions)
                candidates.append({
                    'text': combined_text,
                    'confidence': 0.7,
                    'method': 'segmented'
                })
            
        except Exception as e:
            logger.debug(f"Segmented transcription failed: {e}")
        
        return candidates
    
    async def _select_best_transcription(
        self, 
        candidates: List[Dict[str, Any]], 
        captcha_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Select the best transcription from candidates."""
        if not candidates:
            return None
        
        valid_candidates = [c for c in candidates if c['text'].strip()]
        
        if not valid_candidates:
            return None
        
        scored_candidates = []
        for candidate in valid_candidates:
            score = await self._score_transcription(candidate, captcha_data)
            scored_candidates.append((score, candidate))
        
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        
        best_score, best_candidate = scored_candidates[0]
        if best_candidate['confidence'] >= self.confidence_threshold:
            return best_candidate
        
        return best_candidate
    
    async def _score_transcription(
        self, 
        candidate: Dict[str, Any], 
        captcha_data: Dict[str, Any]
    ) -> float:
        """Score a transcription candidate."""
        score = candidate['confidence']
        
        text = candidate['text'].strip()
        
        if 3 <= len(text) <= 20:
            score += 0.1
        elif len(text) < 3:
            score -= 0.2
        elif len(text) > 30:
            score -= 0.1
        
        alphanumeric_ratio = sum(c.isalnum() for c in text) / len(text) if text else 0
        score += alphanumeric_ratio * 0.1
        
        special_char_ratio = sum(not c.isalnum() and not c.isspace() for c in text) / len(text) if text else 0
        score -= special_char_ratio * 0.2
        
        if text.isdigit():
            score += 0.05
        
        if text.isalpha():
            score += 0.05
        
        if 'direct' in candidate.get('method', ''):
            score += 0.05
        
        return max(0.0, min(1.0, score))
    
    async def _preprocess_audio_for_captcha(self, audio_data: np.ndarray, sample_rate: int) -> np.ndarray:
        """Advanced preprocessing specifically for CAPTCHA audio."""
        try:
            quality_issues = advanced_audio_processor.detect_audio_quality_issues(audio_data, sample_rate)
            logger.debug(f"Audio quality score: {quality_issues.get('quality_score', 0.5):.2f}")
            
            processed_audio = audio_data.copy()
            
            if quality_issues.get('high_noise', False):
                logger.debug("Applying noise reduction")
                processed_audio = advanced_audio_processor.reduce_noise_spectral_subtraction(
                    processed_audio, sample_rate, noise_factor=2.5
                )
            
            if quality_issues.get('low_volume', False):
                logger.debug("Applying volume normalization")
                processed_audio = advanced_audio_processor.normalize_audio(
                    processed_audio, method="rms"
                )
            
            enhanced_audio = advanced_audio_processor.enhance_speech_quality(processed_audio, sample_rate)
            
            final_audio = advanced_audio_processor.normalize_audio(enhanced_audio, method="peak")
            
            return final_audio
            
        except Exception as e:
            logger.error(f"Audio preprocessing failed: {e}")
            return audio_data
    
    async def _clean_transcription(self, text: str) -> str:
        """Clean and normalize transcription text."""
        text = ' '.join(text.split())
        
        artifacts = ['<unk>', '<pad>', '<s>', '</s>']
        for artifact in artifacts:
            text = text.replace(artifact, '')
        
        text = text.replace(' .', '.')
        text = text.replace(' ,', ',')
        text = text.replace(' ?', '?')
        text = text.replace(' !', '!')
        
        return text.strip()
    
    def validate_input(self, captcha_data: Dict[str, Any]) -> bool:
        """Validate input data for audio CAPTCHA solving."""
        if not captcha_data.get('audio_data'):
            logger.error("No audio data provided")
            return False
        
        audio_format = captcha_data.get('audio_format', 'wav')
        supported_formats = ['wav', 'mp3', 'ogg', 'flac', 'm4a']
        
        if audio_format.lower() not in supported_formats:
            logger.warning(f"Audio format {audio_format} may not be supported")
        
        return True
    
    async def _cleanup(self) -> None:
        """Clean up model resources."""
        self.speech_recognizer = None
        self.wav2vec_processor = None
        self.wav2vec_model = None
        logger.debug("Audio solver resources cleaned up")