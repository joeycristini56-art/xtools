from functools import lru_cache
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    api_title: str = "XorthonL CAPTCHA Solver API"
    api_version: str = "1.0.0"
    api_description: str = "Advanced CAPTCHA solving system supporting multiple CAPTCHA types"
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=12000, description="API port")
    api_workers: int = Field(default=1, description="Number of API workers")
    
    api_key: Optional[str] = Field(default=None, description="API authentication key")
    cors_origins: List[str] = Field(default=["*"], description="CORS allowed origins")
    rate_limit_requests: int = Field(default=100, description="Rate limit requests per minute")
    
    browser_headless: bool = Field(default=True, description="Run browsers in headless mode")
    browser_timeout: int = Field(default=30, description="Browser timeout in seconds")
    browser_pool_size: int = Field(default=3, description="Browser pool size")
    browser_user_agent: Optional[str] = Field(default=None, description="Custom user agent")
    
    proxy_enabled: bool = Field(default=False, description="Enable proxy support")
    proxy_list: List[str] = Field(default=[], description="List of proxy servers")
    proxy_rotation: bool = Field(default=True, description="Enable proxy rotation")
    
    ai_model_cache_dir: str = Field(default="./models", description="AI model cache directory")
    ocr_model: str = Field(default="easyocr", description="OCR model to use")
    image_classification_model: str = Field(default="microsoft/resnet-50", description="Image classification model")
    
    redis_url: str = Field(default="redis://localhost:6379", description="Redis connection URL")
    redis_db: int = Field(default=0, description="Redis database number")
    redis_password: Optional[str] = Field(default=None, description="Redis password")
    
    task_timeout: int = Field(default=120, description="Task timeout in seconds")
    task_retry_attempts: int = Field(default=3, description="Number of retry attempts")
    task_cleanup_interval: int = Field(default=300, description="Task cleanup interval in seconds")
    
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json/text)")
    log_file: Optional[str] = Field(default=None, description="Log file path")
    
    max_concurrent_tasks: int = Field(default=10, description="Maximum concurrent tasks")
    memory_limit_mb: int = Field(default=1024, description="Memory limit in MB")
    
    class Config:
        env_file = ".env"
        env_prefix = "XORTHONL_"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()