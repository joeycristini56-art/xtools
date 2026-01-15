from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel as PydanticBaseModel, Field
from datetime import datetime
import uuid


class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class CaptchaType(str, Enum):
    """Supported CAPTCHA types."""
    TEXT = "text"
    IMAGE_GRID = "image_grid"
    IMAGE_ROTATION = "image_rotation"
    SLIDER_CAPTCHA = "slider_captcha"
    AUDIO = "audio"
    RECAPTCHA_V2 = "recaptcha_v2"
    RECAPTCHA_V3 = "recaptcha_v3"
    TURNSTILE = "turnstile"
    ARKOSE = "arkose"
    FUNCAPTCHA = "funcaptcha"
    DICE_SELECTION = "dice_selection"
    MATH_CAPTCHA = "math_captcha"
    OBJECT_IDENTIFICATION = "object_identification"
    DATADOME = "datadome"


class BaseModel(PydanticBaseModel):
    """Base model with common functionality."""
    
    class Config:
        use_enum_values = True
        validate_assignment = True
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }
    
    def dict_exclude_none(self) -> Dict[str, Any]:
        """Return dictionary representation excluding None values."""
        return self.model_dump(exclude_none=True)


class TaskMetadata(BaseModel):
    """Task metadata for tracking and debugging."""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    attempts: int = Field(default=0)
    max_attempts: int = Field(default=3)
    timeout_seconds: int = Field(default=120)
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None