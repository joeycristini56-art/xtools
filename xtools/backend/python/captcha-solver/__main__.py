#!/usr/bin/env python3
"""
XorthonL CAPTCHA Solver API
Main entry point for running the API server.
"""

import asyncio
import sys
import argparse
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from xorthonl.config import get_settings
from xorthonl.utils.logger import setup_logging, get_logger


def create_parser():
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="XorthonL CAPTCHA Solver API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m xorthonl                    # Start API server
  python -m xorthonl --host 0.0.0.0     # Start on all interfaces
  python -m xorthonl --port 8080        # Start on port 8080
  python -m xorthonl --workers 4        # Start with 4 workers
  python -m xorthonl --debug            # Start in debug mode
        """
    )
    
    parser.add_argument(
        "--host",
        default=None,
        help="Host to bind to (default: from config)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind to (default: from config)"
    )
    
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of worker processes (default: from config)"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )
    
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="Set log level (default: from config)"
    )
    
    parser.add_argument(
        "--config-file",
        help="Path to configuration file"
    )
    
    return parser


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    settings = get_settings()
    
    if args.host:
        settings.api_host = args.host
    if args.port:
        settings.api_port = args.port
    if args.workers:
        settings.api_workers = args.workers
    if args.debug:
        settings.log_level = "DEBUG"
        settings.debug = True
    if args.log_level:
        settings.log_level = args.log_level
    
    setup_logging(
        level=settings.log_level,
        format_type=settings.log_format,
        log_file=settings.log_file
    )
    
    logger = get_logger(__name__)
    
    try:
        logger.info("Starting XorthonL CAPTCHA Solver API")
        logger.info(f"Host: {settings.api_host}")
        logger.info(f"Port: {settings.api_port}")
        logger.info(f"Workers: {settings.api_workers}")
        logger.info(f"Environment: {'production' if not settings.log_level == 'DEBUG' else 'development'}")
        logger.info(f"Log Level: {settings.log_level}")
        
        import uvicorn
        
        uvicorn.run(
            "xorthonl.api.main:app",
            host=settings.api_host,
            port=settings.api_port,
            workers=1 if args.reload else settings.api_workers,
            reload=args.reload,
            access_log=True,
            log_level=settings.log_level.lower(),
            loop="asyncio"
        )
        
    except KeyboardInterrupt:
        logger.info("Shutting down XorthonL API (KeyboardInterrupt)")
    except Exception as e:
        logger.error(f"Failed to start XorthonL API: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
# XTools FFI Integration
import json

def solve_captcha(image_path: str) -> str:
    """Solve CAPTCHA via FFI"""
    try:
        # Would need actual CAPTCHA solving implementation
        return json.dumps({
            "success": True,
            "message": "CAPTCHA would be solved here",
            "image": image_path,
            "solution": "placeholder"
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(solve_captcha(sys.argv[1]))
