"""
Advanced Stealth Utilities for CAPTCHA Solving
Implements anti-detection techniques for browser automation.
"""

import random
import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Tuple
from playwright.async_api import Page, BrowserContext
from .logger import get_logger

logger = get_logger(__name__)


class StealthManager:
    """Advanced stealth techniques for avoiding CAPTCHA detection."""
    
    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0"
        ]
        
        self.screen_resolutions = [
            (1920, 1080), (1366, 768), (1536, 864), (1440, 900),
            (1280, 720), (1600, 900), (1024, 768), (1280, 1024)
        ]
        
        self.languages = [
            "en-US,en;q=0.9",
            "en-GB,en;q=0.9",
            "en-US,en;q=0.8,es;q=0.6",
            "en-US,en;q=0.9,fr;q=0.8"
        ]
        
    async def setup_stealth_context(self, context: BrowserContext) -> None:
        """Setup stealth configuration for browser context."""
        try:
            await context.add_init_script(self._get_webdriver_stealth_script())
            await context.add_init_script(self._get_navigator_stealth_script())
            await context.add_init_script(self._get_chrome_stealth_script())
            await context.add_init_script(self._get_permissions_stealth_script())
            
            logger.debug("Stealth context setup completed")
            
        except Exception as e:
            logger.error(f"Failed to setup stealth context: {e}")
            
    async def create_stealth_page(self, context: BrowserContext) -> Page:
        """Create a stealth page with human-like properties."""
        try:
            page = await context.new_page()
            
            width, height = random.choice(self.screen_resolutions)
            await page.set_viewport_size({"width": width, "height": height})
            
            user_agent = random.choice(self.user_agents)
            await page.set_extra_http_headers({
                "User-Agent": user_agent,
                "Accept-Language": random.choice(self.languages),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Cache-Control": "max-age=0"
            })
            
            await self._add_human_behavior(page)
            
            logger.debug("Stealth page created successfully")
            return page
            
        except Exception as e:
            logger.error(f"Failed to create stealth page: {e}")
            raise
            
    async def _add_human_behavior(self, page: Page) -> None:
        """Add human-like behavior patterns to the page."""
        try:
            await page.add_init_script("""
                // Track mouse movements
                let mouseMovements = [];
                let lastMouseMove = Date.now();
                
                document.addEventListener('mousemove', (e) => {
                    const now = Date.now();
                    mouseMovements.push({
                        x: e.clientX,
                        y: e.clientY,
                        timestamp: now,
                        timeDelta: now - lastMouseMove
                    });
                    lastMouseMove = now;
                    
                    // Keep only recent movements
                    if (mouseMovements.length > 100) {
                        mouseMovements = mouseMovements.slice(-50);
                    }
                });
                
                // Add to window for access
                window.getMouseMovements = () => mouseMovements;
            """)
            
            await page.add_init_script("""
                let keystrokes = [];
                let lastKeyTime = Date.now();
                
                document.addEventListener('keydown', (e) => {
                    const now = Date.now();
                    keystrokes.push({
                        key: e.key,
                        timestamp: now,
                        timeDelta: now - lastKeyTime
                    });
                    lastKeyTime = now;
                    
                    if (keystrokes.length > 50) {
                        keystrokes = keystrokes.slice(-25);
                    }
                });
                
                window.getKeystrokes = () => keystrokes;
            """)
            
        except Exception as e:
            logger.debug(f"Failed to add human behavior: {e}")
            
    async def human_like_click(self, page: Page, selector: str, delay_range: Tuple[float, float] = (0.1, 0.3)) -> None:
        """Perform a human-like click with natural timing and movement."""
        try:
            element = await page.wait_for_selector(selector, timeout=10000)
            if not element:
                raise Exception(f"Element not found: {selector}")
                
            box = await element.bounding_box()
            if not box:
                raise Exception(f"Element has no bounding box: {selector}")
                
            x = box["x"] + box["width"] / 2 + random.uniform(-5, 5)
            y = box["y"] + box["height"] / 2 + random.uniform(-5, 5)
            
            await self._human_like_mouse_move(page, x, y)
            
            await asyncio.sleep(random.uniform(*delay_range))
            
            await page.mouse.click(x, y, delay=random.uniform(50, 150))
            
            await asyncio.sleep(random.uniform(0.05, 0.15))
            
        except Exception as e:
            logger.error(f"Human-like click failed: {e}")
            raise
            
    async def _human_like_mouse_move(self, page: Page, target_x: float, target_y: float, steps: int = None) -> None:
        """Move mouse in a human-like curved path."""
        try:
            current_x, current_y = 100, 100
            
            if steps is None:
                distance = ((target_x - current_x) ** 2 + (target_y - current_y) ** 2) ** 0.5
                steps = max(5, int(distance / 20))
                
            for i in range(steps):
                progress = i / (steps - 1) if steps > 1 else 1
                
                curve_offset = random.uniform(-10, 10) * (0.5 - abs(progress - 0.5))
                
                x = current_x + (target_x - current_x) * progress + curve_offset
                y = current_y + (target_y - current_y) * progress + curve_offset
                
                await page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.01, 0.03))
                
        except Exception as e:
            logger.debug(f"Mouse movement failed: {e}")
            
    async def human_like_type(self, page: Page, selector: str, text: str, typing_speed_range: Tuple[float, float] = (0.05, 0.15)) -> None:
        """Type text with human-like timing and occasional mistakes."""
        try:
            element = await page.wait_for_selector(selector, timeout=10000)
            if not element:
                raise Exception(f"Element not found: {selector}")
                
            await element.click()
            await asyncio.sleep(random.uniform(0.1, 0.3))
            
            await element.fill("")
            
            for i, char in enumerate(text):
                if random.random() < 0.05 and i > 0:
                    wrong_char = random.choice("abcdefghijklmnopqrstuvwxyz")
                    await element.type(wrong_char, delay=random.uniform(*typing_speed_range) * 1000)
                    await asyncio.sleep(random.uniform(0.1, 0.3))
                    
                    await page.keyboard.press("Backspace")
                    await asyncio.sleep(random.uniform(0.05, 0.15))
                    
                await element.type(char, delay=random.uniform(*typing_speed_range) * 1000)
                
                if random.random() < 0.1:
                    await asyncio.sleep(random.uniform(0.3, 0.8))
                    
        except Exception as e:
            logger.error(f"Human-like typing failed: {e}")
            raise
            
    async def simulate_human_reading(self, page: Page, duration_range: Tuple[float, float] = (2.0, 5.0)) -> None:
        """Simulate human reading behavior with scrolling and pauses."""
        try:
            duration = random.uniform(*duration_range)
            end_time = time.time() + duration
            
            while time.time() < end_time:
                if random.random() < 0.3:
                    scroll_amount = random.randint(-200, 200)
                    await page.mouse.wheel(0, scroll_amount)
                    
                if random.random() < 0.4:
                    x = random.randint(100, 800)
                    y = random.randint(100, 600)
                    await page.mouse.move(x, y)
                    
                await asyncio.sleep(random.uniform(0.5, 1.5))
                
        except Exception as e:
            logger.debug(f"Human reading simulation failed: {e}")
            
    def _get_webdriver_stealth_script(self) -> str:
        """Get script to hide webdriver property."""
        return """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
        """
        
    def _get_navigator_stealth_script(self) -> str:
        """Get script to modify navigator properties."""
        return """
        // Override navigator properties
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
        
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
        
        Object.defineProperty(navigator, 'permissions', {
            get: () => ({
                query: () => Promise.resolve({ state: 'granted' }),
            }),
        });
        """
        
    def _get_chrome_stealth_script(self) -> str:
        """Get script to add Chrome-specific properties."""
        return """
        // Add chrome object
        window.chrome = {
            runtime: {},
            loadTimes: function() {
                return {
                    commitLoadTime: Date.now() / 1000 - Math.random(),
                    finishDocumentLoadTime: Date.now() / 1000 - Math.random(),
                    finishLoadTime: Date.now() / 1000 - Math.random(),
                    firstPaintAfterLoadTime: 0,
                    firstPaintTime: Date.now() / 1000 - Math.random(),
                    navigationType: 'Other',
                    npnNegotiatedProtocol: 'h2',
                    requestTime: Date.now() / 1000 - Math.random(),
                    startLoadTime: Date.now() / 1000 - Math.random(),
                    connectionInfo: 'h2',
                    wasFetchedViaSpdy: true,
                    wasNpnNegotiated: true
                };
            },
            csi: function() {
                return {
                    onloadT: Date.now(),
                    startE: Date.now(),
                    tran: 15
                };
            }
        };
        """
        
    def _get_permissions_stealth_script(self) -> str:
        """Get script to handle permissions API."""
        return """
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        """
        
    async def add_behavioral_fingerprint(self, page: Page) -> None:
        """Add realistic behavioral fingerprint to the page."""
        try:
            await page.add_init_script(f"""
                // Add realistic timing data
                window.performance.timing.navigationStart = {int(time.time() * 1000) - random.randint(1000, 5000)};
                
                // Add realistic screen properties
                Object.defineProperty(screen, 'availWidth', {{
                    get: () => {random.choice([1920, 1366, 1536, 1440])},
                }});
                
                Object.defineProperty(screen, 'availHeight', {{
                    get: () => {random.choice([1080, 768, 864, 900])},
                }});
                
                // Add realistic timezone
                Intl.DateTimeFormat().resolvedOptions = () => ({{
                    timeZone: '{random.choice(["America/New_York", "America/Los_Angeles", "Europe/London", "Europe/Berlin"])}',
                    locale: 'en-US'
                }});
                
                // Add realistic battery API
                navigator.getBattery = () => Promise.resolve({{
                    charging: {random.choice(["true", "false"])},
                    chargingTime: {random.randint(0, 7200)},
                    dischargingTime: {random.randint(3600, 28800)},
                    level: {random.uniform(0.2, 1.0):.2f}
                }});
            """)
            
        except Exception as e:
            logger.debug(f"Failed to add behavioral fingerprint: {e}")
            
    async def randomize_request_timing(self, min_delay: float = 1.0, max_delay: float = 3.0) -> None:
        """Add random delay to simulate human request timing."""
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)
        
    def get_random_user_agent(self) -> str:
        """Get a random user agent string."""
        return random.choice(self.user_agents)
        
    def get_random_viewport(self) -> Dict[str, int]:
        """Get random viewport dimensions."""
        width, height = random.choice(self.screen_resolutions)
        return {"width": width, "height": height}


stealth_manager = StealthManager()