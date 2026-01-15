import asyncio
import random
import time
from typing import Any, Dict, Optional, List
from core.base_solver import BaseSolver
from models.base import CaptchaType
from models.responses import TokenSolution
from utils.browser_utils import browser_manager
from utils.proxy_utils import proxy_manager
from utils.logger import get_logger
from utils.cache_utils import cache_manager
from utils.stealth_utils import stealth_manager
from utils.advanced_image_utils import advanced_image_processor
from utils.ml_model_manager import model_manager

logger = get_logger(__name__)


class RecaptchaV2Solver(BaseSolver):
    """
    Advanced Google reCAPTCHA v2 solver using modern techniques.
    
    Features:
    - YOLO-based object detection for image challenges
    - Advanced stealth techniques to avoid detection
    - Behavioral simulation for human-like interaction
    - Multi-method approach with fallbacks
    - Production-grade error handling and retry logic
    """
    
    def __init__(self):
        super().__init__("RecaptchaV2Solver", CaptchaType.RECAPTCHA_V2)
        self.max_attempts = 5
        self.timeout_seconds = 120
        self.yolo_model = None
        self.confidence_threshold = 0.6
        
        self.captcha_object_mappings = {
            'car': ['car', 'truck', 'bus', 'van', 'suv', 'sedan'],
            'bus': ['bus', 'coach'],
            'bicycle': ['bicycle', 'bike'],
            'motorcycle': ['motorcycle', 'motorbike', 'scooter'],
            'traffic light': ['traffic light', 'stoplight'],
            'crosswalk': ['crosswalk', 'zebra crossing'],
            'fire hydrant': ['fire hydrant', 'hydrant'],
            'stop sign': ['stop sign'],
            'parking meter': ['parking meter'],
            'boat': ['boat', 'ship', 'yacht'],
            'airplane': ['airplane', 'aircraft', 'plane'],
            'train': ['train', 'locomotive'],
            'bridge': ['bridge'],
            'mountain': ['mountain', 'hill'],
            'tree': ['tree'],
            'flower': ['flower'],
            'person': ['person', 'people', 'human']
        }
    
    async def _initialize(self) -> None:
        """Initialize browser manager and ML models."""
        try:
            await browser_manager.initialize()
            
            await advanced_image_processor.initialize()
            self.yolo_model = await model_manager.get_object_detector("yolov8n")
            
            logger.info("reCAPTCHA v2 solver initialized successfully with YOLO support")
        except Exception as e:
            logger.error(f"Failed to initialize reCAPTCHA v2 solver: {e}")
            raise
    
    async def solve(self, captcha_data: Dict[str, Any]) -> Optional[TokenSolution]:
        """
        Solve Google reCAPTCHA v2.
        
        Args:
            captcha_data: Dictionary containing:
                - website_url: URL where reCAPTCHA is embedded
                - site_key: reCAPTCHA site key
                - proxy: Optional proxy to use
        
        Returns:
            TokenSolution with reCAPTCHA token or None if failed
        """
        try:
            if not self.validate_input(captcha_data):
                return None
            
            cached_result = await cache_manager.get_cached_solution(captcha_data)
            if cached_result:
                logger.debug("Using cached reCAPTCHA v2 solution")
                return TokenSolution(**cached_result)
            
            website_url = captcha_data['website_url']
            site_key = captcha_data['site_key']
            proxy = captcha_data.get('proxy')
            
            if not proxy and proxy_manager.working_proxies:
                proxy = await proxy_manager.get_proxy()
            
            for attempt in range(self.max_attempts):
                try:
                    logger.info(f"Solving reCAPTCHA v2 attempt {attempt + 1}/{self.max_attempts}")
                    
                    context = await browser_manager.get_context(proxy=proxy)
                    await stealth_manager.setup_stealth_context(context)
                    
                    try:
                        page = await stealth_manager.create_stealth_page(context)
                        await stealth_manager.add_behavioral_fingerprint(page)
                        
                        token = await self._solve_recaptcha_v2_challenge(
                            page, website_url, site_key
                        )
                        
                        if token:
                            solution = TokenSolution(
                                token=token,
                                confidence=0.85
                            )
                            
                            await cache_manager.cache_captcha_solution(
                                captcha_data, solution.dict(), expire_minutes=20
                            )
                            
                            logger.info("reCAPTCHA v2 solved successfully")
                            return solution
                        
                    finally:
                        await context.close()
                    
                except Exception as e:
                    logger.warning(f"reCAPTCHA v2 attempt {attempt + 1} failed: {e}")
                    
                    if proxy:
                        proxy_manager.mark_proxy_failed(proxy)
                        proxy = await proxy_manager.get_proxy()
                    
                    if attempt < self.max_attempts - 1:
                        await asyncio.sleep(3)
            
            logger.error("All reCAPTCHA v2 solving attempts failed")
            return None
            
        except Exception as e:
            logger.error(f"Error solving reCAPTCHA v2: {e}")
            return None
    
    async def _solve_recaptcha_v2_challenge(
        self,
        page,
        website_url: str,
        site_key: str
    ) -> Optional[str]:
        """Solve reCAPTCHA v2 challenge on a specific page."""
        try:
            html_template = self._create_recaptcha_html(site_key)
            
            await page.route(website_url, lambda route: route.fulfill(
                body=html_template,
                status=200,
                content_type="text/html"
            ))
            
            await page.goto(website_url)
            
            recaptcha_frame_selector = 'iframe[src*="recaptcha"]'
            recaptcha_frame = await browser_manager.wait_for_element(
                page, recaptcha_frame_selector, timeout=15000
            )
            
            if not recaptcha_frame:
                logger.error("reCAPTCHA iframe not found")
                return None
            
            frame = await recaptcha_frame.content_frame()
            if not frame:
                logger.error("Could not access reCAPTCHA frame content")
                return None
            
            checkbox_selector = '.recaptcha-checkbox-border'
            checkbox = await browser_manager.wait_for_element(
                frame, checkbox_selector, timeout=10000
            )
            
            if not checkbox:
                logger.error("reCAPTCHA checkbox not found")
                return None
            
            await checkbox.click()
            logger.debug("Clicked reCAPTCHA checkbox")
            
            await asyncio.sleep(3)
            
            token = await self._get_recaptcha_token(page)
            if token:
                logger.debug("reCAPTCHA solved without challenge")
                return token
            
            challenge_frame_selector = 'iframe[src*="bframe"]'
            challenge_frame_element = await page.query_selector(challenge_frame_selector)
            
            if challenge_frame_element:
                logger.debug("reCAPTCHA image challenge detected")
                challenge_frame = await challenge_frame_element.content_frame()
                
                if challenge_frame:
                    success = await self._solve_image_challenge(challenge_frame)
                    if success:
                        for _ in range(30):
                            token = await self._get_recaptcha_token(page)
                            if token:
                                return token
                            await asyncio.sleep(1)
            
            for _ in range(self.timeout_seconds):
                token = await self._get_recaptcha_token(page)
                if token:
                    return token
                await asyncio.sleep(1)
            
            logger.warning("reCAPTCHA token not obtained within timeout")
            return None
            
        except Exception as e:
            logger.error(f"Error in reCAPTCHA v2 challenge solving: {e}")
            return None
    
    async def _get_recaptcha_token(self, page) -> Optional[str]:
        """Get reCAPTCHA token from the page."""
        try:
            token_element = await page.query_selector('textarea[name="g-recaptcha-response"]')
            if token_element:
                token = await token_element.get_attribute('value')
                if token and len(token) > 10:
                    return token
            return None
        except Exception as e:
            logger.debug(f"Error getting reCAPTCHA token: {e}")
            return None
    
    async def _solve_image_challenge(self, challenge_frame) -> bool:
        """Solve reCAPTCHA image challenge using YOLO object detection."""
        try:
            await stealth_manager.simulate_human_reading(challenge_frame, (1.0, 2.5))
            
            instruction_element = await challenge_frame.query_selector('.rc-imageselect-desc-no-canonical')
            if not instruction_element:
                instruction_element = await challenge_frame.query_selector('.rc-imageselect-desc')
            
            instruction = ""
            if instruction_element:
                instruction = await instruction_element.text_content()
                logger.debug(f"reCAPTCHA challenge instruction: {instruction}")
            
            target_objects = await self._parse_captcha_instruction(instruction)
            if not target_objects:
                logger.warning(f"Could not parse instruction: {instruction}")
                return await self._fallback_random_selection(challenge_frame)
            
            image_table = await challenge_frame.query_selector('.rc-imageselect-table')
            if not image_table:
                logger.warning("reCAPTCHA image table not found")
                return False
            
            image_cells = await challenge_frame.query_selector_all('.rc-imageselect-tile')
            
            if not image_cells:
                logger.warning("No reCAPTCHA image cells found")
                return False
            
            cells_to_click = []
            for i, cell in enumerate(image_cells):
                try:
                    img_element = await cell.query_selector('img')
                    if not img_element:
                        continue
                        
                    img_src = await img_element.get_attribute('src')
                    if not img_src:
                        continue
                    
                    should_click = await self._analyze_captcha_image(img_src, target_objects)
                    
                    if should_click:
                        cells_to_click.append((i, cell))
                        
                except Exception as e:
                    logger.debug(f"Error analyzing image cell {i}: {e}")
                    continue
            
            if cells_to_click:
                logger.info(f"Clicking {len(cells_to_click)} cells based on YOLO analysis")
                
                for i, (cell_idx, cell) in enumerate(cells_to_click):
                    try:
                        await stealth_manager.human_like_click(challenge_frame, f'.rc-imageselect-tile:nth-child({cell_idx + 1})')
                        
                        if i < len(cells_to_click) - 1:
                            await asyncio.sleep(random.uniform(0.3, 0.8))
                            
                    except Exception as e:
                        logger.debug(f"Error clicking cell {cell_idx}: {e}")
                        
            else:
                logger.warning("No cells selected by YOLO analysis, using fallback")
                return await self._fallback_random_selection(challenge_frame)
            
            await asyncio.sleep(random.uniform(0.5, 1.2))
            
            verify_button = await challenge_frame.query_selector('#recaptcha-verify-button')
            if verify_button:
                await stealth_manager.human_like_click(challenge_frame, '#recaptcha-verify-button')
                await asyncio.sleep(random.uniform(1.0, 2.0))
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error solving reCAPTCHA image challenge: {e}")
            return await self._fallback_random_selection(challenge_frame)
    
    async def _parse_captcha_instruction(self, instruction: str) -> List[str]:
        """Parse reCAPTCHA instruction to determine target objects."""
        if not instruction:
            return []
            
        instruction_lower = instruction.lower()
        target_objects = []
        
        for captcha_obj, yolo_classes in self.captcha_object_mappings.items():
            for keyword in [captcha_obj] + yolo_classes:
                if keyword in instruction_lower:
                    target_objects.append(captcha_obj)
                    break
                    
        if 'vehicle' in instruction_lower or 'vehicles' in instruction_lower:
            target_objects.extend(['car', 'bus', 'motorcycle', 'bicycle', 'truck'])
        
        if 'traffic' in instruction_lower:
            target_objects.extend(['traffic light', 'stop sign'])
            
        return list(set(target_objects))
    
    async def _analyze_captcha_image(self, img_src: str, target_objects: List[str]) -> bool:
        """Analyze a single CAPTCHA image using YOLO to determine if it should be clicked."""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(img_src)
                if response.status_code != 200:
                    return False
                    
                image_bytes = response.content
                
            import cv2
            import numpy as np
            nparr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                return False
                
            detections = await advanced_image_processor.detect_objects_yolo(
                image, 
                conf_threshold=self.confidence_threshold,
                target_classes=target_objects
            )
            
            for detection in detections:
                detected_class = detection['class_name'].lower()
                
                for target_obj in target_objects:
                    if target_obj in self.captcha_object_mappings:
                        yolo_classes = self.captcha_object_mappings[target_obj]
                        
                        for yolo_class in yolo_classes:
                            if yolo_class.lower() in detected_class or detected_class in yolo_class.lower():
                                logger.debug(f"Found {target_obj} in image: {detected_class} (confidence: {detection['confidence']:.2f})")
                                return True
                                
            return False
            
        except Exception as e:
            logger.debug(f"Error analyzing CAPTCHA image: {e}")
            return False
    
    async def _fallback_random_selection(self, challenge_frame) -> bool:
        """Fallback method using intelligent random selection."""
        try:
            logger.info("Using fallback random selection method")
            
            image_cells = await challenge_frame.query_selector_all('.rc-imageselect-tile')
            
            if not image_cells:
                return False
                
            num_to_click = random.randint(2, min(4, len(image_cells)))
            cells_to_click = random.sample(image_cells, num_to_click)
            
            for i, cell in enumerate(cells_to_click):
                try:
                    await stealth_manager.human_like_click(challenge_frame, f'.rc-imageselect-tile:nth-child({image_cells.index(cell) + 1})')
                    
                    if i < len(cells_to_click) - 1:
                        await asyncio.sleep(random.uniform(0.4, 0.9))
                        
                except Exception as e:
                    logger.debug(f"Error clicking fallback cell: {e}")
                    
            await asyncio.sleep(random.uniform(0.6, 1.3))
            verify_button = await challenge_frame.query_selector('#recaptcha-verify-button')
            if verify_button:
                await stealth_manager.human_like_click(challenge_frame, '#recaptcha-verify-button')
                await asyncio.sleep(random.uniform(1.0, 2.0))
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Fallback selection failed: {e}")
            return False
    
    def _create_recaptcha_html(self, site_key: str) -> str:
        """Create HTML template with reCAPTCHA widget."""
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>reCAPTCHA Challenge</title>
            <script src="https://www.google.com/recaptcha/api.js" async defer></script>
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
                .g-recaptcha {{
                    margin: 20px auto;
                    display: inline-block;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Please complete the security check</h2>
                <div class="g-recaptcha" 
                     data-sitekey="{site_key}"
                     data-theme="light"
                     data-size="normal">
                </div>
                <p id="status">Loading challenge...</p>
            </div>
            
            <script>
                // Monitor for token
                function checkToken() {{
                    const tokenInput = document.querySelector('textarea[name="g-recaptcha-response"]');
                    const status = document.getElementById('status');
                    
                    if (tokenInput && tokenInput.value) {{
                        status.textContent = 'Challenge completed!';
                        status.style.color = 'green';
                    }} else {{
                        setTimeout(checkToken, 500);
                    }}
                }}
                
                // Start monitoring after page load
                window.addEventListener('load', function() {{
                    setTimeout(checkToken, 2000);
                }});
                
                // reCAPTCHA callback
                function recaptchaCallback(token) {{
                    console.log('reCAPTCHA token received:', token);
                    document.getElementById('status').textContent = 'Challenge completed!';
                    document.getElementById('status').style.color = 'green';
                }}
                
                function recaptchaExpiredCallback() {{
                    console.log('reCAPTCHA expired');
                    document.getElementById('status').textContent = 'Challenge expired, please try again';
                    document.getElementById('status').style.color = 'orange';
                }}
                
                function recaptchaErrorCallback() {{
                    console.log('reCAPTCHA error');
                    document.getElementById('status').textContent = 'Challenge error, please try again';
                    document.getElementById('status').style.color = 'red';
                }}
            </script>
        </body>
        </html>
        """
    
    def validate_input(self, captcha_data: Dict[str, Any]) -> bool:
        """Validate input data for reCAPTCHA v2 solving."""
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
        
        return True
    
    async def _cleanup(self) -> None:
        """Clean up browser resources."""
        logger.debug("reCAPTCHA v2 solver cleanup completed")