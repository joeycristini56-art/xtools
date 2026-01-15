"""
Advanced Audio Processing Utilities for CAPTCHA Solving
Includes Whisper integration, advanced noise reduction, and speech enhancement.
"""

import base64
import io
import numpy as np
try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False

try:
    import soundfile as sf
    SOUNDFILE_AVAILABLE = True
except ImportError:
    SOUNDFILE_AVAILABLE = False

from scipy import signal
from scipy.signal import butter, filtfilt, wiener

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
from typing import Tuple, List, Dict, Any, Optional, Union
from .logger import get_logger
from .ml_model_manager import model_manager

logger = get_logger(__name__)


class AdvancedAudioProcessor:
    """Advanced audio processing with modern speech recognition techniques."""
    
    def __init__(self):
        self.whisper_model = None
        self.sample_rate = 16000
        
    async def initialize(self):
        """Initialize ML models for audio processing."""
        try:
            self.whisper_model = await model_manager.get_speech_recognizer("whisper_base")
            
            logger.info("Advanced audio processor initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize audio processor: {e}")
            
    def decode_base64_audio(self, base64_data: str, expected_format: str = "wav") -> Tuple[np.ndarray, int]:
        """Decode base64 audio data with enhanced format support."""
        try:
            if base64_data.startswith('data:audio'):
                base64_data = base64_data.split(',')[1]
            
            audio_bytes = base64.b64decode(base64_data)
            
            audio_data, sample_rate = sf.read(io.BytesIO(audio_bytes))
            
            if len(audio_data.shape) > 1:
                audio_data = np.mean(audio_data, axis=1)
                
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
                
            return audio_data, sample_rate
            
        except Exception as e:
            logger.error(f"Failed to decode base64 audio: {e}")
            try:
                audio_data, sample_rate = librosa.load(io.BytesIO(base64.b64decode(base64_data)), sr=None)
                return audio_data, sample_rate
            except Exception as e2:
                logger.error(f"Fallback audio decoding also failed: {e2}")
                raise ValueError(f"Invalid base64 audio data: {e}")
                
    def resample_audio(self, audio_data: np.ndarray, original_sr: int, target_sr: int = None) -> Tuple[np.ndarray, int]:
        """Resample audio to target sample rate."""
        try:
            if target_sr is None:
                target_sr = self.sample_rate
                
            if original_sr == target_sr:
                return audio_data, original_sr
                
            resampled = librosa.resample(audio_data, orig_sr=original_sr, target_sr=target_sr)
            return resampled, target_sr
            
        except Exception as e:
            logger.error(f"Audio resampling failed: {e}")
            return audio_data, original_sr
            
    def normalize_audio(self, audio_data: np.ndarray, method: str = "peak") -> np.ndarray:
        """Normalize audio using various methods."""
        try:
            if method == "peak":
                max_val = np.max(np.abs(audio_data))
                if max_val > 0:
                    return audio_data / max_val
                return audio_data
                
            elif method == "rms":
                rms = np.sqrt(np.mean(audio_data ** 2))
                if rms > 0:
                    return audio_data / rms * 0.1
                return audio_data
                
            elif method == "lufs":
                target_lufs = -23.0
                current_lufs = 20 * np.log10(np.sqrt(np.mean(audio_data ** 2)) + 1e-10)
                gain = target_lufs - current_lufs
                return audio_data * (10 ** (gain / 20))
                
            else:
                return audio_data
                
        except Exception as e:
            logger.error(f"Audio normalization failed: {e}")
            return audio_data
            
    def reduce_noise_spectral_subtraction(self, audio_data: np.ndarray, sample_rate: int, noise_factor: float = 2.0) -> np.ndarray:
        """Advanced noise reduction using spectral subtraction."""
        try:
            stft = librosa.stft(audio_data, n_fft=2048, hop_length=512)
            magnitude = np.abs(stft)
            phase = np.angle(stft)
            
            noise_frames = int(0.5 * sample_rate / 512)
            noise_spectrum = np.mean(magnitude[:, :noise_frames], axis=1, keepdims=True)
            
            alpha = noise_factor
            beta = 0.01
            
            subtracted_magnitude = magnitude - alpha * noise_spectrum
            
            floor_magnitude = beta * magnitude
            cleaned_magnitude = np.maximum(subtracted_magnitude, floor_magnitude)
            
            cleaned_stft = cleaned_magnitude * np.exp(1j * phase)
            cleaned_audio = librosa.istft(cleaned_stft, hop_length=512)
            
            return cleaned_audio
            
        except Exception as e:
            logger.error(f"Spectral subtraction failed: {e}")
            return audio_data
            
    def reduce_noise_wiener(self, audio_data: np.ndarray, noise_estimate: Optional[np.ndarray] = None) -> np.ndarray:
        """Noise reduction using Wiener filtering."""
        try:
            if noise_estimate is None:
                noise_samples = int(0.5 * len(audio_data))
                noise_estimate = audio_data[:noise_samples]
                
            cleaned_audio = wiener(audio_data, noise=np.var(noise_estimate))
            
            return cleaned_audio
            
        except Exception as e:
            logger.error(f"Wiener filtering failed: {e}")
            return audio_data
            
    def enhance_speech_quality(self, audio_data: np.ndarray, sample_rate: int) -> np.ndarray:
        """Enhance speech quality using multiple techniques."""
        try:
            pre_emphasis = 0.97
            emphasized = np.append(audio_data[0], audio_data[1:] - pre_emphasis * audio_data[:-1])
            
            nyquist = sample_rate / 2
            low_freq = 300 / nyquist
            high_freq = 3400 / nyquist
            
            b, a = butter(4, [low_freq, high_freq], btype='band')
            filtered = filtfilt(b, a, emphasized)
            
            compressed = self._apply_compression(filtered)
            
            normalized = self.normalize_audio(compressed, method="peak")
            
            return normalized
            
        except Exception as e:
            logger.error(f"Speech enhancement failed: {e}")
            return audio_data
            
    def _apply_compression(self, audio_data: np.ndarray, threshold: float = 0.5, ratio: float = 4.0) -> np.ndarray:
        """Apply dynamic range compression."""
        try:
            compressed = np.copy(audio_data)
            
            above_threshold = np.abs(compressed) > threshold
            
            compressed[above_threshold] = np.sign(compressed[above_threshold]) * (
                threshold + (np.abs(compressed[above_threshold]) - threshold) / ratio
            )
            
            return compressed
            
        except Exception as e:
            logger.error(f"Audio compression failed: {e}")
            return audio_data
            
    def detect_speech_segments(self, audio_data: np.ndarray, sample_rate: int, min_duration: float = 0.3) -> List[Tuple[float, float]]:
        """Detect speech segments using voice activity detection."""
        try:
            hop_length = 512
            frame_length = 2048
            
            rms = librosa.feature.rms(y=audio_data, frame_length=frame_length, hop_length=hop_length)[0]
            
            spectral_centroid = librosa.feature.spectral_centroid(y=audio_data, sr=sample_rate, hop_length=hop_length)[0]
            
            energy_threshold = np.percentile(rms, 30)
            centroid_threshold = np.percentile(spectral_centroid, 40)
            
            speech_frames = (rms > energy_threshold) & (spectral_centroid > centroid_threshold)
            
            frame_times = librosa.frames_to_time(np.arange(len(speech_frames)), sr=sample_rate, hop_length=hop_length)
            
            segments = []
            start_time = None
            
            for i, is_speech in enumerate(speech_frames):
                if is_speech and start_time is None:
                    start_time = frame_times[i]
                elif not is_speech and start_time is not None:
                    end_time = frame_times[i]
                    if end_time - start_time >= min_duration:
                        segments.append((start_time, end_time))
                    start_time = None
                    
            if start_time is not None:
                end_time = frame_times[-1]
                if end_time - start_time >= min_duration:
                    segments.append((start_time, end_time))
                    
            return segments
            
        except Exception as e:
            logger.error(f"Speech segment detection failed: {e}")
            return [(0.0, len(audio_data) / sample_rate)]
            
    async def transcribe_with_whisper(self, audio_data: np.ndarray, language: str = "en") -> Dict[str, Any]:
        """Transcribe audio using Whisper with advanced preprocessing."""
        try:
            if self.whisper_model is None:
                await self.initialize()
                
            processed_audio = self.preprocess_for_whisper(audio_data)
            
            result = await model_manager.transcribe_audio(processed_audio, "whisper_base", language)
            
            return result
            
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return {"text": "", "chunks": [], "confidence": 0.0}
            
    def preprocess_for_whisper(self, audio_data: np.ndarray) -> np.ndarray:
        """Preprocess audio specifically for Whisper model."""
        try:
            if len(audio_data.shape) > 1:
                audio_data = np.mean(audio_data, axis=1)
                
            audio_data = self.normalize_audio(audio_data, method="peak")
            
            cleaned_audio = self.reduce_noise_spectral_subtraction(audio_data, self.sample_rate, noise_factor=1.5)
            
            enhanced_audio = self.enhance_speech_quality(cleaned_audio, self.sample_rate)
            
            max_length = 30 * self.sample_rate
            if len(enhanced_audio) > max_length:
                enhanced_audio = enhanced_audio[:max_length]
            elif len(enhanced_audio) < self.sample_rate:
                padding = self.sample_rate - len(enhanced_audio)
                enhanced_audio = np.pad(enhanced_audio, (0, padding), mode='constant')
                
            return enhanced_audio
            
        except Exception as e:
            logger.error(f"Whisper preprocessing failed: {e}")
            return audio_data
            
    def extract_audio_features(self, audio_data: np.ndarray, sample_rate: int) -> Dict[str, Any]:
        """Extract comprehensive audio features for analysis."""
        try:
            features = {}
            
            features['duration'] = len(audio_data) / sample_rate
            features['sample_rate'] = sample_rate
            features['rms_energy'] = np.sqrt(np.mean(audio_data ** 2))
            features['zero_crossing_rate'] = np.mean(librosa.feature.zero_crossing_rate(audio_data))
            
            spectral_centroids = librosa.feature.spectral_centroid(y=audio_data, sr=sample_rate)[0]
            features['spectral_centroid_mean'] = np.mean(spectral_centroids)
            features['spectral_centroid_std'] = np.std(spectral_centroids)
            
            spectral_rolloff = librosa.feature.spectral_rolloff(y=audio_data, sr=sample_rate)[0]
            features['spectral_rolloff_mean'] = np.mean(spectral_rolloff)
            
            spectral_bandwidth = librosa.feature.spectral_bandwidth(y=audio_data, sr=sample_rate)[0]
            features['spectral_bandwidth_mean'] = np.mean(spectral_bandwidth)
            
            mfccs = librosa.feature.mfcc(y=audio_data, sr=sample_rate, n_mfcc=13)
            for i in range(13):
                features[f'mfcc_{i}_mean'] = np.mean(mfccs[i])
                features[f'mfcc_{i}_std'] = np.std(mfccs[i])
                
            chroma = librosa.feature.chroma_stft(y=audio_data, sr=sample_rate)
            features['chroma_mean'] = np.mean(chroma)
            features['chroma_std'] = np.std(chroma)
            
            tempo, _ = librosa.beat.beat_track(y=audio_data, sr=sample_rate)
            features['tempo'] = tempo
            
            return features
            
        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            return {}
            
    def detect_audio_quality_issues(self, audio_data: np.ndarray, sample_rate: int) -> Dict[str, Any]:
        """Detect common audio quality issues."""
        try:
            issues = {
                'clipping': False,
                'low_volume': False,
                'high_noise': False,
                'distortion': False,
                'quality_score': 1.0
            }
            
            clipping_threshold = 0.95
            if np.max(np.abs(audio_data)) > clipping_threshold:
                issues['clipping'] = True
                issues['quality_score'] -= 0.3
                
            rms = np.sqrt(np.mean(audio_data ** 2))
            if rms < 0.01:
                issues['low_volume'] = True
                issues['quality_score'] -= 0.2
                
            stft = librosa.stft(audio_data)
            magnitude = np.abs(stft)
            
            noise_floor = np.percentile(magnitude, 10)
            signal_level = np.percentile(magnitude, 90)
            
            if noise_floor / (signal_level + 1e-10) > 0.1:
                issues['high_noise'] = True
                issues['quality_score'] -= 0.2
                
            try:
                fft = np.fft.fft(audio_data)
                magnitude_spectrum = np.abs(fft)
                
                freqs = np.fft.fftfreq(len(fft), 1/sample_rate)
                fundamental_idx = np.argmax(magnitude_spectrum[:len(magnitude_spectrum)//2])
                
                if fundamental_idx > 0:
                    fundamental_power = magnitude_spectrum[fundamental_idx]
                    harmonic_power = 0
                    
                    for harmonic in range(2, 6):
                        harmonic_idx = fundamental_idx * harmonic
                        if harmonic_idx < len(magnitude_spectrum):
                            harmonic_power += magnitude_spectrum[harmonic_idx]
                            
                    thd = harmonic_power / (fundamental_power + 1e-10)
                    if thd > 0.1:
                        issues['distortion'] = True
                        issues['quality_score'] -= 0.3
                        
            except Exception:
                pass
                
            issues['quality_score'] = max(0.0, min(1.0, issues['quality_score']))
            
            return issues
            
        except Exception as e:
            logger.error(f"Audio quality analysis failed: {e}")
            return {'quality_score': 0.5}
            
    def apply_audio_filters(self, audio_data: np.ndarray, sample_rate: int, filter_type: str = "speech") -> np.ndarray:
        """Apply various audio filters for different purposes."""
        try:
            if filter_type == "speech":
                return self.enhance_speech_quality(audio_data, sample_rate)
                
            elif filter_type == "denoise":
                return self.reduce_noise_spectral_subtraction(audio_data, sample_rate)
                
            elif filter_type == "normalize":
                return self.normalize_audio(audio_data, method="peak")
                
            elif filter_type == "highpass":
                nyquist = sample_rate / 2
                cutoff = 80 / nyquist
                b, a = butter(4, cutoff, btype='high')
                return filtfilt(b, a, audio_data)
                
            elif filter_type == "lowpass":
                nyquist = sample_rate / 2
                cutoff = 8000 / nyquist
                b, a = butter(4, cutoff, btype='low')
                return filtfilt(b, a, audio_data)
                
            else:
                return audio_data
                
        except Exception as e:
            logger.error(f"Audio filtering failed: {e}")
            return audio_data
            
    def segment_audio_by_silence(self, audio_data: np.ndarray, sample_rate: int, silence_threshold: float = 0.01, min_silence_duration: float = 0.5) -> List[Tuple[float, float]]:
        """Segment audio by detecting silence periods."""
        try:
            window_size = int(0.1 * sample_rate)
            hop_size = int(0.05 * sample_rate)
            
            energy = []
            for i in range(0, len(audio_data) - window_size, hop_size):
                window = audio_data[i:i + window_size]
                rms = np.sqrt(np.mean(window ** 2))
                energy.append(rms)
                
            energy = np.array(energy)
            
            is_silence = energy < silence_threshold
            
            segments = []
            in_speech = False
            speech_start = 0
            
            for i, silent in enumerate(is_silence):
                time_pos = i * hop_size / sample_rate
                
                if not silent and not in_speech:
                    speech_start = time_pos
                    in_speech = True
                elif silent and in_speech:
                    silence_start = i
                    silence_duration = 0
                    
                    for j in range(i, min(len(is_silence), i + int(min_silence_duration / (hop_size / sample_rate)))):
                        if not is_silence[j]:
                            break
                        silence_duration = (j - silence_start) * hop_size / sample_rate
                        
                    if silence_duration >= min_silence_duration:
                        segments.append((speech_start, time_pos))
                        in_speech = False
                        
            if in_speech:
                segments.append((speech_start, len(audio_data) / sample_rate))
                
            return segments
            
        except Exception as e:
            logger.error(f"Audio segmentation failed: {e}")
            return [(0.0, len(audio_data) / sample_rate)]


advanced_audio_processor = AdvancedAudioProcessor()