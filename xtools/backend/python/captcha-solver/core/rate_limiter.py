import asyncio
import time
from typing import Dict, Optional
from collections import defaultdict, deque
from utils.logger import get_logger
from config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class RateLimiter:
    """Rate limiter for API requests with sliding window algorithm."""
    
    def __init__(self):
        self.request_history: Dict[str, deque] = defaultdict(deque)
        self.blocked_clients: Dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._started = False
    
    async def start(self) -> None:
        """Start the rate limiter cleanup task."""
        if self._started:
            return
        
        self._cleanup_task = asyncio.create_task(self._cleanup_old_requests())
        self._started = True
        logger.info("Rate limiter started")
    
    async def stop(self) -> None:
        """Stop the rate limiter cleanup task."""
        if not self._started:
            return
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        self._started = False
        logger.info("Rate limiter stopped")
    
    async def is_allowed(
        self, 
        client_id: str, 
        requests_per_minute: Optional[int] = None,
        requests_per_hour: Optional[int] = None
    ) -> bool:
        """
        Check if a request is allowed for the given client.
        
        Args:
            client_id: Unique identifier for the client (IP, API key, etc.)
            requests_per_minute: Override default requests per minute limit
            requests_per_hour: Override default requests per hour limit
            
        Returns:
            True if request is allowed, False otherwise
        """
        current_time = time.time()
        
        if client_id in self.blocked_clients:
            if current_time < self.blocked_clients[client_id]:
                return False
            else:
                del self.blocked_clients[client_id]
        
        async with self._lock:
            history = self.request_history[client_id]
            
            rpm_limit = requests_per_minute or settings.rate_limit_requests
            rph_limit = requests_per_hour or (rpm_limit * 60)
            
            cutoff_time = current_time - 3600
            while history and history[0] < cutoff_time:
                history.popleft()
            
            minute_cutoff = current_time - 60
            hour_cutoff = current_time - 3600
            
            requests_last_minute = sum(1 for timestamp in history if timestamp > minute_cutoff)
            requests_last_hour = len(history)
            
            if requests_last_minute >= rpm_limit:
                logger.warning(f"Rate limit exceeded for {client_id}: {requests_last_minute}/{rpm_limit} per minute")
                await self._block_client(client_id, 60)
                return False
            
            if requests_last_hour >= rph_limit:
                logger.warning(f"Rate limit exceeded for {client_id}: {requests_last_hour}/{rph_limit} per hour")
                await self._block_client(client_id, 300)
                return False
            
            history.append(current_time)
            
            return True
    
    async def _block_client(self, client_id: str, duration_seconds: int) -> None:
        """Block a client for a specified duration."""
        block_until = time.time() + duration_seconds
        self.blocked_clients[client_id] = block_until
        logger.info(f"Blocked client {client_id} for {duration_seconds} seconds")
    
    async def unblock_client(self, client_id: str) -> bool:
        """Manually unblock a client."""
        if client_id in self.blocked_clients:
            del self.blocked_clients[client_id]
            logger.info(f"Manually unblocked client {client_id}")
            return True
        return False
    
    async def get_client_stats(self, client_id: str) -> Dict[str, any]:
        """Get statistics for a specific client."""
        current_time = time.time()
        
        async with self._lock:
            history = self.request_history.get(client_id, deque())
            
            minute_cutoff = current_time - 60
            hour_cutoff = current_time - 3600
            day_cutoff = current_time - 86400
            
            requests_last_minute = sum(1 for timestamp in history if timestamp > minute_cutoff)
            requests_last_hour = sum(1 for timestamp in history if timestamp > hour_cutoff)
            requests_last_day = sum(1 for timestamp in history if timestamp > day_cutoff)
            
            is_blocked = client_id in self.blocked_clients
            blocked_until = self.blocked_clients.get(client_id, 0)
            
            return {
                'client_id': client_id,
                'requests_last_minute': requests_last_minute,
                'requests_last_hour': requests_last_hour,
                'requests_last_day': requests_last_day,
                'is_blocked': is_blocked,
                'blocked_until': blocked_until if is_blocked else None,
                'total_requests': len(history)
            }
    
    async def get_global_stats(self) -> Dict[str, any]:
        """Get global rate limiter statistics."""
        current_time = time.time()
        
        async with self._lock:
            total_clients = len(self.request_history)
            total_blocked = len(self.blocked_clients)
            
            total_requests_minute = 0
            total_requests_hour = 0
            total_requests_day = 0
            
            minute_cutoff = current_time - 60
            hour_cutoff = current_time - 3600
            day_cutoff = current_time - 86400
            
            for history in self.request_history.values():
                total_requests_minute += sum(1 for timestamp in history if timestamp > minute_cutoff)
                total_requests_hour += sum(1 for timestamp in history if timestamp > hour_cutoff)
                total_requests_day += sum(1 for timestamp in history if timestamp > day_cutoff)
            
            return {
                'total_clients': total_clients,
                'blocked_clients': total_blocked,
                'requests_last_minute': total_requests_minute,
                'requests_last_hour': total_requests_hour,
                'requests_last_day': total_requests_day,
                'rate_limit_per_minute': settings.rate_limit_requests,
                'active_blocks': len([
                    client_id for client_id, block_time in self.blocked_clients.items()
                    if block_time > current_time
                ])
            }
    
    async def reset_client_history(self, client_id: str) -> bool:
        """Reset request history for a specific client."""
        async with self._lock:
            if client_id in self.request_history:
                del self.request_history[client_id]
                logger.info(f"Reset request history for client {client_id}")
                return True
            return False
    
    async def _cleanup_old_requests(self) -> None:
        """Periodically clean up old request history."""
        while True:
            try:
                await asyncio.sleep(300)
                
                current_time = time.time()
                cutoff_time = current_time - 86400
                
                async with self._lock:
                    clients_to_remove = []
                    
                    for client_id, history in self.request_history.items():
                        while history and history[0] < cutoff_time:
                            history.popleft()
                        
                        if not history:
                            clients_to_remove.append(client_id)
                    
                    for client_id in clients_to_remove:
                        del self.request_history[client_id]
                    
                    expired_blocks = [
                        client_id for client_id, block_time in self.blocked_clients.items()
                        if block_time <= current_time
                    ]
                    
                    for client_id in expired_blocks:
                        del self.blocked_clients[client_id]
                
                if clients_to_remove or expired_blocks:
                    logger.debug(f"Cleaned up {len(clients_to_remove)} client histories and {len(expired_blocks)} expired blocks")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in rate limiter cleanup: {e}")
    
    async def add_whitelist(self, client_id: str) -> None:
        """Add a client to whitelist (not implemented in this basic version)."""
        pass
    
    async def add_blacklist(self, client_id: str, duration_seconds: int = 3600) -> None:
        """Add a client to blacklist by blocking them."""
        await self._block_client(client_id, duration_seconds)
        logger.info(f"Added client {client_id} to blacklist for {duration_seconds} seconds")


rate_limiter = RateLimiter()