import asyncio
import random
from typing import Optional, Dict, Any, List
try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Browser = None
    BrowserContext = None
    Page = None
from .logger import get_logger
from config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class BrowserManager:
    """Advanced browser management for CAPTCHA solving."""
    
    def __init__(self):
        self.playwright = None
        self.browser_pool: List[Browser] = []
        self.context_pool: List[BrowserContext] = []
        self.active_contexts: Dict[str, BrowserContext] = {}
        self._lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize browser pool."""
        if self._initialized:
            return
        
        try:
            logger.info("Initializing browser manager")
            self.playwright = await async_playwright().start()
            
            for i in range(settings.browser_pool_size):
                browser = await self._create_browser()
                self.browser_pool.append(browser)
                logger.info(f"Browser {i+1}/{settings.browser_pool_size} initialized")
            
            self._initialized = True
            logger.info(f"Browser pool initialized with {len(self.browser_pool)} browsers")
            
        except Exception as e:
            logger.error(f"Failed to initialize browser manager: {e}")
            raise
    
    async def _create_browser(self) -> Browser:
        """Create a new browser instance."""
        browser_args = [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding'
        ]
        
        if settings.browser_user_agent:
            browser_args.append(f'--user-agent={settings.browser_user_agent}')
        
        browser = await self.playwright.chromium.launch(
            headless=settings.browser_headless,
            args=browser_args
        )
        
        return browser
    
    async def get_context(self, proxy: Optional[str] = None, task_id: Optional[str] = None) -> BrowserContext:
        """Get a browser context with optional proxy."""
        async with self._lock:
            if not self._initialized:
                await self.initialize()
            
            try:
                browser = random.choice(self.browser_pool)
                
                context_options = {
                    'viewport': {'width': 1920, 'height': 1080},
                    'user_agent': settings.browser_user_agent or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'java_script_enabled': True,
                    'accept_downloads': False,
                    'ignore_https_errors': True
                }
                
                if proxy:
                    proxy_config = self._parse_proxy(proxy)
                    if proxy_config:
                        context_options['proxy'] = proxy_config
                
                context = await browser.new_context(**context_options)
                
                await context.set_extra_http_headers({
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                })
                
                if task_id:
                    self.active_contexts[task_id] = context
                
                logger.debug(f"Created browser context for task {task_id}")
                return context
                
            except Exception as e:
                logger.error(f"Failed to create browser context: {e}")
                raise
    
    def _parse_proxy(self, proxy: str) -> Optional[Dict[str, Any]]:
        """Parse proxy string into configuration."""
        try:
            parts = proxy.split(':')
            
            if len(parts) == 2:
                return {
                    'server': f'http://{parts[0]}:{parts[1]}'
                }
            elif len(parts) == 4:
                return {
                    'server': f'http://{parts[0]}:{parts[1]}',
                    'username': parts[2],
                    'password': parts[3]
                }
            elif len(parts) == 5:
                protocol, host, port, username, password = parts
                return {
                    'server': f'{protocol}://{host}:{port}',
                    'username': username,
                    'password': password
                }
            else:
                logger.warning(f"Invalid proxy format: {proxy}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to parse proxy {proxy}: {e}")
            return None
    
    async def create_stealth_page(self, context: BrowserContext) -> Page:
        """Create a stealth page with anti-detection measures."""
        try:
            page = await context.new_page()
            
            await page.add_init_script("""
                // Override webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                // Override plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                
                // Override languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
                
                // Override permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                
                // Override chrome runtime
                window.chrome = {
                    runtime: {},
                };
            """)
            
            await page.set_viewport_size({'width': 1920, 'height': 1080})
            
            logger.debug("Created stealth page with anti-detection measures")
            return page
            
        except Exception as e:
            logger.error(f"Failed to create stealth page: {e}")
            raise
    
    async def wait_for_element(
        self, 
        page: Page, 
        selector: str, 
        timeout: int = 30000,
        state: str = "visible"
    ) -> Optional[Any]:
        """Wait for element with timeout."""
        try:
            element = await page.wait_for_selector(
                selector, 
                timeout=timeout, 
                state=state
            )
            return element
        except Exception as e:
            logger.warning(f"Element {selector} not found within {timeout}ms: {e}")
            return None
    
    async def solve_turnstile(
        self, 
        page: Page, 
        site_key: str, 
        url: str,
        action: Optional[str] = None,
        cdata: Optional[str] = None
    ) -> Optional[str]:
        """Solve Cloudflare Turnstile challenge."""
        try:
            logger.info(f"Solving Turnstile for {url}")
            
            await page.goto(url)
            
            turnstile_selector = f'[data-sitekey="{site_key}"]'
            widget = await self.wait_for_element(page, turnstile_selector, timeout=10000)
            
            if not widget:
                logger.error("Turnstile widget not found")
                return None
            
            await widget.click()
            
            token_selector = 'input[name="cf-turnstile-response"]'
            for attempt in range(30):
                try:
                    token_element = await page.query_selector(token_selector)
                    if token_element:
                        token = await token_element.get_attribute('value')
                        if token and len(token) > 10:
                            logger.info("Turnstile solved successfully")
                            return token
                except:
                    pass
                
                await asyncio.sleep(1)
            
            logger.error("Turnstile solving timeout")
            return None
            
        except Exception as e:
            logger.error(f"Failed to solve Turnstile: {e}")
            return None
    
    async def solve_recaptcha_v2(
        self, 
        page: Page, 
        site_key: str, 
        url: str
    ) -> Optional[str]:
        """Solve reCAPTCHA v2 challenge."""
        try:
            logger.info(f"Solving reCAPTCHA v2 for {url}")
            
            await page.goto(url)
            
            recaptcha_frame = await self.wait_for_element(
                page, 
                'iframe[src*="recaptcha"]', 
                timeout=10000
            )
            
            if not recaptcha_frame:
                logger.error("reCAPTCHA iframe not found")
                return None
            
            frame = await recaptcha_frame.content_frame()
            checkbox = await self.wait_for_element(
                frame, 
                '.recaptcha-checkbox-border', 
                timeout=5000
            )
            
            if checkbox:
                await checkbox.click()
            
            for attempt in range(60):
                try:
                    token_element = await page.query_selector('textarea[name="g-recaptcha-response"]')
                    if token_element:
                        token = await token_element.get_attribute('value')
                        if token and len(token) > 10:
                            logger.info("reCAPTCHA v2 solved successfully")
                            return token
                except:
                    pass
                
                await asyncio.sleep(1)
            
            logger.error("reCAPTCHA v2 solving timeout")
            return None
            
        except Exception as e:
            logger.error(f"Failed to solve reCAPTCHA v2: {e}")
            return None
    
    async def close_context(self, task_id: str) -> None:
        """Close browser context for task."""
        try:
            if task_id in self.active_contexts:
                context = self.active_contexts[task_id]
                await context.close()
                del self.active_contexts[task_id]
                logger.debug(f"Closed browser context for task {task_id}")
        except Exception as e:
            logger.error(f"Failed to close context for task {task_id}: {e}")
    
    async def cleanup(self) -> None:
        """Cleanup browser resources."""
        try:
            logger.info("Cleaning up browser manager")
            
            for task_id in list(self.active_contexts.keys()):
                await self.close_context(task_id)
            
            for browser in self.browser_pool:
                await browser.close()
            
            if self.playwright:
                await self.playwright.stop()
            
            self._initialized = False
            logger.info("Browser manager cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during browser cleanup: {e}")


browser_manager = BrowserManager()