from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from typing import Dict, Any, List
import time

from models.requests import (
    CaptchaTaskRequest, TaskResultRequest, TextCaptchaRequest,
    ImageCaptchaRequest, AudioCaptchaRequest, RecaptchaRequest,
    TurnstileRequest, ArkoseRequest, SliderCaptchaRequest,
    DataDomeRequest
)
from models.responses import (
    CaptchaTaskResponse, TaskResultResponse, ErrorResponse,
    HealthResponse, StatsResponse
)
from core.task_manager import task_manager
from core.solver_factory import solver_factory
from utils.logger import get_logger
from utils.cache_utils import cache_manager

logger = get_logger(__name__)
router = APIRouter()


@router.post("/captcha/solve", response_model=CaptchaTaskResponse)
async def create_captcha_task(
    request: CaptchaTaskRequest,
    http_request: Request,
    background_tasks: BackgroundTasks
) -> CaptchaTaskResponse:
    """
    Create a new CAPTCHA solving task.
    
    This endpoint accepts various types of CAPTCHA challenges and returns a task ID
    that can be used to retrieve the solution once processing is complete.
    """
    try:
        client_ip = http_request.client.host if http_request.client else "unknown"
        user_agent = http_request.headers.get("user-agent")
        
        if not solver_factory.is_solver_available(request.captcha_type):
            raise HTTPException(
                status_code=400,
                detail=f"Solver for {request.captcha_type} is not available"
            )
        
        task_id = await task_manager.create_task(
            captcha_type=request.captcha_type,
            task_data=request.model_dump(),
            client_ip=client_ip,
            user_agent=user_agent
        )
        
        estimated_time = _get_estimated_time(request.captcha_type)
        
        logger.info(f"Created CAPTCHA task {task_id} for type {request.captcha_type}")
        
        return CaptchaTaskResponse(
            task_id=task_id,
            estimated_time=estimated_time,
            message=f"Task created successfully for {request.captcha_type} CAPTCHA"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating CAPTCHA task: {e}")
        raise HTTPException(status_code=500, detail="Failed to create CAPTCHA task")


@router.post("/captcha/text", response_model=CaptchaTaskResponse)
async def solve_text_captcha(
    request: TextCaptchaRequest,
    http_request: Request
) -> CaptchaTaskResponse:
    """Solve text-based CAPTCHA with OCR."""
    return await create_captcha_task(request, http_request, BackgroundTasks())


@router.post("/captcha/image", response_model=CaptchaTaskResponse)
async def solve_image_captcha(
    request: ImageCaptchaRequest,
    http_request: Request
) -> CaptchaTaskResponse:
    """Solve image grid CAPTCHA with computer vision."""
    return await create_captcha_task(request, http_request, BackgroundTasks())


@router.post("/captcha/audio", response_model=CaptchaTaskResponse)
async def solve_audio_captcha(
    request: AudioCaptchaRequest,
    http_request: Request
) -> CaptchaTaskResponse:
    """Solve audio CAPTCHA with speech recognition."""
    return await create_captcha_task(request, http_request, BackgroundTasks())


@router.post("/captcha/recaptcha", response_model=CaptchaTaskResponse)
async def solve_recaptcha(
    request: RecaptchaRequest,
    http_request: Request
) -> CaptchaTaskResponse:
    """Solve Google reCAPTCHA v2/v3."""
    return await create_captcha_task(request, http_request, BackgroundTasks())


@router.post("/captcha/turnstile", response_model=CaptchaTaskResponse)
async def solve_turnstile(
    request: TurnstileRequest,
    http_request: Request
) -> CaptchaTaskResponse:
    """Solve Cloudflare Turnstile CAPTCHA."""
    return await create_captcha_task(request, http_request, BackgroundTasks())


@router.post("/captcha/arkose", response_model=CaptchaTaskResponse)
async def solve_arkose(
    request: ArkoseRequest,
    http_request: Request
) -> CaptchaTaskResponse:
    """Solve Arkose/FunCAPTCHA."""
    return await create_captcha_task(request, http_request, BackgroundTasks())


@router.post("/captcha/slider", response_model=CaptchaTaskResponse)
async def solve_slider_captcha(
    request: SliderCaptchaRequest,
    http_request: Request
) -> CaptchaTaskResponse:
    """Solve slider CAPTCHA with image matching."""
    return await create_captcha_task(request, http_request, BackgroundTasks())


@router.post("/captcha/datadome", response_model=CaptchaTaskResponse)
async def solve_datadome(
    request: DataDomeRequest,
    http_request: Request
) -> CaptchaTaskResponse:
    """Solve DataDome CAPTCHA with advanced device fingerprinting."""
    return await create_captcha_task(request, http_request, BackgroundTasks())


@router.get("/task/{task_id}", response_model=TaskResultResponse)
async def get_task_result(task_id: str) -> TaskResultResponse:
    """
    Get the result of a CAPTCHA solving task.
    
    Returns the current status and solution (if completed) for the specified task ID.
    """
    try:
        result = await task_manager.get_task_result(task_id)
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail="Task not found"
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task result for {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get task result")


@router.delete("/task/{task_id}")
async def cancel_task(task_id: str) -> Dict[str, Any]:
    """Cancel a pending or processing task."""
    try:
        success = await task_manager.cancel_task(task_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Task not found or cannot be cancelled"
            )
        
        return {
            "message": f"Task {task_id} cancelled successfully",
            "task_id": task_id,
            "cancelled": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel task")


@router.get("/tasks/active")
async def get_active_tasks() -> List[Dict[str, Any]]:
    """Get list of currently active tasks."""
    try:
        active_tasks = await task_manager.get_active_tasks()
        return active_tasks
        
    except Exception as e:
        logger.error(f"Error getting active tasks: {e}")
        raise HTTPException(status_code=500, detail="Failed to get active tasks")


@router.get("/solvers")
async def get_available_solvers() -> Dict[str, Any]:
    """Get information about available CAPTCHA solvers."""
    try:
        solvers_info = solver_factory.get_all_solver_info()
        available_types = solver_factory.get_available_solvers()
        
        return {
            "available_types": available_types,
            "solvers": solvers_info,
            "total_solvers": len(solvers_info)
        }
        
    except Exception as e:
        logger.error(f"Error getting solver information: {e}")
        raise HTTPException(status_code=500, detail="Failed to get solver information")


@router.get("/solvers/{captcha_type}")
async def get_solver_info(captcha_type: str) -> Dict[str, Any]:
    """Get information about a specific solver."""
    try:
        solver_info = solver_factory.get_solver_info(captcha_type)
        
        if not solver_info:
            raise HTTPException(
                status_code=404,
                detail=f"Solver for {captcha_type} not found"
            )
        
        return solver_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting solver info for {captcha_type}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get solver information")


@router.post("/solvers/{captcha_type}/test")
async def test_solver(captcha_type: str) -> Dict[str, Any]:
    """Test a specific solver."""
    try:
        is_working = await solver_factory.test_solver(captcha_type)
        
        return {
            "captcha_type": captcha_type,
            "is_working": is_working,
            "tested_at": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error testing solver {captcha_type}: {e}")
        raise HTTPException(status_code=500, detail="Failed to test solver")


@router.get("/stats", response_model=StatsResponse)
async def get_statistics() -> StatsResponse:
    """Get API usage statistics."""
    try:
        task_stats = await task_manager.get_task_stats()
        
        total_tasks = task_stats['total_tasks']
        completed_tasks = task_stats['completed_tasks']
        processing_tasks = task_stats['processing_tasks']
        
        total_finished = completed_tasks + task_stats.get('failed_tasks', 0)
        success_rate = (completed_tasks / total_finished * 100) if total_finished > 0 else 0
        
        average_processing_time = 30.0
        
        return StatsResponse(
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=task_stats.get('failed_tasks', 0),
            pending_tasks=task_stats['active_tasks'] - processing_tasks,
            processing_tasks=processing_tasks,
            average_processing_time=average_processing_time,
            success_rate=success_rate,
            captcha_type_stats={}
        )
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")


@router.get("/cache/stats")
async def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics."""
    try:
        cache_stats = await cache_manager.get_cache_stats()
        return cache_stats
        
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cache statistics")


@router.delete("/cache/clear")
async def clear_cache() -> Dict[str, Any]:
    """Clear cache (admin operation)."""
    try:
        cleared_solutions = await cache_manager.clear_pattern("xorthonl:solution:*")
        
        cleared_models = await cache_manager.clear_pattern("xorthonl:model:*")
        
        cleared_tasks = await cache_manager.clear_pattern("xorthonl:task:*")
        
        total_cleared = cleared_solutions + cleared_models + cleared_tasks
        
        return {
            "message": "Cache cleared successfully",
            "cleared_items": {
                "solutions": cleared_solutions,
                "models": cleared_models,
                "tasks": cleared_tasks,
                "total": total_cleared
            }
        }
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")


def _get_estimated_time(captcha_type: str) -> int:
    """Get estimated completion time for different CAPTCHA types."""
    estimates = {
        "text": 8,
        "image_grid": 15,
        "audio": 12,
        "recaptcha_v2": 25,
        "recaptcha_v3": 5,
        "turnstile": 10,
        "arkose": 35,
        "funcaptcha": 35,
        "image_rotation": 18,
        "dice_selection": 15,
        "math_captcha": 8,
        "object_identification": 20,
        "datadome": 15,
        "slider_captcha": 12
    }
    
    return estimates.get(captcha_type, 25)
