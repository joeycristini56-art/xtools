import asyncio
from typing import Any, Dict, Optional
from core.base_solver import BaseSolver
from models.base import CaptchaType
from models.responses import TokenSolution
from utils.browser_utils import browser_manager
from utils.proxy_utils import proxy_manager
from utils.logger import get_logger
from utils.cache_utils import cache_manager

logger = get_logger(__name__)


class RecaptchaV3Solver(BaseSolver):
    """Google reCAPTCHA v3 solver using browser automation."""
    
    def __init__(self):
        super().__init__("RecaptchaV3Solver", CaptchaType.RECAPTCHA_V3)
        self.max_attempts = 2
        self.timeout_seconds = 30
    
    async def _initialize(self) -> None:
        """Initialize browser manager."""
        try:
            await browser_manager.initialize()
            logger.info("reCAPTCHA v3 solver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize reCAPTCHA v3 solver: {e}")
            raise
    
    async def solve(self, captcha_data: Dict[str, Any]) -> Optional[TokenSolution]:
        """
        Solve Google reCAPTCHA v3.
        
        Args:
            captcha_data: Dictionary containing:
                - website_url: URL where reCAPTCHA is embedded
                - site_key: reCAPTCHA site key
                - action: Action name for v3
                - min_score: Minimum score required (0.0-1.0)
                - proxy: Optional proxy to use
        
        Returns:
            TokenSolution with reCAPTCHA token or None if failed
        """
        try:
            if not self.validate_input(captcha_data):
                return None
            
            cached_result = await cache_manager.get_cached_solution(captcha_data)
            if cached_result:
                logger.debug("Using cached reCAPTCHA v3 solution")
                return TokenSolution(**cached_result)
            
            website_url = captcha_data['website_url']
            site_key = captcha_data['site_key']
            action = captcha_data.get('action', 'submit')
            min_score = captcha_data.get('min_score', 0.5)
            proxy = captcha_data.get('proxy')
            
            if not proxy and proxy_manager.working_proxies:
                proxy = await proxy_manager.get_proxy()
            
            for attempt in range(self.max_attempts):
                try:
                    logger.info(f"Solving reCAPTCHA v3 attempt {attempt + 1}/{self.max_attempts}")
                    
                    context = await browser_manager.get_context(proxy=proxy)
                    
                    try:
                        page = await browser_manager.create_stealth_page(context)
                        
                        token = await self._solve_recaptcha_v3_challenge(
                            page, website_url, site_key, action
                        )
                        
                        if token:
                            solution = TokenSolution(
                                token=token,
                                confidence=0.9
                            )
                            
                            await cache_manager.cache_captcha_solution(
                                captcha_data, solution.dict(), expire_minutes=15
                            )
                            
                            logger.info("reCAPTCHA v3 solved successfully")
                            return solution
                        
                    finally:
                        await context.close()
                    
                except Exception as e:
                    logger.warning(f"reCAPTCHA v3 attempt {attempt + 1} failed: {e}")
                    
                    if proxy:
                        proxy_manager.mark_proxy_failed(proxy)
                        proxy = await proxy_manager.get_proxy()
                    
                    if attempt < self.max_attempts - 1:
                        await asyncio.sleep(2)
            
            logger.error("All reCAPTCHA v3 solving attempts failed")
            return None
            
        except Exception as e:
            logger.error(f"Error solving reCAPTCHA v3: {e}")
            return None
    
    async def _solve_recaptcha_v3_challenge(
        self,
        page,
        website_url: str,
        site_key: str,
        action: str
    ) -> Optional[str]:
        """Solve reCAPTCHA v3 challenge on a specific page."""
        try:
            html_template = self._create_recaptcha_v3_html(site_key, action)
            
            await page.route(website_url, lambda route: route.fulfill(
                body=html_template,
                status=200,
                content_type="text/html"
            ))
            
            await page.goto(website_url)
            
            await asyncio.sleep(3)
            
            token = await page.evaluate(f"""
                new Promise((resolve) => {{
                    if (typeof grecaptcha !== 'undefined' && grecaptcha.ready) {{
                        grecaptcha.ready(function() {{
                            grecaptcha.execute('{site_key}', {{action: '{action}'}}).then(function(token) {{
                                resolve(token);
                            }}).catch(function(error) {{
                                console.error('reCAPTCHA error:', error);
                                resolve(null);
                            }});
                        }});
                    }} else {{
                        console.error('reCAPTCHA not loaded');
                        resolve(null);
                    }}
                }})
            """)
            
            if token and len(token) > 10:
                logger.debug(f"reCAPTCHA v3 token obtained: {token[:20]}...")
                return token
            
            logger.warning("reCAPTCHA v3 token not obtained")
            return None
            
        except Exception as e:
            logger.error(f"Error in reCAPTCHA v3 challenge solving: {e}")
            return None
    
    def _create_recaptcha_v3_html(self, site_key: str, action: str) -> str:
        """Create HTML template with reCAPTCHA v3 widget."""
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>reCAPTCHA v3 Challenge</title>
            <script src="https://www.google.com/recaptcha/api.js?render={site_key}"></script>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    margin: 0;
                    background-color: #f5f5f5;
                }}
                .container {{
                    text-align: center;
                    padding: 20px;
                    background: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .status {{
                    margin: 20px 0;
                    padding: 10px;
                    border-radius: 4px;
                }}
                .loading {{
                    background-color: #e3f2fd;
                    color: #1976d2;
                }}
                .success {{
                    background-color: #e8f5e8;
                    color: #2e7d32;
                }}
                .error {{
                    background-color: #ffebee;
                    color: #c62828;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>reCAPTCHA v3 Security Check</h2>
                <div id="status" class="status loading">Processing security check...</div>
                <div id="score-display" style="margin-top: 10px; font-size: 14px; color: #666;"></div>
            </div>
            
            <script>
                let tokenReceived = false;
                
                grecaptcha.ready(function() {{
                    console.log('reCAPTCHA v3 ready');
                    document.getElementById('status').textContent = 'Executing security check...';
                    
                    grecaptcha.execute('{site_key}', {{action: '{action}'}}).then(function(token) {{
                        console.log('reCAPTCHA v3 token received:', token.substring(0, 20) + '...');
                        tokenReceived = true;
                        
                        document.getElementById('status').textContent = 'Security check completed!';
                        document.getElementById('status').className = 'status success';
                        
                        // Store token for retrieval
                        window.recaptchaToken = token;
                        
                    }}).catch(function(error) {{
                        console.error('reCAPTCHA v3 error:', error);
                        document.getElementById('status').textContent = 'Security check failed: ' + error;
                        document.getElementById('status').className = 'status error';
                    }});
                }});
                
                // Fallback timeout
                setTimeout(function() {{
                    if (!tokenReceived) {{
                        console.warn('reCAPTCHA v3 timeout');
                        document.getElementById('status').textContent = 'Security check timeout';
                        document.getElementById('status').className = 'status error';
                    }}
                }}, 15000);
            </script>
        </body>
        </html>
        """
    
    def validate_input(self, captcha_data: Dict[str, Any]) -> bool:
        """Validate input data for reCAPTCHA v3 solving."""
        if not captcha_data.get('website_url'):
            logger.error("No website URL provided")
            return False
        
        if not captcha_data.get('site_key'):
            logger.error("No site key provided")
            return False
        
        site_key = captcha_data['site_key']
        if not isinstance(site_key, str) or len(site_key) < 10:
            logger.error("Invalid site key format")
            return False
        
        min_score = captcha_data.get('min_score')
        if min_score is not None:
            if not isinstance(min_score, (int, float)) or not (0.0 <= min_score <= 1.0):
                logger.error("min_score must be a number between 0.0 and 1.0")
                return False
        
        return True
    
    async def _cleanup(self) -> None:
        """Clean up browser resources."""
        logger.debug("reCAPTCHA v3 solver cleanup completed")