from typing import Optional, Dict, Any, List
from pydantic import Field, HttpUrl, validator
from .base import BaseModel, CaptchaType


class CaptchaTaskRequest(BaseModel):
    """Base CAPTCHA task request."""
    captcha_type: CaptchaType
    website_url: HttpUrl
    additional_data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    proxy: Optional[str] = None
    timeout: Optional[int] = Field(default=120, ge=10, le=300)


class TaskResultRequest(BaseModel):
    """Request to get task result."""
    task_id: str = Field(..., min_length=1)


class TextCaptchaRequest(CaptchaTaskRequest):
    """Text-based CAPTCHA request."""
    captcha_type: CaptchaType = CaptchaType.TEXT
    image_data: str = Field(..., description="Base64 encoded image data")
    case_sensitive: bool = Field(default=False)
    min_length: Optional[int] = Field(default=None, ge=1)
    max_length: Optional[int] = Field(default=None, ge=1)
    
    @validator('max_length')
    def validate_length_range(cls, v, values):
        if v is not None and 'min_length' in values and values['min_length'] is not None:
            if v < values['min_length']:
                raise ValueError('max_length must be greater than or equal to min_length')
        return v


class ImageCaptchaRequest(CaptchaTaskRequest):
    """Image-based CAPTCHA request."""
    captcha_type: CaptchaType = CaptchaType.IMAGE_GRID
    image_data: str = Field(..., description="Base64 encoded image data")
    instruction: str = Field(..., description="Instruction text (e.g., 'Select all images with cars')")
    grid_size: Optional[str] = Field(default="3x3", description="Grid size (e.g., '3x3', '4x4')")


class AudioCaptchaRequest(CaptchaTaskRequest):
    """Audio CAPTCHA request."""
    captcha_type: CaptchaType = CaptchaType.AUDIO
    audio_data: str = Field(..., description="Base64 encoded audio data")
    audio_format: str = Field(default="wav", description="Audio format")
    language: str = Field(default="en", description="Expected language")


class RecaptchaRequest(CaptchaTaskRequest):
    """reCAPTCHA request."""
    site_key: str = Field(..., min_length=1)
    version: str = Field(default="v2", pattern="^(v2|v3)$")
    action: Optional[str] = None
    min_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    page_action: Optional[str] = None
    
    @validator('captcha_type', pre=True, always=True)
    def set_captcha_type(cls, v, values):
        version = values.get('version', 'v2')
        return CaptchaType.RECAPTCHA_V3 if version == 'v3' else CaptchaType.RECAPTCHA_V2


class TurnstileRequest(CaptchaTaskRequest):
    """Cloudflare Turnstile request."""
    captcha_type: CaptchaType = CaptchaType.TURNSTILE
    site_key: str = Field(..., min_length=1)
    action: Optional[str] = None
    cdata: Optional[str] = None


class ArkoseRequest(CaptchaTaskRequest):
    """Arkose/FunCAPTCHA request."""
    captcha_type: CaptchaType = CaptchaType.ARKOSE
    public_key: str = Field(..., min_length=1)
    blob_data: Optional[str] = None
    subdomain: Optional[str] = None


class RotationCaptchaRequest(CaptchaTaskRequest):
    """Image rotation CAPTCHA request."""
    captcha_type: CaptchaType = CaptchaType.IMAGE_ROTATION
    image_data: str = Field(..., description="Base64 encoded image data")
    instruction: str = Field(..., description="Rotation instruction")


class DiceCaptchaRequest(CaptchaTaskRequest):
    """Dice selection CAPTCHA request."""
    captcha_type: CaptchaType = CaptchaType.DICE_SELECTION
    image_data: str = Field(..., description="Base64 encoded image data")
    target_sum: Optional[int] = Field(default=None, description="Target sum for dice")


class MathCaptchaRequest(CaptchaTaskRequest):
    """Math CAPTCHA request."""
    captcha_type: CaptchaType = CaptchaType.MATH_CAPTCHA
    image_data: Optional[str] = Field(default=None, description="Base64 encoded image data")
    math_expression: Optional[str] = Field(default=None, description="Math expression text")
    
    @validator('math_expression')
    def validate_input_data(cls, v, values):
        if not v and not values.get('image_data'):
            raise ValueError('Either math_expression or image_data must be provided')
        return v


class SliderCaptchaRequest(CaptchaTaskRequest):
    """Slider CAPTCHA request."""
    captcha_type: CaptchaType = CaptchaType.SLIDER_CAPTCHA
    image_data: str = Field(..., description="Base64 encoded background image data")
    puzzle_piece_data: str = Field(..., description="Base64 encoded puzzle piece image data")
    image_width: int = Field(..., description="Width of the background image", gt=0)
    image_height: int = Field(..., description="Height of the background image", gt=0)


class ObjectIdentificationRequest(CaptchaTaskRequest):
    """Object identification CAPTCHA request."""
    captcha_type: CaptchaType = CaptchaType.OBJECT_IDENTIFICATION
    image_data: str = Field(..., description="Base64 encoded image data")
    objects_to_identify: List[str] = Field(..., description="List of objects to identify")
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class DataDomeRequest(CaptchaTaskRequest):
    """DataDome CAPTCHA request."""
    captcha_type: CaptchaType = CaptchaType.DATADOME
    datadome_url: Optional[str] = Field(default=None, description="DataDome challenge URL (if different from website_url)")
    user_agent: Optional[str] = Field(default=None, description="Custom user agent to use")
    additional_headers: Optional[Dict[str, str]] = Field(default=None, description="Additional headers to send")