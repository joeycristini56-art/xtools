import sys
import json
from typing import Optional
from loguru import logger
from datetime import datetime


class JSONFormatter:
    """Custom JSON formatter for structured logging."""
    
    def format(self, record):
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record["level"].name,
            "message": record["message"],
            "module": record["name"],
            "function": record["function"],
            "line": record["line"]
        }
        
        if record.get("extra"):
            safe_extra = {}
            for key, value in record["extra"].items():
                try:
                    json.dumps(value)
                    safe_extra[key] = value
                except (TypeError, ValueError):
                    safe_extra[key] = str(value)
            log_entry.update(safe_extra)
            
        return json.dumps(log_entry)


def setup_logging(
    level: str = "INFO",
    format_type: str = "json",
    log_file: Optional[str] = None
) -> None:
    """Setup application logging configuration."""
    
    logger.remove()
    
    if format_type.lower() == "json":
        log_format = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
    else:
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )
    
    logger.add(
        sys.stdout,
        format=log_format,
        level=level.upper(),
        colorize=format_type.lower() != "json"
    )
    
    if log_file:
        logger.add(
            log_file,
            format=log_format,
            level=level.upper(),
            rotation="100 MB",
            retention="30 days",
            compression="gz"
        )
    
    logger.info("Logging configured", level=level, format=format_type, file=log_file)


def get_logger(name: str = "xorthonl"):
    """Get logger instance with context."""
    return logger.bind(service=name)


default_logger = get_logger()