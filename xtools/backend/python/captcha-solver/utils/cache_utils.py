import json
import pickle
import hashlib
import asyncio
from typing import Any, Optional, Dict, Union
from datetime import datetime, timedelta
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
from pydantic import BaseModel
from .logger import get_logger
from config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle datetime and Pydantic models."""
    
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, BaseModel):
            return obj.model_dump()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)


def parse_datetime_strings(obj):
    """Recursively parse datetime strings in a dictionary."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str) and key.endswith('_at'):
                try:
                    obj[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                except (ValueError, AttributeError, TypeError):
                    pass
            elif isinstance(value, (dict, list)):
                obj[key] = parse_datetime_strings(value)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            obj[i] = parse_datetime_strings(item)
    return obj


class CacheManager:
    """Redis-based cache manager for CAPTCHA solving results and data."""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self._connected = False
        self._lock = asyncio.Lock()
    
    async def connect(self) -> None:
        """Connect to Redis server."""
        if self._connected:
            return
        
        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                db=settings.redis_db,
                password=settings.redis_password,
                decode_responses=False,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            await self.redis_client.ping()
            self._connected = True
            logger.info("Connected to Redis cache")
            
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Cache will be disabled.")
            self.redis_client = None
            self._connected = False
    
    async def disconnect(self) -> None:
        """Disconnect from Redis server."""
        if self.redis_client:
            await self.redis_client.close()
            self._connected = False
            logger.info("Disconnected from Redis cache")
    
    def _generate_key(self, prefix: str, data: Union[str, Dict[str, Any]]) -> str:
        """Generate a cache key from data."""
        if isinstance(data, dict):
            serializable_data = {}
            for key, value in data.items():
                try:
                    json.dumps(value)
                    serializable_data[key] = value
                except (TypeError, ValueError):
                    serializable_data[key] = str(value)
            data_str = json.dumps(serializable_data, sort_keys=True)
        else:
            data_str = str(data)
        
        hash_obj = hashlib.sha256(data_str.encode())
        hash_hex = hash_obj.hexdigest()[:16]
        
        return f"xorthonl:{prefix}:{hash_hex}"
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        expire_seconds: Optional[int] = None,
        serialize: bool = True
    ) -> bool:
        """Set a value in cache."""
        if not self._connected or not self.redis_client:
            return False
        
        try:
            if serialize:
                if isinstance(value, (dict, list, BaseModel)) or hasattr(value, '__dict__'):
                    serialized_value = json.dumps(value, cls=CustomJSONEncoder).encode()
                else:
                    serialized_value = pickle.dumps(value)
            else:
                serialized_value = value if isinstance(value, bytes) else str(value).encode()
            
            if expire_seconds:
                await self.redis_client.setex(key, expire_seconds, serialized_value)
            else:
                await self.redis_client.set(key, serialized_value)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to set cache key {key}: {e}")
            return False
    
    async def get(self, key: str, deserialize: bool = True) -> Optional[Any]:
        """Get a value from cache."""
        if not self._connected or not self.redis_client:
            return None
        
        try:
            value = await self.redis_client.get(key)
            if value is None:
                return None
            
            if deserialize:
                try:
                    data = json.loads(value.decode())
                    return parse_datetime_strings(data)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    try:
                        return pickle.loads(value)
                    except:
                        return value.decode() if isinstance(value, bytes) else value
            else:
                return value
                
        except Exception as e:
            logger.error(f"Failed to get cache key {key}: {e}")
            return None
    
    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        if not self._connected or not self.redis_client:
            return False
        
        try:
            result = await self.redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Failed to delete cache key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        if not self._connected or not self.redis_client:
            return False
        
        try:
            result = await self.redis_client.exists(key)
            return result > 0
        except Exception as e:
            logger.error(f"Failed to check cache key {key}: {e}")
            return False
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration time for a key."""
        if not self._connected or not self.redis_client:
            return False
        
        try:
            result = await self.redis_client.expire(key, seconds)
            return result
        except Exception as e:
            logger.error(f"Failed to set expiration for key {key}: {e}")
            return False
    
    async def cache_captcha_solution(
        self, 
        captcha_data: Dict[str, Any], 
        solution: Any,
        expire_minutes: int = 60
    ) -> str:
        """Cache a CAPTCHA solution."""
        cache_key = self._generate_key("solution", captcha_data)
        
        cache_data = {
            'solution': solution,
            'cached_at': datetime.utcnow().isoformat(),
            'captcha_type': captcha_data.get('captcha_type'),
            'expires_at': (datetime.utcnow() + timedelta(minutes=expire_minutes)).isoformat()
        }
        
        success = await self.set(cache_key, cache_data, expire_seconds=expire_minutes * 60)
        
        if success:
            logger.debug(f"Cached CAPTCHA solution with key: {cache_key}")
        
        return cache_key
    
    async def get_cached_solution(self, captcha_data: Dict[str, Any]) -> Optional[Any]:
        """Get a cached CAPTCHA solution."""
        cache_key = self._generate_key("solution", captcha_data)
        cached_data = await self.get(cache_key)
        
        if cached_data:
            expires_at = cached_data.get('expires_at')
            if expires_at:
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                elif not isinstance(expires_at, datetime):
                    expires_at = None
            
            if expires_at and datetime.utcnow() < expires_at:
                logger.debug(f"Found cached solution for key: {cache_key}")
                return cached_data['solution']
            else:
                await self.delete(cache_key)
                logger.debug(f"Cached solution expired for key: {cache_key}")
        
        return None
    
    async def cache_model_result(
        self, 
        model_name: str, 
        input_data: Any, 
        result: Any,
        expire_hours: int = 24
    ) -> str:
        """Cache AI model results."""
        cache_key = self._generate_key(f"model:{model_name}", input_data)
        
        cache_data = {
            'result': result,
            'model_name': model_name,
            'cached_at': datetime.utcnow().isoformat(),
            'input_hash': hashlib.sha256(str(input_data).encode()).hexdigest()[:16]
        }
        
        success = await self.set(cache_key, cache_data, expire_seconds=expire_hours * 3600)
        
        if success:
            logger.debug(f"Cached model result for {model_name} with key: {cache_key}")
        
        return cache_key
    
    async def get_cached_model_result(self, model_name: str, input_data: Any) -> Optional[Any]:
        """Get cached AI model result."""
        cache_key = self._generate_key(f"model:{model_name}", input_data)
        cached_data = await self.get(cache_key)
        
        if cached_data:
            logger.debug(f"Found cached model result for {model_name}")
            return cached_data['result']
        
        return None
    
    async def cache_task_result(
        self, 
        task_id: str, 
        result: Dict[str, Any],
        expire_hours: int = 1
    ) -> bool:
        """Cache task result."""
        cache_key = f"xorthonl:task:{task_id}"
        
        cache_data = {
            'task_id': task_id,
            'result': result,
            'cached_at': datetime.utcnow().isoformat()
        }
        
        return await self.set(cache_key, cache_data, expire_seconds=expire_hours * 3600)
    
    async def get_cached_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get cached task result."""
        cache_key = f"xorthonl:task:{task_id}"
        return await self.get(cache_key)
    
    async def increment_counter(self, key: str, amount: int = 1) -> int:
        """Increment a counter in cache."""
        if not self._connected or not self.redis_client:
            return 0
        
        try:
            return await self.redis_client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Failed to increment counter {key}: {e}")
            return 0
    
    async def get_counter(self, key: str) -> int:
        """Get counter value."""
        if not self._connected or not self.redis_client:
            return 0
        
        try:
            value = await self.redis_client.get(key)
            return int(value) if value else 0
        except Exception as e:
            logger.error(f"Failed to get counter {key}: {e}")
            return 0
    
    async def set_hash(self, key: str, field: str, value: Any) -> bool:
        """Set a field in a hash."""
        if not self._connected or not self.redis_client:
            return False
        
        try:
            serialized_value = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
            await self.redis_client.hset(key, field, serialized_value)
            return True
        except Exception as e:
            logger.error(f"Failed to set hash field {key}:{field}: {e}")
            return False
    
    async def get_hash(self, key: str, field: str) -> Optional[Any]:
        """Get a field from a hash."""
        if not self._connected or not self.redis_client:
            return None
        
        try:
            value = await self.redis_client.hget(key, field)
            if value:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value.decode() if isinstance(value, bytes) else value
            return None
        except Exception as e:
            logger.error(f"Failed to get hash field {key}:{field}: {e}")
            return None
    
    async def get_all_hash(self, key: str) -> Dict[str, Any]:
        """Get all fields from a hash."""
        if not self._connected or not self.redis_client:
            return {}
        
        try:
            hash_data = await self.redis_client.hgetall(key)
            result = {}
            for field, value in hash_data.items():
                field_str = field.decode() if isinstance(field, bytes) else field
                try:
                    result[field_str] = json.loads(value)
                except json.JSONDecodeError:
                    result[field_str] = value.decode() if isinstance(value, bytes) else value
            return result
        except Exception as e:
            logger.error(f"Failed to get all hash fields for {key}: {e}")
            return {}
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching a pattern."""
        if not self._connected or not self.redis_client:
            return 0
        
        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                return await self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Failed to clear pattern {pattern}: {e}")
            return 0
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self._connected or not self.redis_client:
            return {'connected': False}
        
        try:
            info = await self.redis_client.info()
            return {
                'connected': True,
                'used_memory': info.get('used_memory_human', 'Unknown'),
                'connected_clients': info.get('connected_clients', 0),
                'total_commands_processed': info.get('total_commands_processed', 0),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'hit_rate': info.get('keyspace_hits', 0) / max(
                    info.get('keyspace_hits', 0) + info.get('keyspace_misses', 0), 1
                ) * 100
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {'connected': False, 'error': str(e)}


cache_manager = CacheManager()