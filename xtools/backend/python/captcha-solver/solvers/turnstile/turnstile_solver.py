import asyncio
import random
import time
from typing import Any, Dict, Optional, List, Tuple
from core.base_solver import BaseSolver
from models.base import CaptchaType
from models.responses import TokenSolution
from utils.browser_utils import browser_manager
from utils.proxy_utils import proxy_manager
from utils.logger import get_logger
from utils.cache_utils import cache_manager

logger = get_logger(__name__)


class TurnstileSolver(BaseSolver):
    """Advanced Cloudflare Turnstile CAPTCHA solver using browser automation with D3-vin techniques."""
    
    def __init__(self):
        super().__init__("TurnstileSolver", CaptchaType.TURNSTILE)
        self.max_attempts = 5
        self.timeout_seconds = 30
        self.browser_configs = self._get_browser_configs()
    
    def _get_browser_configs(self) -> Dict[str, Dict[str, str]]:
        """Get realistic browser configurations for anti-detection with 2024-2025 updates."""
        return {
            "chrome_131": {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "sec_ch_ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                "sec_ch_ua_platform": '"Windows"',
                "sec_ch_ua_mobile": "?0",
                "sec_ch_ua_full_version": '"131.0.6778.86"',
                "sec_ch_ua_arch": '"x86"',
                "sec_ch_ua_bitness": '"64"',
                "sec_ch_ua_model": '""'
            },
            "chrome_130": {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                "sec_ch_ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
                "sec_ch_ua_platform": '"Windows"',
                "sec_ch_ua_mobile": "?0",
                "sec_ch_ua_full_version": '"130.0.6723.117"',
                "sec_ch_ua_arch": '"x86"',
                "sec_ch_ua_bitness": '"64"',
                "sec_ch_ua_model": '""'
            },
            "edge_131": {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
                "sec_ch_ua": '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                "sec_ch_ua_platform": '"Windows"',
                "sec_ch_ua_mobile": "?0",
                "sec_ch_ua_full_version": '"131.0.2903.86"',
                "sec_ch_ua_arch": '"x86"',
                "sec_ch_ua_bitness": '"64"',
                "sec_ch_ua_model": '""'
            },
            "firefox_132": {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
                "sec_ch_ua": None,
                "sec_ch_ua_platform": None,
                "sec_ch_ua_mobile": None,
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "accept_language": "en-US,en;q=0.5",
                "accept_encoding": "gzip, deflate, br, zstd"
            },
            "safari_17": {
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
                "sec_ch_ua": None,
                "sec_ch_ua_platform": None,
                "sec_ch_ua_mobile": None,
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "accept_language": "en-US,en;q=0.9",
                "accept_encoding": "gzip, deflate, br"
            },
            "opera_115": {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 OPR/115.0.0.0",
                "sec_ch_ua": '"Opera";v="115", "Chromium";v="129", "Not=A?Brand";v="8"',
                "sec_ch_ua_platform": '"Windows"',
                "sec_ch_ua_mobile": "?0",
                "sec_ch_ua_full_version": '"115.0.5322.68"',
                "sec_ch_ua_arch": '"x86"',
                "sec_ch_ua_bitness": '"64"',
                "sec_ch_ua_model": '""'
            }
        }
    
    async def _initialize(self) -> None:
        """Initialize browser manager."""
        try:
            await browser_manager.initialize()
            logger.info("Turnstile solver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Turnstile solver: {e}")
            raise
    
    async def solve(self, captcha_data: Dict[str, Any]) -> Optional[TokenSolution]:
        """
        Solve Cloudflare Turnstile CAPTCHA using advanced D3-vin techniques.
        
        Args:
            captcha_data: Dictionary containing:
                - website_url: URL where Turnstile is embedded
                - site_key: Turnstile site key
                - action: Optional action parameter
                - cdata: Optional custom data
                - proxy: Optional proxy to use
        
        Returns:
            TokenSolution with Turnstile token or None if failed
        """
        try:
            if not self.validate_input(captcha_data):
                return None
            
            website_url = str(captcha_data['website_url'])
            site_key = captcha_data['site_key']
            
            cache_data = {
                'captcha_type': captcha_data['captcha_type'].value if hasattr(captcha_data['captcha_type'], 'value') else str(captcha_data['captcha_type']),
                'website_url': website_url,
                'site_key': site_key,
                'action': captcha_data.get('action'),
                'cdata': captcha_data.get('cdata'),
                'additional_data': captcha_data.get('additional_data', {}),
                'timeout': captcha_data.get('timeout', 120)
            }
            
            cached_result = await cache_manager.get_cached_solution(cache_data)
            if cached_result:
                logger.debug("Using cached Turnstile solution")
                return TokenSolution(**cached_result)
            
            action = captcha_data.get('action', '')
            cdata = captcha_data.get('cdata', '')
            proxy = captcha_data.get('proxy')
            
            if not proxy and proxy_manager.working_proxies:
                proxy = await proxy_manager.get_proxy()
            
            for attempt in range(self.max_attempts):
                try:
                    logger.info(f"Solving Turnstile attempt {attempt + 1}/{self.max_attempts}")
                    
                    browser_config = random.choice(list(self.browser_configs.values()))
                    
                    context = await self._get_advanced_context(proxy, browser_config)
                    
                    try:
                        page = await self._create_optimized_page(context)
                        
                        token = await self._solve_turnstile_advanced(
                            page, website_url, site_key, action, cdata, attempt
                        )
                        
                        if token:
                            solution = TokenSolution(
                                token=token,
                                confidence=0.95
                            )
                            
                            await cache_manager.cache_captcha_solution(
                                cache_data, solution.dict(), expire_minutes=30
                            )
                            
                            logger.info(f"Turnstile CAPTCHA solved successfully: {token[:20]}...")
                            return solution
                        
                    finally:
                        await context.close()
                    
                except Exception as e:
                    logger.warning(f"Turnstile attempt {attempt + 1} failed: {e}")
                    
                    if proxy:
                        proxy_manager.mark_proxy_failed(proxy)
                        proxy = await proxy_manager.get_proxy()
                    
                    if attempt < self.max_attempts - 1:
                        await asyncio.sleep(random.uniform(2, 4))
            
            logger.error("All Turnstile solving attempts failed")
            return None
            
        except Exception as e:
            logger.error(f"Error solving Turnstile CAPTCHA: {e}")
            return None
    
    async def _get_advanced_context(self, proxy: Optional[str], browser_config: Dict[str, str]):
        """Create browser context with advanced anti-detection configuration using 2024-2025 techniques."""
        context = await browser_manager.get_context(proxy=proxy)
        
        headers = {
            "user-agent": browser_config["user_agent"],
            "accept": browser_config.get("accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"),
            "accept-language": browser_config.get("accept_language", "en-US,en;q=0.9"),
            "accept-encoding": browser_config.get("accept_encoding", "gzip, deflate, br, zstd"),
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "cache-control": "max-age=0"
        }
        
        if browser_config.get("sec_ch_ua"):
            headers.update({
                "sec-ch-ua": browser_config["sec_ch_ua"],
                "sec-ch-ua-mobile": browser_config.get("sec_ch_ua_mobile", "?0"),
                "sec-ch-ua-platform": browser_config.get("sec_ch_ua_platform", '"Windows"'),
                "sec-ch-ua-arch": browser_config.get("sec_ch_ua_arch", '"x86"'),
                "sec-ch-ua-bitness": browser_config.get("sec_ch_ua_bitness", '"64"'),
                "sec-ch-ua-model": browser_config.get("sec_ch_ua_model", '""'),
                "sec-ch-ua-full-version": browser_config.get("sec_ch_ua_full_version", '""'),
                "sec-ch-ua-wow64": "?0",
                "sec-ch-ua-form-factors": '""',
                "sec-ch-prefers-color-scheme": "light",
                "sec-ch-prefers-reduced-motion": "no-preference"
            })
        
        await context.set_extra_http_headers(headers)
        
        await context.set_viewport_size({"width": 1920, "height": 1080})
        
        return context
    
    async def _create_optimized_page(self, context):
        """Create page with resource blocking for better performance."""
        page = await context.new_page()
        
        await page.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,eot}", 
                        lambda route: route.abort())
        await page.route("**/*.css", lambda route: route.abort())
        
        await page.add_init_script("""
            // Enhanced anti-detection script for 2024-2025
            
            // Remove webdriver property completely
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true
            });
            
            // Enhanced chrome object with realistic properties
            window.chrome = {
                runtime: {
                    onConnect: null,
                    onMessage: null,
                    onStartup: null,
                    onInstalled: null,
                    onSuspend: null,
                    onSuspendCanceled: null,
                    onUpdateAvailable: null,
                    onBrowserUpdateAvailable: null,
                    onRestartRequired: null,
                    onPerformanceWarning: null,
                    getBackgroundPage: function() {},
                    getManifest: function() { return {}; },
                    getURL: function(path) { return 'chrome-extension://invalid/' + path; },
                    connect: function() {},
                    sendMessage: function() {},
                    reload: function() {},
                    restart: function() {},
                    connectNative: function() {},
                    sendNativeMessage: function() {},
                    getPlatformInfo: function() {},
                    getPackageDirectoryEntry: function() {}
                },
                loadTimes: function() {
                    return {
                        requestTime: Date.now() / 1000 - Math.random() * 2,
                        startLoadTime: Date.now() / 1000 - Math.random() * 1.5,
                        commitLoadTime: Date.now() / 1000 - Math.random() * 1,
                        finishDocumentLoadTime: Date.now() / 1000 - Math.random() * 0.5,
                        finishLoadTime: Date.now() / 1000 - Math.random() * 0.2,
                        firstPaintTime: Date.now() / 1000 - Math.random() * 0.1,
                        firstPaintAfterLoadTime: 0,
                        navigationType: 'Other',
                        wasFetchedViaSpdy: false,
                        wasNpnNegotiated: false,
                        npnNegotiatedProtocol: 'unknown',
                        wasAlternateProtocolAvailable: false,
                        connectionInfo: 'http/1.1'
                    };
                },
                csi: function() {
                    return {
                        startE: Date.now() - Math.random() * 1000,
                        onloadT: Date.now() - Math.random() * 500,
                        pageT: Math.random() * 100 + 50,
                        tran: Math.floor(Math.random() * 20) + 1
                    };
                },
                app: {
                    isInstalled: false,
                    InstallState: {
                        DISABLED: 'disabled',
                        INSTALLED: 'installed',
                        NOT_INSTALLED: 'not_installed'
                    },
                    RunningState: {
                        CANNOT_RUN: 'cannot_run',
                        READY_TO_RUN: 'ready_to_run',
                        RUNNING: 'running'
                    }
                }
            };
            
            // Override permissions with realistic responses
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => {
                const permission = parameters.name;
                const states = ['granted', 'denied', 'prompt'];
                const defaultStates = {
                    'notifications': 'default',
                    'geolocation': 'prompt',
                    'camera': 'prompt',
                    'microphone': 'prompt',
                    'persistent-storage': 'prompt',
                    'push': 'prompt',
                    'midi': 'prompt'
                };
                
                return Promise.resolve({
                    state: defaultStates[permission] || 'prompt',
                    onchange: null
                });
            };
            
            // Override plugin detection
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    const plugins = [];
                    // Add realistic plugins for Chrome
                    plugins.push({
                        name: 'Chrome PDF Plugin',
                        filename: 'internal-pdf-viewer',
                        description: 'Portable Document Format',
                        length: 1
                    });
                    plugins.push({
                        name: 'Chrome PDF Viewer',
                        filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',
                        description: '',
                        length: 1
                    });
                    plugins.push({
                        name: 'Native Client',
                        filename: 'internal-nacl-plugin',
                        description: '',
                        length: 2
                    });
                    return plugins;
                }
            });
            
            // Override language detection
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // Override hardware concurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => Math.floor(Math.random() * 8) + 4
            });
            
            // Override device memory
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => [4, 8, 16][Math.floor(Math.random() * 3)]
            });
            
            // Override connection
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: Math.floor(Math.random() * 50) + 50,
                    downlink: Math.random() * 10 + 5,
                    saveData: false
                })
            });
            
            // Override screen properties with realistic values
            Object.defineProperty(screen, 'availWidth', {
                get: () => 1920
            });
            Object.defineProperty(screen, 'availHeight', {
                get: () => 1040
            });
            Object.defineProperty(screen, 'width', {
                get: () => 1920
            });
            Object.defineProperty(screen, 'height', {
                get: () => 1080
            });
            Object.defineProperty(screen, 'colorDepth', {
                get: () => 24
            });
            Object.defineProperty(screen, 'pixelDepth', {
                get: () => 24
            });
            
            // Override timezone
            const originalDateTimeFormat = Intl.DateTimeFormat;
            Intl.DateTimeFormat = function(...args) {
                if (args.length === 0) {
                    args = ['en-US'];
                }
                return new originalDateTimeFormat(...args);
            };
            
            // Override WebGL fingerprinting
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel(R) Iris(TM) Graphics 6100';
                }
                return getParameter.call(this, parameter);
            };
            
            // Override canvas fingerprinting
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(...args) {
                const result = originalToDataURL.apply(this, args);
                // Add slight randomization to canvas fingerprint
                return result.replace(/.$/, String.fromCharCode(Math.floor(Math.random() * 26) + 97));
            };
            
            // Override audio context fingerprinting
            const originalCreateAnalyser = AudioContext.prototype.createAnalyser;
            AudioContext.prototype.createAnalyser = function() {
                const analyser = originalCreateAnalyser.call(this);
                const originalGetFloatFrequencyData = analyser.getFloatFrequencyData;
                analyser.getFloatFrequencyData = function(array) {
                    originalGetFloatFrequencyData.call(this, array);
                    // Add slight noise to audio fingerprint
                    for (let i = 0; i < array.length; i++) {
                        array[i] += Math.random() * 0.0001 - 0.00005;
                    }
                };
                return analyser;
            };
            
            // Override battery API
            Object.defineProperty(navigator, 'getBattery', {
                get: () => () => Promise.resolve({
                    charging: Math.random() > 0.5,
                    chargingTime: Math.random() * 7200,
                    dischargingTime: Math.random() * 28800 + 3600,
                    level: Math.random() * 0.8 + 0.2
                })
            });
            
            // Override media devices
            Object.defineProperty(navigator, 'mediaDevices', {
                get: () => ({
                    enumerateDevices: () => Promise.resolve([
                        {
                            deviceId: 'default',
                            kind: 'audioinput',
                            label: 'Default - Microphone',
                            groupId: 'default'
                        },
                        {
                            deviceId: 'default',
                            kind: 'audiooutput',
                            label: 'Default - Speaker',
                            groupId: 'default'
                        }
                    ]),
                    getUserMedia: () => Promise.reject(new Error('Permission denied'))
                })
            });
            
            // Remove automation indicators
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_JSON;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Object;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Proxy;
            
            // Override toString methods to hide modifications
            const originalToString = Function.prototype.toString;
            Function.prototype.toString = function() {
                if (this === navigator.permissions.query) {
                    return 'function query() { [native code] }';
                }
                if (this === HTMLCanvasElement.prototype.toDataURL) {
                    return 'function toDataURL() { [native code] }';
                }
                return originalToString.call(this);
            };
        """)
        
        return page
    
    async def _solve_turnstile_advanced(
        self,
        page,
        website_url: str,
        site_key: str,
        action: str,
        cdata: str,
        attempt: int
    ) -> Optional[str]:
        """Solve Turnstile challenge using advanced D3-vin techniques."""
        try:
            start_time = time.time()
            logger.debug(f"Starting Turnstile solve for URL: {website_url} with Sitekey: {site_key}")
            
            await page.goto(website_url, wait_until='domcontentloaded', timeout=30000)
            
            await asyncio.sleep(3)
            
            token_selector = 'input[name="cf-turnstile-response"]'
            max_token_attempts = 20
            
            for token_attempt in range(max_token_attempts):
                try:
                    token = await self._check_for_tokens(page, token_selector)
                    if token:
                        elapsed_time = round(time.time() - start_time, 3)
                        logger.info(f"Turnstile token obtained: {token[:20]}... in {elapsed_time}s")
                        return token
                    
                    if token_attempt > 2 and token_attempt % 3 == 0:
                        click_success = await self._try_click_strategies(page, site_key)
                        if not click_success:
                            logger.debug(f"Click strategies failed on attempt {token_attempt + 1}")
                    
                    if token_attempt == 10:
                        await self._create_turnstile_overlay(page, site_key, action, cdata)
                        logger.debug("Created fallback Turnstile overlay")
                    
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.debug(f"Token detection attempt {token_attempt + 1} failed: {e}")
                    await asyncio.sleep(1)
            
            logger.warning("Turnstile token not obtained within timeout")
            return None
            
        except Exception as e:
            logger.error(f"Error in advanced Turnstile solving: {e}")
            return None
    
    async def _check_for_tokens(self, page, token_selector: str) -> Optional[str]:
        """Advanced token detection with multiple element checking."""
        try:
            elements = await page.query_selector_all(token_selector)
            
            if not elements:
                return None
            
            for element in elements:
                try:
                    token = await element.get_attribute('value')
                    if token and len(token) > 10:
                        return token
                except Exception as e:
                    logger.debug(f"Error checking token element: {e}")
                    continue
            
            return None
            
        except Exception as e:
            logger.debug(f"Error in token detection: {e}")
            return None
    
    async def _try_click_strategies(self, page, site_key: str) -> bool:
        """Try multiple click strategies like D3-vin's implementation."""
        strategies = [
            ('direct_widget', lambda: self._safe_click(page, '.cf-turnstile')),
            ('sitekey_attr', lambda: self._safe_click(page, f'[data-sitekey="{site_key}"]')),
            ('iframe_click', lambda: self._safe_click(page, 'iframe[src*="turnstile"]')),
            ('any_turnstile', lambda: self._safe_click(page, '*[class*="turnstile"]')),
            ('js_click', lambda: page.evaluate("document.querySelector('.cf-turnstile')?.click()")),
            ('checkbox_click', lambda: self._find_and_click_checkbox(page))
        ]
        
        for strategy_name, strategy_func in strategies:
            try:
                result = await strategy_func()
                if result is not False:
                    logger.debug(f"Click strategy '{strategy_name}' succeeded")
                    return True
            except Exception as e:
                logger.debug(f"Click strategy '{strategy_name}' failed: {e}")
                continue
        
        return False
    
    async def _safe_click(self, page, selector: str) -> bool:
        """Safe click with error handling."""
        try:
            element = await page.query_selector(selector)
            if element:
                await element.click(timeout=1000)
                return True
            return False
        except Exception as e:
            logger.debug(f"Safe click failed for '{selector}': {e}")
            return False
    
    async def _find_and_click_checkbox(self, page) -> bool:
        """Find and click Turnstile checkbox."""
        try:
            frames = page.frames
            for frame in frames:
                try:
                    if 'turnstile' in frame.url:
                        checkbox = await frame.query_selector('input[type="checkbox"]')
                        if checkbox:
                            await checkbox.click()
                            return True
                except Exception as e:
                    logger.debug(f"Checkbox click in frame failed: {e}")
                    continue
            return False
        except Exception as e:
            logger.debug(f"Checkbox search failed: {e}")
            return False
    
    async def _create_turnstile_overlay(self, page, site_key: str, action: str, cdata: str):
        """Create Turnstile overlay as fallback."""
        script = f"""
        const existing = document.querySelector('#captcha-overlay');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.id = 'captcha-overlay';
        overlay.style.position = 'fixed';
        overlay.style.top = '0';
        overlay.style.left = '0';
        overlay.style.width = '100vw';
        overlay.style.height = '100vh';
        overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
        overlay.style.display = 'flex';
        overlay.style.justifyContent = 'center';
        overlay.style.alignItems = 'center';
        overlay.style.zIndex = '10000';

        const captchaDiv = document.createElement('div');
        captchaDiv.className = 'cf-turnstile';
        captchaDiv.setAttribute('data-sitekey', '{site_key}');
        captchaDiv.setAttribute('data-callback', 'onCaptchaSuccess');
        captchaDiv.setAttribute('data-action', '{action}');
        captchaDiv.setAttribute('data-cdata', '{cdata}');

        overlay.appendChild(captchaDiv);
        document.body.appendChild(overlay);

        // Load Turnstile script if not already loaded
        if (!document.querySelector('script[src*="turnstile"]')) {{
            const script = document.createElement('script');
            script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js';
            script.async = true;
            script.defer = true;
            document.head.appendChild(script);
        }}
        """
        
        await page.evaluate(script)
    

    def validate_input(self, captcha_data: Dict[str, Any]) -> bool:
        """Validate input data for Turnstile solving."""
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
        logger.debug("Turnstile solver cleanup completed")