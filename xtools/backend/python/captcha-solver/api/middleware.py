import time
from sqlalchemy.ext.asyncio import AsyncSession
from database.database import get_async_db
from database.api_key_service import APIKeyService
from typing import Callable
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from config import get_settings
from core.rate_limiter import rate_limiter
from utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if (request.url.path.startswith("/static/") or 
            request.url.path in ["/health", "/metrics", "/", "/docs", "/redoc", "/openapi.json"]):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        is_allowed = await rate_limiter.is_allowed(client_ip)

        if not is_allowed:
            logger.warning(f"Rate limit exceeded for client {client_ip}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Limit: {settings.rate_limit_requests} requests per minute",
                    "retry_after": 60
                }
            )

        response = await call_next(request)


        return response


class AuthMiddleware(BaseHTTPMiddleware):
    """API key authentication middleware."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        public_paths = ["/", "/health", "/metrics", "/docs", "/redoc", "/openapi.json", "/metrics/prometheus", "/metrics/prometheus/login", "/metrics/prometheus/dashboard", "/metrics/prometheus/data", "/xorn/admin", "/xorn/admin/login", "/xorn/admin/dashboard", "/xorn/admin/logout", "/xorn/admin/api-keys/create", "/xorn/admin/api-keys", "/xorn/admin/api-keys/create", "/xorn/admin/api-keys/*/deactivate", "/xorn/admin/api-keys/*/stats"]
        if request.url.path.startswith("/static/") or request.url.path in public_paths or request.url.path.startswith("/xorn/admin"):
            return await call_next(request)

        api_key = None

        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            api_key = auth_header[7:]

        if not api_key:
            api_key = request.headers.get("X-API-Key")

        if not api_key:
            api_key = request.query_params.get("api_key")

        if not api_key:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Authentication required",
                    "message": "API key is required. Provide it via Authorization header, X-API-Key header, or api_key query parameter."
                }
            )

        try:
            from database.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                api_key_obj = await APIKeyService.get_api_key(db, api_key)
                
                if not api_key_obj:
                    logger.warning(f"Invalid API key attempt from {request.client.host if request.client else 'unknown'}")
                    return JSONResponse(
                        status_code=401,
                        content={
                            "error": "Invalid API key",
                            "message": "The provided API key is invalid or inactive."
                        }
                    )
                
                if not await APIKeyService.check_rate_limit(db, api_key_obj.id):
                    logger.warning(f"Rate limit exceeded for API key {api_key_obj.key_id}")
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": "Rate limit exceeded",
                            "message": f"API key rate limit of {api_key_obj.rate_limit} requests per hour exceeded."
                        }
                    )
                
                request.state.api_key = api_key
                request.state.api_key_obj = api_key_obj
                        
        except Exception as e:
            logger.error(f"Error validating API key: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Authentication error",
                    "message": "Unable to validate API key. Please try again."
                }
            )

        start_time = time.time()
        response = await call_next(request)
        response_time = (time.time() - start_time) * 1000
        
        if hasattr(request.state, 'api_key_obj'):
            try:
                from database.database import AsyncSessionLocal
                async with AsyncSessionLocal() as db:
                    client_ip = request.client.host if request.client else "unknown"
                    user_agent = request.headers.get("user-agent", "")
                    
                    captcha_type = None
                    if hasattr(request.state, 'captcha_type'):
                        captcha_type = request.state.captcha_type
                    
                    task_id = None
                    if hasattr(request.state, 'task_id'):
                        task_id = request.state.task_id
                    
                    await APIKeyService.update_api_key_usage(
                        db=db,
                        api_key_id=request.state.api_key_obj.id,
                        endpoint=request.url.path,
                        method=request.method,
                        ip_address=client_ip,
                        user_agent=user_agent,
                        response_status=response.status_code,
                        response_time=response_time,
                        captcha_type=captcha_type,
                        task_id=task_id
                    )
            except Exception as e:
                logger.error(f"Error recording API usage: {e}")
        
        return response
