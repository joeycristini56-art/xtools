import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.utils import get_openapi
import time
import psutil
import os
from typing import Optional

from config import get_settings
from utils.logger import setup_logging, get_logger
from utils.cache_utils import cache_manager
from core.task_manager import task_manager
from core.solver_factory import solver_factory, register_all_solvers
from core.rate_limiter import rate_limiter
from api.routes import router
from api.middleware import RateLimitMiddleware, AuthMiddleware
from api.admin_routes import router as admin_router
from database.database import create_tables

settings = get_settings()
logger = get_logger(__name__)

prometheus_sessions = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting XorthonL CAPTCHA Solver API")

    try:
        setup_logging(
            level=settings.log_level,
            format_type=settings.log_format,
            log_file=settings.log_file
        )

        await cache_manager.connect()

        await rate_limiter.start()
        await create_tables()

        await register_all_solvers()
        await solver_factory.initialize_all_solvers()

        await task_manager.start_workers()

        logger.info("XorthonL API startup completed successfully")

    except Exception as e:
        logger.error(f"Failed to start XorthonL API: {e}")
        raise

    yield

    logger.info("Shutting down XorthonL CAPTCHA Solver API")
    try:
        await task_manager.stop_workers()
        await rate_limiter.stop()
        await cache_manager.disconnect()
        logger.info("XorthonL API shutdown completed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


app = FastAPI(lifespan=lifespan)
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=settings.api_title,
        version=settings.api_version,
        description=settings.api_description,
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "Enter your API key"
        }
    }
    for path in openapi_schema["paths"]:
        if path.startswith("/api/v1/"):
            for method in openapi_schema["paths"][path]:
                if method in ["get", "post", "put", "delete", "patch"]:
                    openapi_schema["paths"][path][method]["security"] = [{"ApiKeyAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)

app.include_router(router, prefix="/api/v1", tags=["CAPTCHA Solving"])


app.include_router(admin_router, prefix="/xorn", tags=["Admin"])
def format_uptime(seconds):
    """Format uptime in a human-readable format."""
    if not seconds:
        return "0s"

    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)

    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def check_prometheus_session(request: Request) -> bool:
    """Check if user has valid prometheus session."""
    session_id = request.cookies.get("prometheus_session")
    return session_id in prometheus_sessions


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root endpoint with API information."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "name": settings.api_title,
        "version": settings.api_version,
        "description": settings.api_description,
        "status": "running",
        "docs_url": "/docs",
        "health_check": "/health"
    })


@app.get("/api")
async def api_root():
    """API root endpoint with JSON information."""
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "description": settings.api_description,
        "status": "running",
        "docs_url": "/docs",
        "health_check": "/health"
    }


@app.get("/health", response_class=HTMLResponse)
async def health_check_page(request: Request):
    """Health check page with dashboard."""
    try:
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()

        task_stats = await task_manager.get_task_stats()

        solver_stats = solver_factory.get_solver_stats()

        uptime = time.time() - process.create_time()

        health_data = {
            "status": "healthy",
            "version": settings.api_version,
            "uptime": uptime,
            "uptime_formatted": format_uptime(uptime),
            "system_info": {
                "cpu_percent": psutil.cpu_percent(),
                "memory_usage_mb": memory_info.rss / 1024 / 1024,
                "memory_percent": process.memory_percent(),
                "disk_usage": {
                    "total": psutil.disk_usage('/').total,
                    "used": psutil.disk_usage('/').used,
                    "free": psutil.disk_usage('/').free
                }
            },
            "task_stats": task_stats,
            "solver_stats": solver_stats,
            "performance_metrics": {
                "avg_response_time": 0.0,
                "p95_response_time": 0.0,
                "success_rate": 0.95,
                "hourly_success_rate": 0.98
            }
        }

        return templates.TemplateResponse("health.html", {
            "request": request,
            **health_data
        })

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return templates.TemplateResponse("health.html", {
            "request": request,
            "status": "error",
            "version": settings.api_version,
            "uptime": 0,
            "uptime_formatted": "0s",
            "system_info": {
                "cpu_percent": 0,
                "memory_usage_mb": 0,
                "memory_percent": 0,
                "disk_usage": {"total": 0, "used": 0, "free": 0}
            },
            "task_stats": {},
            "solver_stats": {},
            "performance_metrics": {
                "avg_response_time": 0.0,
                "p95_response_time": 0.0,
                "success_rate": 0.0,
                "hourly_success_rate": 0.0
            }
        })


@app.get("/health/api")
async def health_check_api():
    """Health check API endpoint (JSON)."""
    try:
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()

        task_stats = await task_manager.get_task_stats()

        solver_stats = solver_factory.get_solver_stats()

        return {
            "status": "healthy",
            "version": settings.api_version,
            "uptime": time.time() - process.create_time(),
            "system_info": {
                "cpu_percent": psutil.cpu_percent(),
                "memory_usage_mb": memory_info.rss / 1024 / 1024,
                "memory_percent": process.memory_percent(),
                "disk_usage": {
                    "total": psutil.disk_usage('/').total,
                    "used": psutil.disk_usage('/').used,
                    "free": psutil.disk_usage('/').free
                }
            },
            "task_stats": task_stats,
            "solver_stats": solver_stats
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail="Health check failed")


@app.get("/metrics", response_class=HTMLResponse)
async def metrics_dashboard(request: Request):
    """Metrics dashboard with beautiful UI."""
    try:
        task_stats = await task_manager.get_task_stats()

        solver_stats = solver_factory.get_solver_stats()

        cache_stats = await cache_manager.get_cache_stats()

        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        disk_usage = psutil.disk_usage('/')

        metrics_data = {
            "task_metrics": task_stats,
            "solver_metrics": solver_stats,
            "cache_metrics": cache_stats,
            "system_metrics": {
                "memory_usage_mb": memory_info.rss / 1024 / 1024,
                "cpu_percent": psutil.cpu_percent(),
                "disk_used_gb": disk_usage.used / (1024**3),
                "disk_total_gb": disk_usage.total / (1024**3)
            }
        }

        return templates.TemplateResponse("metrics.html", {
            "request": request,
            **metrics_data
        })

    except Exception as e:
        logger.error(f"Metrics dashboard failed: {e}")
        return templates.TemplateResponse("metrics.html", {
            "request": request,
            "task_metrics": {},
            "solver_metrics": {},
            "cache_metrics": {},
            "system_metrics": {
                "memory_usage_mb": 0,
                "cpu_percent": 0,
                "disk_used_gb": 0,
                "disk_total_gb": 0
            }
        })


@app.get("/metrics/prometheus", response_class=HTMLResponse)
async def prometheus_login_page(request: Request, error: Optional[str] = None):
    """Prometheus metrics login page."""
    if check_prometheus_session(request):
        return RedirectResponse(url="/metrics/prometheus/dashboard", status_code=302)
    
    return templates.TemplateResponse("prometheus_login.html", {
        "request": request,
        "error": error
    })


@app.post("/metrics/prometheus/login")
async def prometheus_login(request: Request, password: str = Form(...)):
    """Handle prometheus login."""
    if password == getattr(settings, 'api_key', '$&$Hello13$&$'):
        session_id = f"prometheus_{int(time.time())}_{hash(request.client.host)}"
        prometheus_sessions.add(session_id)
        
        response = RedirectResponse(url="/metrics/prometheus/dashboard", status_code=302)
        response.set_cookie(
            key="prometheus_session",
            value=session_id,
            max_age=3600,
            httponly=True,
            secure=False
        )
        return response
    else:
        return templates.TemplateResponse("prometheus_login.html", {
            "request": request,
            "error": "Invalid password. Please try again."
        })


@app.get("/metrics/prometheus/dashboard", response_class=HTMLResponse)
async def prometheus_dashboard(request: Request):
    """Prometheus metrics dashboard."""
    if not check_prometheus_session(request):
        return RedirectResponse(url="/metrics/prometheus?error=Session expired. Please login again.", status_code=302)
    
    return templates.TemplateResponse("prometheus_dashboard.html", {
        "request": request
    })


@app.get("/metrics/prometheus/data", response_class=PlainTextResponse)
async def prometheus_data(request: Request):
    """Get prometheus metrics data (requires authentication)."""
    if not check_prometheus_session(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        task_stats = await task_manager.get_task_stats()
        solver_stats = solver_factory.get_solver_stats()
        cache_stats = await cache_manager.get_cache_stats()

        metrics_data = []

        metrics_data.append(f"# HELP xorthonl_tasks_active Number of active tasks")
        metrics_data.append(f"# TYPE xorthonl_tasks_active gauge")
        metrics_data.append(f"xorthonl_tasks_active {task_stats.get('active', 0)}")

        metrics_data.append(f"# HELP xorthonl_tasks_completed Number of completed tasks")
        metrics_data.append(f"# TYPE xorthonl_tasks_completed counter")
        metrics_data.append(f"xorthonl_tasks_completed {task_stats.get('completed', 0)}")

        metrics_data.append(f"# HELP xorthonl_tasks_failed Number of failed tasks")
        metrics_data.append(f"# TYPE xorthonl_tasks_failed counter")
        metrics_data.append(f"xorthonl_tasks_failed {task_stats.get('failed', 0)}")

        metrics_data.append(f"# HELP xorthonl_solvers_available Number of available solvers")
        metrics_data.append(f"# TYPE xorthonl_solvers_available gauge")
        metrics_data.append(f"xorthonl_solvers_available {solver_stats.get('available', 0)}")

        metrics_data.append(f"# HELP xorthonl_solvers_total Total number of solvers")
        metrics_data.append(f"# TYPE xorthonl_solvers_total gauge")
        metrics_data.append(f"xorthonl_solvers_total {solver_stats.get('total', 0)}")

        if cache_stats:
            metrics_data.append(f"# HELP xorthonl_cache_hits Number of cache hits")
            metrics_data.append(f"# TYPE xorthonl_cache_hits counter")
            metrics_data.append(f"xorthonl_cache_hits {cache_stats.get('hits', 0)}")

            metrics_data.append(f"# HELP xorthonl_cache_misses Number of cache misses")
            metrics_data.append(f"# TYPE xorthonl_cache_misses counter")
            metrics_data.append(f"xorthonl_cache_misses {cache_stats.get('misses', 0)}")

        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()

        metrics_data.append(f"# HELP xorthonl_memory_usage_bytes Memory usage in bytes")
        metrics_data.append(f"# TYPE xorthonl_memory_usage_bytes gauge")
        metrics_data.append(f"xorthonl_memory_usage_bytes {memory_info.rss}")

        metrics_data.append(f"# HELP xorthonl_cpu_usage_percent CPU usage percentage")
        metrics_data.append(f"# TYPE xorthonl_cpu_usage_percent gauge")
        metrics_data.append(f"xorthonl_cpu_usage_percent {psutil.cpu_percent()}")

        return "\n".join(metrics_data)

    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")
        raise HTTPException(status_code=500, detail="Metrics collection failed")


@app.get("/metrics/prometheus/logout")
async def prometheus_logout(request: Request):
    """Logout from prometheus dashboard."""
    session_id = request.cookies.get("prometheus_session")
    if session_id and session_id in prometheus_sessions:
        prometheus_sessions.remove(session_id)
    
    response = RedirectResponse(url="/metrics/prometheus", status_code=302)
    response.delete_cookie("prometheus_session")
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": time.time(),
            "path": str(request.url)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.log_level == "DEBUG" else "An unexpected error occurred",
            "status_code": 500,
            "timestamp": time.time(),
            "path": str(request.url)
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "xorthonl.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        reload=False,
        access_log=True,
        log_level=settings.log_level.lower()
    )