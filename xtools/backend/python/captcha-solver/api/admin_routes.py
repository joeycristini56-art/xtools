from fastapi import APIRouter, HTTPException, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from database.database import get_async_db
from database.api_key_service import APIKeyService
from session_manager import session_manager
from typing import Optional
import os
import time

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def check_admin_auth(request: Request):
    """Check if user is authenticated as admin."""
    session_id = request.cookies.get("admin_session")
    if not session_id or not session_manager.is_valid_session(session_id):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return True

@router.get("/admin", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Admin login page."""
    session_id = request.cookies.get("admin_session")
    if session_id and session_manager.is_valid_session(session_id):
        return RedirectResponse(url="/xorn/admin/dashboard", status_code=302)

    return templates.TemplateResponse("admin_login.html", {"request": request})

@router.post("/admin/login")
async def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    """Handle admin login."""
    print(f"DEBUG: Received username: {username}, password: {password}")
    if username == "root" and password == "bdgadmin245":
        import secrets
        session_id = secrets.token_urlsafe(32)
        session_manager.add_session(session_id, 86400)

        response = RedirectResponse(url="/xorn/admin/dashboard", status_code=302)
        response.set_cookie("admin_session", session_id, httponly=True, max_age=86400)
        return response
    else:
        return templates.TemplateResponse("admin_login.html", {
            "request": request,
            "error": "Invalid credentials"
        })

@router.get("/admin/logout")
async def admin_logout(request: Request):
    """Handle admin logout."""
    session_id = request.cookies.get("admin_session")
    if session_id:
        session_manager.remove_session(session_id)

    response = RedirectResponse(url="/xorn/admin", status_code=302)
    response.delete_cookie("admin_session")
    return response

@router.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    _: bool = Depends(check_admin_auth)
):
    """Admin dashboard."""
    api_keys = await APIKeyService.get_all_api_keys(db)

    usage_stats = await APIKeyService.get_usage_stats(db)
    
    try:
        real_time_stats = await APIKeyService.get_real_time_stats(db)
        user_activity = await APIKeyService.get_user_activity_stats(db)
    except Exception as e:
        real_time_stats = {
            'hourly_requests': 0,
            'hourly_success_rate': 0,
            'active_api_keys': 0,
            'active_users': 0
        }
        user_activity = {
            'active_users_hour': 0,
            'active_users_day': 0,
            'active_users_week': 0
        }

    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "api_keys": api_keys,
        "usage_stats": usage_stats,
        "real_time_stats": real_time_stats,
        "user_activity": user_activity
    })

@router.post("/admin/api-keys/create")
async def create_api_key(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    rate_limit: int = Form(1000),
    db: AsyncSession = Depends(get_async_db),
    _: bool = Depends(check_admin_auth)
):
    """Create a new API key."""
    try:
        api_key = await APIKeyService.create_api_key(
            db=db,
            name=name,
            description=description,
            rate_limit=rate_limit
        )
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "api_key": api_key.api_key,
                "key_id": api_key.key_id,
                "name": api_key.name,
                "description": api_key.description,
                "rate_limit": api_key.rate_limit,
                "created_at": api_key.created_at.isoformat() if api_key.created_at else None
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": str(e)}
        )

@router.get("/admin/api-keys")
async def get_api_keys(
    db: AsyncSession = Depends(get_async_db),
    _: bool = Depends(check_admin_auth)
):
    """Get all API keys."""
    api_keys = await APIKeyService.get_all_api_keys(db)
    return {"api_keys": api_keys}

@router.post("/admin/api-keys/{key_id}/deactivate")
async def deactivate_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_async_db),
    _: bool = Depends(check_admin_auth)
):
    """Deactivate an API key."""
    try:
        success = await APIKeyService.deactivate_api_key(db, key_id)
        if success:
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": "API key deactivated successfully"}
            )
        else:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "API key not found"}
            )
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": str(e)}
        )

@router.get("/admin/api-keys/{key_id}/stats")
async def get_api_key_stats(
    key_id: str,
    db: AsyncSession = Depends(get_async_db),
    _: bool = Depends(check_admin_auth)
):
    """Get statistics for a specific API key."""
    try:
        from sqlalchemy import select
        from database.models import APIKey
        
        result = await db.execute(
            select(APIKey).where(APIKey.key_id == key_id)
        )
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "API key not found"}
            )
        
        stats = await APIKeyService.get_usage_stats(db, api_key.id)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "total_requests": stats["total_requests"],
                "successful_requests": stats["successful_requests"],
                "success_rate": stats["success_rate"],
                "captcha_type_stats": stats["captcha_type_stats"]
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": str(e)}
        )

@router.post("/admin/api-keys/{key_id}/toggle")
async def toggle_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_async_db),
    _: bool = Depends(check_admin_auth)
):
    """Toggle API key active status."""
    try:
        await APIKeyService.toggle_api_key(db, key_id)
        return RedirectResponse(url="/xorn/admin/dashboard", status_code=302)
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": str(e)}
        )

@router.delete("/admin/api-keys/{key_id}")
async def delete_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_async_db),
    _: bool = Depends(check_admin_auth)
):
    """Delete an API key."""
    try:
        await APIKeyService.delete_api_key(db, key_id)
        return {"message": "API key deleted successfully"}
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": str(e)}
        )

@router.get("/admin/stats/realtime")
async def get_realtime_stats(
    db: AsyncSession = Depends(get_async_db),
    _: bool = Depends(check_admin_auth)
):
    """Get real-time API usage statistics."""
    try:
        real_time_stats = await APIKeyService.get_real_time_stats(db)
        overall_stats = await APIKeyService.get_usage_stats(db)
        user_activity = await APIKeyService.get_user_activity_stats(db)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "real_time": real_time_stats,
                "overall": overall_stats,
                "user_activity": user_activity
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": str(e)}
        )

@router.get("/admin/stats/dashboard")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_async_db),
    _: bool = Depends(check_admin_auth)
):
    """Get comprehensive dashboard statistics."""
    try:
        api_keys = await APIKeyService.get_all_api_keys(db)
        
        usage_stats = await APIKeyService.get_usage_stats(db)
        
        real_time_stats = await APIKeyService.get_real_time_stats(db)
        
        user_activity = await APIKeyService.get_user_activity_stats(db)
        
        active_keys = len([key for key in api_keys if key.is_active])
        total_keys = len(api_keys)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "api_keys": {
                    "total": total_keys,
                    "active": active_keys,
                    "inactive": total_keys - active_keys
                },
                "usage": usage_stats,
                "real_time": real_time_stats,
                "user_activity": user_activity,
                "timestamp": time.time()
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": str(e)}
        )
