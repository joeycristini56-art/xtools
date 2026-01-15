from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from database.models import APIKey, APIUsage
from datetime import datetime, timedelta
import secrets
import string
from typing import List, Optional

class APIKeyService:
    @staticmethod
    def generate_api_key() -> str:
        """Generate a secure API key."""
        alphabet = string.ascii_letters + string.digits
        return 'xorn_' + ''.join(secrets.choice(alphabet) for _ in range(32))
    
    @staticmethod
    async def create_api_key(
        db: AsyncSession,
        name: str,
        description: str = None,
        rate_limit: int = 1000
    ) -> APIKey:
        """Create a new API key."""
        api_key = APIKey(
            api_key=APIKeyService.generate_api_key(),
            name=name,
            description=description,
            rate_limit=rate_limit
        )
        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)
        return api_key
    
    @staticmethod
    async def get_api_key(db: AsyncSession, api_key: str) -> Optional[APIKey]:
        """Get API key by key value."""
        result = await db.execute(
            select(APIKey).where(
                and_(APIKey.api_key == api_key, APIKey.is_active == True)
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_all_api_keys(db: AsyncSession) -> List[APIKey]:
        """Get all API keys."""
        result = await db.execute(select(APIKey).order_by(APIKey.created_at.desc()))
        return result.scalars().all()
    
    @staticmethod
    async def update_api_key_usage(
        db: AsyncSession,
        api_key_id: int,
        endpoint: str,
        method: str,
        ip_address: str = None,
        user_agent: str = None,
        response_status: int = None,
        response_time: float = None,
        captcha_type: str = None,
        task_id: str = None
    ):
        """Log API key usage."""
        try:
            await db.execute(
                update(APIKey)
                .where(APIKey.id == api_key_id)
                .values(
                    last_used=datetime.utcnow(),
                    usage_count=APIKey.usage_count + 1
                )
            )
            
            usage_log = APIUsage(
                api_key_id=api_key_id,
                endpoint=endpoint,
                method=method,
                ip_address=ip_address,
                user_agent=user_agent,
                response_status=response_status,
                response_time=response_time,
                captcha_type=captcha_type,
                task_id=task_id
            )
            db.add(usage_log)
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise e
    
    @staticmethod
    async def check_rate_limit(db: AsyncSession, api_key_id: int) -> bool:
        """Check if API key is within rate limit."""
        from sqlalchemy import func
        
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        
        api_key_result = await db.execute(
            select(APIKey.rate_limit).where(APIKey.id == api_key_id)
        )
        rate_limit = api_key_result.scalar_one()
        
        usage_count_result = await db.execute(
            select(func.count(APIUsage.id)).where(
                and_(
                    APIUsage.api_key_id == api_key_id,
                    APIUsage.timestamp >= one_hour_ago
                )
            )
        )
        usage_count = usage_count_result.scalar()
        
        return usage_count < rate_limit
    
    @staticmethod
    async def deactivate_api_key(db: AsyncSession, key_id: str) -> bool:
        """Deactivate an API key."""
        result = await db.execute(
            update(APIKey)
            .where(APIKey.key_id == key_id)
            .values(is_active=False)
        )
        await db.commit()
        return result.rowcount > 0
    
    @staticmethod
    async def get_usage_stats(db: AsyncSession, api_key_id: int = None) -> dict:
        """Get usage statistics."""
        if api_key_id:
            usage_result = await db.execute(
                select(APIUsage).where(APIUsage.api_key_id == api_key_id)
            )
            usage_logs = usage_result.scalars().all()
        else:
            usage_result = await db.execute(select(APIUsage))
            usage_logs = usage_result.scalars().all()
        
        total_requests = len(usage_logs)
        successful_requests = len([log for log in usage_logs if log.response_status == 200])
        
        captcha_stats = {}
        for log in usage_logs:
            if log.captcha_type:
                captcha_stats[log.captcha_type] = captcha_stats.get(log.captcha_type, 0) + 1
        
        response_times = [log.response_time for log in usage_logs if log.response_time is not None]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        unique_ips = set(log.ip_address for log in usage_logs if log.ip_address)
        
        return {
            'total_requests': total_requests,
            'successful_requests': successful_requests,
            'success_rate': (successful_requests / total_requests * 100) if total_requests > 0 else 0,
            'captcha_type_stats': captcha_stats,
            'avg_response_time': avg_response_time,
            'unique_users': len(unique_ips)
        }
    
    @staticmethod
    async def get_real_time_stats(db: AsyncSession) -> dict:
        """Get real-time statistics for the last hour."""
        from datetime import datetime, timedelta
        
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        
        recent_usage_result = await db.execute(
            select(APIUsage).where(APIUsage.timestamp >= one_hour_ago)
        )
        recent_logs = recent_usage_result.scalars().all()
        
        active_keys_result = await db.execute(
            select(APIKey).where(APIKey.last_used >= one_hour_ago)
        )
        active_keys = active_keys_result.scalars().all()
        
        hourly_requests = len(recent_logs)
        hourly_successful = len([log for log in recent_logs if log.response_status == 200])
        hourly_success_rate = (hourly_successful / hourly_requests * 100) if hourly_requests > 0 else 0
        
        requests_per_minute = {}
        for log in recent_logs:
            minute_key = log.timestamp.strftime('%H:%M')
            requests_per_minute[minute_key] = requests_per_minute.get(minute_key, 0) + 1
        
        return {
            'hourly_requests': hourly_requests,
            'hourly_success_rate': hourly_success_rate,
            'active_api_keys': len(active_keys),
            'requests_per_minute': requests_per_minute,
            'active_users': len(set(log.ip_address for log in recent_logs if log.ip_address))
        }
    
    @staticmethod
    async def get_user_activity_stats(db: AsyncSession) -> dict:
        """Get user activity statistics."""
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        one_day_ago = now - timedelta(days=1)
        one_week_ago = now - timedelta(weeks=1)
        
        hour_users_result = await db.execute(
            select(APIUsage.ip_address).where(
                and_(APIUsage.timestamp >= one_hour_ago, APIUsage.ip_address.isnot(None))
            ).distinct()
        )
        hour_users = len(hour_users_result.scalars().all())
        
        day_users_result = await db.execute(
            select(APIUsage.ip_address).where(
                and_(APIUsage.timestamp >= one_day_ago, APIUsage.ip_address.isnot(None))
            ).distinct()
        )
        day_users = len(day_users_result.scalars().all())
        
        week_users_result = await db.execute(
            select(APIUsage.ip_address).where(
                and_(APIUsage.timestamp >= one_week_ago, APIUsage.ip_address.isnot(None))
            ).distinct()
        )
        week_users = len(week_users_result.scalars().all())
        
        return {
            'active_users_hour': hour_users,
            'active_users_day': day_users,
            'active_users_week': week_users
        }

    @staticmethod
    async def toggle_api_key(db: AsyncSession, key_id: str) -> bool:
        """Toggle API key active status."""
        result = await db.execute(
            select(APIKey.is_active).where(APIKey.key_id == key_id)
        )
        current_status = result.scalar_one_or_none()
        
        if current_status is None:
            return False
        
        new_status = not current_status
        result = await db.execute(
            update(APIKey)
            .where(APIKey.key_id == key_id)
            .values(is_active=new_status)
        )
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def delete_api_key(db: AsyncSession, key_id: str) -> bool:
        """Delete an API key."""
        from sqlalchemy import delete
        result = await db.execute(
            delete(APIKey).where(APIKey.key_id == key_id)
        )
        await db.commit()
        return result.rowcount > 0
