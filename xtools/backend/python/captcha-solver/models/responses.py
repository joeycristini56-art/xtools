from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from pydantic import Field
from .base import BaseModel, TaskStatus, CaptchaType


class CaptchaTaskResponse(BaseModel):
    """CAPTCHA task creation response."""
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    message: str = "Task created successfully"
    estimated_time: Optional[int] = Field(default=None, description="Estimated completion time in seconds")


class TaskSolution(BaseModel):
    """Base solution model."""
    solution_type: str
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    processing_time: Optional[float] = Field(default=None, description="Processing time in seconds")


class TextSolution(TaskSolution):
    """Text CAPTCHA solution."""
    solution_type: str = "text"
    text: str
    case_sensitive: bool = False


class ImageGridSolution(TaskSolution):
    """Image grid CAPTCHA solution."""
    solution_type: str = "image_grid"
    selected_indices: List[int] = Field(..., description="Indices of selected grid items")
    grid_size: str = "3x3"


class AudioSolution(TaskSolution):
    """Audio CAPTCHA solution."""
    solution_type: str = "audio"
    transcription: str
    language: str = "en"


class TokenSolution(TaskSolution):
    """Token-based solution (reCAPTCHA, Turnstile, DataDome, etc.)."""
    solution_type: str = "token"
    token: str
    expires_at: Optional[datetime] = None
    cookies: Optional[Dict[str, str]] = Field(default=None, description="Additional cookies returned with the solution")


class RotationSolution(TaskSolution):
    """Image rotation solution."""
    solution_type: str = "rotation"
    rotation_angle: int = Field(..., description="Rotation angle in degrees")


class DiceSolution(TaskSolution):
    """Dice selection solution."""
    solution_type: str = "dice"
    selected_dice: List[int] = Field(..., description="Indices of selected dice")
    total_sum: int


class MathSolution(TaskSolution):
    """Math CAPTCHA solution."""
    solution_type: str = "math"
    answer: Union[str, int, float]
    expression: Optional[str] = None


class SliderSolution(TaskSolution):
    """Slider CAPTCHA solution."""
    solution_type: str = "slider"
    slider_position: float = Field(..., description="Slider position as percentage (0-100)")
    puzzle_offset_x: int = Field(..., description="X offset of puzzle piece")
    puzzle_offset_y: int = Field(..., description="Y offset of puzzle piece")
    drag_distance: float = Field(..., description="Distance to drag the slider")


class ObjectIdentificationSolution(TaskSolution):
    """Advanced object identification solution."""
    solution_type: str = "object_identification"
    task_type: str = Field(..., description="Type of task: select, identify, count")
    selected_indices: Optional[List[int]] = Field(default=None, description="Indices of selected images (for selection tasks)")
    identified_objects: Optional[List[Dict[str, Any]]] = Field(
        default=None, 
        description="List of identified objects with details and confidence"
    )
    object_counts: Optional[Dict[str, int]] = Field(default=None, description="Object counts (for counting tasks)")
    total_images: int = Field(..., description="Total number of images analyzed")


class TaskResultResponse(BaseModel):
    """Task result response."""
    task_id: str
    status: TaskStatus
    captcha_type: Optional[CaptchaType] = None
    solution: Optional[Union[
        TokenSolution,
        TextSolution,
        ImageGridSolution,
        AudioSolution,
        RotationSolution,
        DiceSolution,
        SliderSolution,
        ObjectIdentificationSolution,
        TaskSolution
    ]] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    processing_time: Optional[float] = None
    attempts: int = 0
    
    class Config:
        use_enum_values = True


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str
    uptime: float
    active_tasks: int
    total_completed: int
    total_failed: int
    system_info: Dict[str, Any]


class StatsResponse(BaseModel):
    """Statistics response."""
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    pending_tasks: int
    processing_tasks: int
    average_processing_time: float
    success_rate: float
    captcha_type_stats: Dict[str, Dict[str, int]]