import asyncio
import numpy as np
from typing import Any, Dict, Optional, List
from core.base_solver import BaseSolver
from models.base import CaptchaType
from models.responses import TokenSolution
from utils.browser_utils import browser_manager
from utils.proxy_utils import proxy_manager
from utils.logger import get_logger
from utils.cache_utils import cache_manager

logger = get_logger(__name__)


class ArkoseSolver(BaseSolver):
    """Arkose Labs/FunCAPTCHA solver using browser automation."""
    
    def __init__(self):
        super().__init__("ArkoseSolver", CaptchaType.ARKOSE)
        self.max_attempts = 3
        self.timeout_seconds = 120
    
    async def _initialize(self) -> None:
        """Initialize browser manager."""
        try:
            await browser_manager.initialize()
            logger.info("Arkose solver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Arkose solver: {e}")
            raise
    
    async def solve(self, captcha_data: Dict[str, Any]) -> Optional[TokenSolution]:
        """
        Solve Arkose Labs/FunCAPTCHA.
        
        Args:
            captcha_data: Dictionary containing:
                - website_url: URL where FunCAPTCHA is embedded
                - public_key: FunCAPTCHA public key
                - blob_data: Optional blob data
                - subdomain: Optional subdomain
                - proxy: Optional proxy to use
        
        Returns:
            TokenSolution with FunCAPTCHA token or None if failed
        """
        try:
            if not self.validate_input(captcha_data):
                return None
            
            cached_result = await cache_manager.get_cached_solution(captcha_data)
            if cached_result:
                logger.debug("Using cached Arkose solution")
                return TokenSolution(**cached_result)
            
            website_url = captcha_data['website_url']
            public_key = captcha_data['public_key']
            blob_data = captcha_data.get('blob_data')
            subdomain = captcha_data.get('subdomain', 'client-api')
            proxy = captcha_data.get('proxy')
            
            if not proxy and proxy_manager.working_proxies:
                proxy = await proxy_manager.get_proxy()
            
            for attempt in range(self.max_attempts):
                try:
                    logger.info(f"Solving Arkose attempt {attempt + 1}/{self.max_attempts}")
                    
                    context = await browser_manager.get_context(proxy=proxy)
                    
                    try:
                        page = await browser_manager.create_stealth_page(context)
                        
                        token = await self._solve_arkose_challenge(
                            page, website_url, public_key, blob_data, subdomain
                        )
                        
                        if token:
                            solution = TokenSolution(
                                token=token,
                                confidence=0.8
                            )
                            
                            await cache_manager.cache_captcha_solution(
                                captcha_data, solution.dict(), expire_minutes=25
                            )
                            
                            logger.info("Arkose CAPTCHA solved successfully")
                            return solution
                        
                    finally:
                        await context.close()
                    
                except Exception as e:
                    logger.warning(f"Arkose attempt {attempt + 1} failed: {e}")
                    
                    if proxy:
                        proxy_manager.mark_proxy_failed(proxy)
                        proxy = await proxy_manager.get_proxy()
                    
                    if attempt < self.max_attempts - 1:
                        await asyncio.sleep(5)
            
            logger.error("All Arkose solving attempts failed")
            return None
            
        except Exception as e:
            logger.error(f"Error solving Arkose CAPTCHA: {e}")
            return None
    
    async def _solve_arkose_challenge(
        self,
        page,
        website_url: str,
        public_key: str,
        blob_data: Optional[str] = None,
        subdomain: str = "client-api"
    ) -> Optional[str]:
        """Solve Arkose challenge on a specific page."""
        try:
            html_template = self._create_arkose_html(public_key, blob_data, subdomain)
            
            await page.route(website_url, lambda route: route.fulfill(
                body=html_template,
                status=200,
                content_type="text/html"
            ))
            
            await page.goto(website_url)
            
            await asyncio.sleep(5)
            
            funcaptcha_iframe = await browser_manager.wait_for_element(
                page, 'iframe[src*="funcaptcha.com"]', timeout=15000
            )
            
            if not funcaptcha_iframe:
                logger.error("FunCAPTCHA iframe not found")
                return None
            
            frame = await funcaptcha_iframe.content_frame()
            if not frame:
                logger.error("Could not access FunCAPTCHA frame content")
                return None
            
            await asyncio.sleep(3)
            
            challenge_container = await frame.query_selector('#fc-iframe-wrap')
            if not challenge_container:
                challenge_container = await frame.query_selector('.fc-challenge-container')
            
            if challenge_container:
                logger.debug("FunCAPTCHA challenge detected")
                
                success = await self._solve_funcaptcha_challenge(frame)
                
                if success:
                    for _ in range(60):
                        token = await self._get_arkose_token(page)
                        if token:
                            return token
                        await asyncio.sleep(1)
            else:
                await asyncio.sleep(2)
                token = await self._get_arkose_token(page)
                if token:
                    logger.debug("Arkose solved without challenge")
                    return token
            
            logger.warning("Arkose token not obtained within timeout")
            return None
            
        except Exception as e:
            logger.error(f"Error in Arkose challenge solving: {e}")
            return None
    
    async def _solve_funcaptcha_challenge(self, frame) -> bool:
        """Attempt to solve FunCAPTCHA challenge using computer vision."""
        try:
            await asyncio.sleep(3)
            
            instruction_element = await frame.query_selector('.fc-instructions')
            instruction = ""
            if instruction_element:
                instruction = await instruction_element.text_content()
                logger.debug(f"FunCAPTCHA instruction: {instruction}")
            
            clickable_elements = await frame.query_selector_all('.fc-image-tile')
            
            if not clickable_elements:
                clickable_elements = await frame.query_selector_all('[role="button"]')
                if not clickable_elements:
                    clickable_elements = await frame.query_selector_all('.fc-tile')
            
            if clickable_elements:
                correct_elements = await self._analyze_funcaptcha_images(
                    frame, clickable_elements, instruction
                )
                
                if correct_elements:
                    for element in correct_elements:
                        try:
                            await element.click()
                            await asyncio.sleep(0.5)
                        except Exception as e:
                            logger.debug(f"Error clicking FunCAPTCHA element: {e}")
                else:
                    elements_to_click = await self._intelligent_guess(
                        clickable_elements, instruction
                    )
                    
                    for element in elements_to_click:
                        try:
                            await element.click()
                            await asyncio.sleep(0.5)
                        except Exception as e:
                            logger.debug(f"Error clicking FunCAPTCHA element: {e}")
                
                submit_button = await frame.query_selector('.fc-button-submit')
                if not submit_button:
                    submit_button = await frame.query_selector('[type="submit"]')
                    if not submit_button:
                        submit_button = await frame.query_selector('.fc-submit')
                
                if submit_button:
                    await submit_button.click()
                    await asyncio.sleep(2)
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error solving FunCAPTCHA challenge: {e}")
            return False
    
    async def _analyze_funcaptcha_images(self, frame, elements, instruction: str) -> List:
        """Analyze FunCAPTCHA images using computer vision."""
        try:
            from utils.advanced_image_utils import AdvancedImageProcessor
            import base64
            
            correct_elements = []
            image_processor = AdvancedImageProcessor()
            
            target_objects = await self._parse_funcaptcha_instruction(instruction)
            
            if not target_objects:
                return []
            
            for element in elements:
                try:
                    image_data = await self._extract_element_image(frame, element)
                    
                    if image_data:
                        image = image_processor.decode_base64_image(image_data)
                        
                        if await self._image_contains_objects(image, target_objects):
                            correct_elements.append(element)
                            
                except Exception as e:
                    logger.debug(f"Error analyzing FunCAPTCHA image: {e}")
                    continue
            
            return correct_elements
            
        except Exception as e:
            logger.debug(f"Error in FunCAPTCHA image analysis: {e}")
            return []
    
    async def _parse_funcaptcha_instruction(self, instruction: str) -> List[str]:
        """Parse FunCAPTCHA instruction to identify target objects with enhanced 2024-2025 patterns."""
        instruction = instruction.lower()
        
        object_patterns = {
            'animal': [
                'animal', 'animals', 'dog', 'cat', 'bird', 'horse', 'elephant', 'lion', 'tiger',
                'bear', 'wolf', 'fox', 'rabbit', 'deer', 'cow', 'pig', 'sheep', 'goat',
                'monkey', 'ape', 'zebra', 'giraffe', 'hippo', 'rhino', 'kangaroo', 'koala',
                'panda', 'penguin', 'owl', 'eagle', 'parrot', 'duck', 'chicken', 'fish',
                'shark', 'whale', 'dolphin', 'octopus', 'crab', 'lobster', 'butterfly',
                'bee', 'spider', 'snake', 'lizard', 'frog', 'turtle'
            ],
            'vehicle': [
                'vehicle', 'car', 'truck', 'bus', 'motorcycle', 'bike', 'bicycle', 'scooter',
                'van', 'suv', 'sedan', 'coupe', 'convertible', 'pickup', 'trailer', 'semi',
                'taxi', 'police car', 'ambulance', 'fire truck', 'tractor', 'bulldozer',
                'excavator', 'crane', 'forklift', 'boat', 'ship', 'yacht', 'sailboat',
                'submarine', 'airplane', 'jet', 'helicopter', 'drone', 'rocket', 'train',
                'subway', 'tram', 'trolley'
            ],
            'person': [
                'person', 'people', 'human', 'man', 'woman', 'child', 'baby', 'boy', 'girl',
                'adult', 'teenager', 'elderly', 'senior', 'worker', 'doctor', 'nurse',
                'teacher', 'student', 'police', 'firefighter', 'soldier', 'chef', 'waiter',
                'athlete', 'musician', 'artist', 'dancer', 'actor', 'face', 'head', 'body'
            ],
            'building': [
                'building', 'house', 'home', 'apartment', 'condo', 'mansion', 'cottage',
                'cabin', 'hut', 'palace', 'castle', 'tower', 'skyscraper', 'office',
                'store', 'shop', 'mall', 'restaurant', 'cafe', 'hotel', 'motel', 'hospital',
                'school', 'university', 'library', 'museum', 'theater', 'cinema', 'church',
                'temple', 'mosque', 'synagogue', 'factory', 'warehouse', 'barn', 'garage',
                'bridge', 'tunnel', 'stadium', 'arena'
            ],
            'nature': [
                'tree', 'trees', 'forest', 'woods', 'jungle', 'flower', 'flowers', 'plant',
                'plants', 'grass', 'leaf', 'leaves', 'branch', 'trunk', 'root', 'mountain',
                'mountains', 'hill', 'valley', 'cliff', 'rock', 'stone', 'boulder', 'cave',
                'water', 'ocean', 'sea', 'lake', 'river', 'stream', 'waterfall', 'beach',
                'sand', 'desert', 'sky', 'cloud', 'clouds', 'sun', 'moon', 'star', 'stars',
                'rainbow', 'lightning', 'snow', 'ice', 'fire', 'flame'
            ],
            'food': [
                'food', 'fruit', 'fruits', 'apple', 'banana', 'orange', 'grape', 'strawberry',
                'cherry', 'peach', 'pear', 'pineapple', 'watermelon', 'lemon', 'lime',
                'vegetable', 'vegetables', 'carrot', 'potato', 'tomato', 'onion', 'pepper',
                'cucumber', 'lettuce', 'cabbage', 'broccoli', 'corn', 'peas', 'beans',
                'bread', 'cake', 'cookie', 'pie', 'pizza', 'burger', 'sandwich', 'pasta',
                'rice', 'noodles', 'soup', 'salad', 'meat', 'chicken', 'beef', 'pork',
                'fish', 'cheese', 'milk', 'egg', 'eggs', 'ice cream', 'chocolate', 'candy'
            ],
            'object': [
                'chair', 'table', 'desk', 'bed', 'sofa', 'couch', 'bench', 'stool', 'shelf',
                'cabinet', 'drawer', 'closet', 'wardrobe', 'mirror', 'lamp', 'light',
                'book', 'books', 'newspaper', 'magazine', 'pen', 'pencil', 'paper',
                'phone', 'telephone', 'mobile', 'smartphone', 'computer', 'laptop',
                'tablet', 'keyboard', 'mouse', 'monitor', 'screen', 'tv', 'television',
                'radio', 'camera', 'watch', 'clock', 'calendar', 'bag', 'purse', 'wallet',
                'key', 'keys', 'lock', 'door', 'window', 'bottle', 'cup', 'glass', 'plate',
                'bowl', 'spoon', 'fork', 'knife', 'tool', 'tools', 'hammer', 'screwdriver',
                'wrench', 'saw', 'drill', 'nail', 'screw', 'rope', 'chain', 'wire',
                'ball', 'toy', 'game', 'puzzle', 'dice', 'card', 'cards'
            ],
            'upright': [
                'upright', 'right way up', 'correct orientation', 'normal', 'straight',
                'vertical', 'standing', 'proper', 'correct', 'right side up', 'not rotated',
                'not tilted', 'not sideways', 'not upside down'
            ],
            'rotated': [
                'rotated', 'tilted', 'sideways', 'upside down', 'inverted', 'flipped',
                'turned', 'angled', 'diagonal', 'slanted', 'crooked', 'wrong way',
                'incorrect orientation', 'not upright', 'not straight'
            ],
            'direction': [
                'left', 'right', 'up', 'down', 'north', 'south', 'east', 'west',
                'forward', 'backward', 'clockwise', 'counterclockwise', 'horizontal',
                'vertical', 'diagonal'
            ],
            'color': [
                'red', 'blue', 'green', 'yellow', 'orange', 'purple', 'pink', 'brown',
                'black', 'white', 'gray', 'grey', 'silver', 'gold', 'cyan', 'magenta',
                'maroon', 'navy', 'olive', 'lime', 'aqua', 'teal', 'fuchsia'
            ],
            'shape': [
                'circle', 'square', 'triangle', 'rectangle', 'oval', 'diamond', 'star',
                'heart', 'arrow', 'cross', 'plus', 'minus', 'line', 'curve', 'spiral',
                'polygon', 'hexagon', 'octagon', 'pentagon'
            ],
            'number': [
                'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight',
                'nine', 'ten', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10',
                'number', 'numbers', 'digit', 'digits', 'count', 'amount', 'quantity'
            ],
            'text': [
                'letter', 'letters', 'word', 'words', 'text', 'alphabet', 'character',
                'characters', 'symbol', 'symbols', 'sign', 'signs', 'label', 'title',
                'caption', 'heading'
            ]
        }
        
        target_objects = []
        confidence_scores = {}
        
        for category, keywords in object_patterns.items():
            max_confidence = 0
            for keyword in keywords:
                if keyword in instruction:
                    confidence = len(keyword) / len(instruction) * 100
                    if keyword == instruction.strip():
                        confidence *= 2
                    max_confidence = max(max_confidence, confidence)
            
            if max_confidence > 0:
                confidence_scores[category] = max_confidence
                target_objects.append(category)
        
        if confidence_scores:
            sorted_objects = sorted(target_objects, key=lambda x: confidence_scores[x], reverse=True)
            logger.debug(f"Parsed instruction '{instruction}' -> objects: {sorted_objects[:3]}")
            return sorted_objects[:3]
        
        return target_objects
    
    async def _extract_element_image(self, frame, element) -> Optional[str]:
        """Extract image data from a FunCAPTCHA element."""
        try:
            img_element = await element.query_selector('img')
            if img_element:
                src = await img_element.get_attribute('src')
                if src and src.startswith('data:image'):
                    return src.split(',')[1]
            
            style = await element.get_attribute('style')
            if style and 'background-image' in style:
                import re
                url_match = re.search(r'url\(["\']?(data:image[^"\']+)["\']?\)', style)
                if url_match:
                    return url_match.group(1).split(',')[1]
            
            screenshot = await element.screenshot()
            if screenshot:
                import base64
                return base64.b64encode(screenshot).decode('utf-8')
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting element image: {e}")
            return None
    
    async def _image_contains_objects(self, image: np.ndarray, target_objects: List[str]) -> bool:
        """Check if image contains any of the target objects."""
        try:
            
            if 'upright' in target_objects:
                return await self._is_image_upright(image)
            
            if 'rotated' in target_objects:
                return not await self._is_image_upright(image)
            
            return len(target_objects) > 0
            
        except Exception as e:
            logger.debug(f"Error checking image objects: {e}")
            return False
    
    async def _is_image_upright(self, image: np.ndarray) -> bool:
        """Check if image is in upright orientation."""
        try:
            from utils.advanced_image_utils import AdvancedImageProcessor
            
            angle = AdvancedImageProcessor.detect_rotation_angle(image)
            
            return abs(angle) < 15
            
        except Exception as e:
            logger.debug(f"Error checking image orientation: {e}")
            return True
    
    async def _intelligent_guess(self, elements, instruction: str) -> List:
        """Make an intelligent guess when computer vision fails."""
        try:
            instruction = instruction.lower()
            
            if 'upright' in instruction or 'correct' in instruction:
                import random
                num_to_select = min(3, max(2, len(elements) // 2))
                return random.sample(elements, num_to_select)
            
            elif 'animal' in instruction or 'vehicle' in instruction:
                import random
                num_to_select = min(4, max(3, len(elements) // 2))
                return random.sample(elements, num_to_select)
            
            else:
                import random
                num_to_select = max(1, len(elements) // 2)
                return random.sample(elements, num_to_select)
            
        except Exception as e:
            logger.debug(f"Error in intelligent guessing: {e}")
            import random
            return random.sample(elements, min(2, len(elements)))
    
    async def _get_arkose_token(self, page) -> Optional[str]:
        """Get Arkose token from the page."""
        try:
            token_selectors = [
                'input[name="fc-token"]',
                'input[name="arkose-token"]',
                'input[name="funcaptcha-token"]',
                '[data-arkose-token]'
            ]
            
            for selector in token_selectors:
                token_element = await page.query_selector(selector)
                if token_element:
                    token = await token_element.get_attribute('value')
                    if not token:
                        token = await token_element.get_attribute('data-arkose-token')
                    
                    if token and len(token) > 10:
                        return token
            
            token = await page.evaluate("""
                () => {
                    if (window.arkoseToken) return window.arkoseToken;
                    if (window.fcToken) return window.fcToken;
                    if (window.funcaptchaToken) return window.funcaptchaToken;
                    return null;
                }
            """)
            
            if token and len(token) > 10:
                return token
            
            return None
            
        except Exception as e:
            logger.debug(f"Error getting Arkose token: {e}")
            return None
    
    def _create_arkose_html(
        self, 
        public_key: str, 
        blob_data: Optional[str] = None,
        subdomain: str = "client-api"
    ) -> str:
        """Create HTML template with FunCAPTCHA widget."""
        blob_attr = f' data-blob="{blob_data}"' if blob_data else ''
        
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>FunCAPTCHA Challenge</title>
            <script src="https://{subdomain}.funcaptcha.com/fc/api/nojs/?pkey={public_key}" async defer></script>
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
                #funcaptcha {{
                    margin: 20px auto;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Please complete the security verification</h2>
                <div id="funcaptcha" 
                     data-pkey="{public_key}"
                     data-surl="https://{subdomain}.funcaptcha.com"
                     data-theme="light"{blob_attr}>
                </div>
                <p id="status">Loading verification...</p>
            </div>
            
            <script>
                // Monitor for token
                function checkToken() {{
                    const tokenInput = document.querySelector('input[name="fc-token"]');
                    const status = document.getElementById('status');
                    
                    if (tokenInput && tokenInput.value) {{
                        status.textContent = 'Verification completed!';
                        status.style.color = 'green';
                        window.arkoseToken = tokenInput.value;
                    }} else {{
                        setTimeout(checkToken, 1000);
                    }}
                }}
                
                // Start monitoring after page load
                window.addEventListener('load', function() {{
                    setTimeout(checkToken, 3000);
                }});
                
                // FunCAPTCHA callbacks
                function funcaptchaCallback(token) {{
                    console.log('FunCAPTCHA token received:', token);
                    document.getElementById('status').textContent = 'Verification completed!';
                    document.getElementById('status').style.color = 'green';
                    window.arkoseToken = token;
                }}
                
                function funcaptchaErrorCallback(error) {{
                    console.error('FunCAPTCHA error:', error);
                    document.getElementById('status').textContent = 'Verification failed: ' + error;
                    document.getElementById('status').style.color = 'red';
                }}
            </script>
        </body>
        </html>
        """
    
    def validate_input(self, captcha_data: Dict[str, Any]) -> bool:
        """Validate input data for Arkose solving."""
        if not captcha_data.get('website_url'):
            logger.error("No website URL provided")
            return False
        
        if not captcha_data.get('public_key'):
            logger.error("No public key provided")
            return False
        
        public_key = captcha_data['public_key']
        if not isinstance(public_key, str) or len(public_key) < 10:
            logger.error("Invalid public key format")
            return False
        
        return True
    
    async def _cleanup(self) -> None:
        """Clean up browser resources."""
        logger.debug("Arkose solver cleanup completed")