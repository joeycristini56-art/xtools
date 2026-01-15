"""
Production-Grade DataDome Solver
===============================
Advanced DataDome bypass implementation using device fingerprinting,
Safari iOS impersonation, and comprehensive anti-detection techniques.
"""

import asyncio
import json
import time
import random
import hashlib
import uuid
from typing import Any, Dict, Optional
from dataclasses import dataclass
from urllib.parse import urlencode, urlparse

try:
    import curl_cffi
    from curl_cffi import requests as cf_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    import requests

from core.base_solver import BaseSolver
from models.base import CaptchaType
from models.responses import TokenSolution
from utils.proxy_utils import proxy_manager
from utils.logger import get_logger
from utils.cache_utils import cache_manager

logger = get_logger(__name__)


@dataclass
class DeviceProfile:
    """iOS Device Profile for realistic DataDome fingerprinting"""
    device_id: str
    vendor_id: str
    app_guid: str
    session_id: str
    device_model: str
    os_version: str
    app_version: str
    screen_width: int
    screen_height: int
    scale: float
    timezone: str
    locale: str
    carrier: str
    network_type: str


class iOSDeviceGenerator:
    """Generate realistic iOS device profiles for DataDome bypass"""
    
    DEVICE_MODELS = [
        "iPhone16,1", "iPhone16,2",
        "iPhone15,2", "iPhone15,3", "iPhone15,4", "iPhone15,5",
        "iPhone14,2", "iPhone14,3", "iPhone14,4", "iPhone14,5",
        "iPhone13,1", "iPhone13,2", "iPhone13,3", "iPhone13,4",
    ]
    
    IOS_VERSIONS = [
        "18.1.1", "18.1", "18.0.1", "18.0",
        "17.7.2", "17.7.1", "17.6.1", "17.5.1",
        "17.2.1", "17.2", "17.1.2", "17.1.1"
    ]
    
    CARRIERS = ["Verizon", "AT&T", "T-Mobile", "Sprint", "Visible", "Mint Mobile"]
    TIMEZONES = ["America/New_York", "America/Los_Angeles", "America/Chicago", "America/Denver"]
    
    @classmethod
    def generate_device_profile(cls) -> DeviceProfile:
        """Generate a realistic iOS device profile"""
        device_id = str(uuid.uuid4()).upper()
        vendor_id = str(uuid.uuid4()).upper()
        app_guid = str(uuid.uuid4()).upper()
        session_id = str(uuid.uuid4()).upper()
        
        return DeviceProfile(
            device_id=device_id,
            vendor_id=vendor_id,
            app_guid=app_guid,
            session_id=session_id,
            device_model=random.choice(cls.DEVICE_MODELS),
            os_version=random.choice(cls.IOS_VERSIONS),
            app_version="18.1.0",
            screen_width=random.choice([375, 390, 414, 428]),
            screen_height=random.choice([667, 844, 896, 926]),
            scale=random.choice([2.0, 3.0]),
            timezone=random.choice(cls.TIMEZONES),
            locale="en_US",
            carrier=random.choice(cls.CARRIERS),
            network_type=random.choice(["WiFi", "4G", "5G"])
        )


class DataDomeSolver(BaseSolver):
    """Advanced DataDome CAPTCHA solver using comprehensive device fingerprinting and Safari iOS impersonation."""
    
    def __init__(self):
        super().__init__("DataDomeSolver", CaptchaType.DATADOME)
        self.max_attempts = 3
        self.timeout_seconds = 30
        self.session = None
        self.impersonate_profile = "safari_ios"
        
        if not CURL_CFFI_AVAILABLE:
            logger.warning("curl_cffi not available, falling back to requests (reduced effectiveness)")
    
    async def _initialize(self) -> None:
        """Initialize DataDome solver with curl_cffi session."""
        try:
            if CURL_CFFI_AVAILABLE:
                self.session = cf_requests.Session()
                self.session.headers.update({
                    'Connection': 'keep-alive',
                    'Keep-Alive': 'timeout=30, max=100'
                })
                logger.info(f"DataDome solver initialized with {self.impersonate_profile} impersonation")
            else:
                self.session = requests.Session()
                logger.info("DataDome solver initialized with fallback requests session")
                
        except Exception as e:
            logger.error(f"Failed to initialize DataDome solver: {e}")
            raise
    
    def get_ios_headers(self, device: DeviceProfile, request_type: str = "initial") -> Dict[str, str]:
        """Generate realistic iOS Safari headers with dynamic rotation"""
        base_headers = {
            'User-Agent': f'Mozilla/5.0 (iPhone; CPU iPhone OS {device.os_version.replace(".", "_")} like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Accept': '*/*',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        if request_type == "initial":
            base_headers.update({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1'
            })
        elif request_type == "api":
            base_headers.update({
                'Accept': 'application/json, text/plain, */*',
                'Content-Type': 'application/json',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin'
            })
        
        base_headers.update({
            'X-Device-ID': device.device_id,
            'X-App-GUID': device.app_guid,
            'X-Session-ID': device.session_id,
            'X-Device-Model': device.device_model,
            'X-OS-Version': device.os_version,
            'X-App-Version': device.app_version,
            'X-Internal-Hash': hashlib.md5(f"{device.device_id}{int(time.time())}".encode()).hexdigest()
        })
        
        return base_headers
    
    def _generate_risk_data(self, device: DeviceProfile) -> str:
        """Generate comprehensive risk data payload for DataDome with 2024-2025 enhancements"""
        risk_data = {
            "total_storage_space": random.randint(60000000000, 256000000000),
            "linker_id": str(uuid.uuid4()),
            "bindSchemeEnrolled": "none",
            "local_identifier": str(uuid.uuid4()),
            "screen": {
                "brightness": str(random.randint(30, 100)),
                "height": device.screen_height,
                "mirror": False,
                "scale": str(device.scale),
                "capture": 0,
                "width": device.screen_width,
                "max_frames": random.choice([60, 120]),
                "color_depth": 24,
                "pixel_ratio": device.scale,
                "orientation": "portrait"
            },
            "conf_version": "6.2",
            "timestamp": int(time.time() * 1000),
            "comp_version": "6.8.1",
            "os_type": "iOS",
            "is_rooted": False,
            "payload_type": "full",
            "ip_addresses": [
                f"fe80::{random.randint(1000, 9999)}:{random.randint(1000, 9999)}:{random.randint(1000, 9999)}:{random.randint(1000, 9999)}",
                f"172.20.10.{random.randint(1, 254)}",
                f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}"
            ],
            "device_name": "iPhone",
            "locale_lang": device.locale.split('_')[0],
            "c": 32,
            "app_version": device.app_version,
            "sr": {"gy": True, "mg": True, "ac": True, "or": True},
            "conf_url": "https://geo.captcha-delivery.com/captcha/",
            "os_version": device.os_version,
            "tz_name": device.timezone,
            "battery": {
                "state": random.choice([1, 2, 3]),
                "low_power": random.choice([0, 1]),
                "level": f"{random.uniform(0.15, 1.0):.2f}",
                "charging_time": random.randint(0, 7200) if random.choice([True, False]) else None,
                "discharging_time": random.randint(3600, 28800) if random.choice([True, False]) else None
            },
            "user_agent": {
                "dua": f"Mozilla/5.0 (iPhone; CPU iPhone OS {device.os_version.replace('.', '_')} like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/{device.app_version} Mobile/15E148 Safari/604.1"
            },
            "cpu": {
                "activecores": random.choice([4, 6, 8]),
                "cores": random.choice([4, 6, 8]),
                "state": 0,
                "architecture": "arm64"
            },
            "ds": True,
            "tz": random.choice([10800000, -18000000, -25200000, -21600000, -28800000]),
            "TouchIDAvailable": "true",
            "FaceIDAvailable": random.choice(["true", "false"]),
            "vendor_identifier": device.vendor_id,
            "memory": {
                "total": random.randint(4000000000, 8000000000),
                "used": random.randint(2000000000, 4000000000),
                "device_memory": random.choice([4, 6, 8])
            },
            "sms_enabled": True,
            "magnes_guid": {"id": str(uuid.uuid4()), "created_at": int(time.time() * 1000)},
            "disk": {
                "total": random.randint(64000000000, 512000000000),
                "free": random.randint(30000000000, 200000000000),
                "quota": random.randint(50000000000, 300000000000)
            },
            "app_guid": device.app_guid,
            "system": {
                "hardware": "arm64 v8",
                "version": random.choice(["21C62", "21D62", "21E258", "21F79"]),
                "system_type": "arm64 64 bit",
                "name": random.choice(["N71AP", "N841AP", "N104AP", "N841mAP"]),
                "kernel_version": f"Darwin Kernel Version {random.randint(21, 23)}.{random.randint(0, 6)}.0"
            },
            "pin_lock_last_timestamp": int(time.time() * 1000) - random.randint(1000, 10000),
            "source_app_version": device.app_version,
            "bindSchemeAvailable": "crypto:kmli,biometric:fingerprint,biometric:face",
            "risk_comp_session_id": str(uuid.uuid4()),
            "magnes_source": 10,
            "device_model": device.device_model,
            "mg_id": hashlib.md5(device.device_id.encode()).hexdigest(),
            "email_configured": random.choice([True, False]),
            "device_uptime": random.randint(60000000, 600000000),
            "rf": "11011",
            "dbg": False,
            "cloud_identifier": str(uuid.uuid4()),
            "PasscodeSet": "true",
            "is_emulator": False,
            "t": True,
            "locale_country": device.locale.split('_')[1],
            "ip_addrs": f"172.20.10.{random.randint(1, 254)}",
            "app_id": "com.apple.mobilesafari",
            "pairing_id": hashlib.md5(f"{device.device_id}pairing".encode()).hexdigest(),
            "conn_type": random.choice(["wifi", "cellular"]),
            "network_info": {
                "connection_type": random.choice(["wifi", "4g", "5g"]),
                "signal_strength": random.randint(-100, -30),
                "carrier": device.carrier
            },
            "TouchIDEnrolled": random.choice(["true", "false"]),
            "dc_id": hashlib.md5(f"{device.device_id}dc".encode()).hexdigest(),
            "location_auth_status": random.choice(["authorized", "denied", "not_determined"]),
            "webgl_info": {
                "vendor": "Apple Inc.",
                "renderer": "Apple GPU",
                "version": "WebGL 2.0",
                "shading_language_version": "WebGL GLSL ES 3.00"
            },
            "canvas_fingerprint": hashlib.md5(f"{device.device_id}canvas{int(time.time())}".encode()).hexdigest()[:16],
            "audio_fingerprint": hashlib.md5(f"{device.device_id}audio{int(time.time())}".encode()).hexdigest()[:16],
            "font_list": [
                "Arial", "Helvetica", "Times", "Courier", "Verdana", "Georgia", "Palatino",
                "Garamond", "Bookman", "Comic Sans MS", "Trebuchet MS", "Arial Black", "Impact"
            ],
            "plugins": [],
            "media_devices": {
                "audio_input": random.randint(0, 2),
                "audio_output": random.randint(1, 3),
                "video_input": random.randint(0, 2)
            },
            "permissions": {
                "camera": random.choice(["granted", "denied", "prompt"]),
                "microphone": random.choice(["granted", "denied", "prompt"]),
                "geolocation": random.choice(["granted", "denied", "prompt"]),
                "notifications": random.choice(["granted", "denied", "default"])
            },
            "performance_timing": {
                "navigation_start": int(time.time() * 1000) - random.randint(1000, 5000),
                "dom_content_loaded": random.randint(100, 500),
                "load_complete": random.randint(500, 2000)
            }
        }
        return json.dumps(risk_data, separators=(',', ':'))
    
    async def solve(self, captcha_data: Dict[str, Any]) -> Optional[TokenSolution]:
        """
        Solve DataDome CAPTCHA using advanced device fingerprinting and Safari iOS impersonation.
        
        Args:
            captcha_data: Dictionary containing:
                - website_url: URL where DataDome is protecting
                - datadome_url: DataDome challenge URL (optional)
                - proxy: Optional proxy to use
                - user_agent: Optional custom user agent
                - additional_headers: Optional additional headers
        
        Returns:
            TokenSolution with DataDome cookie/token or None if failed
        """
        try:
            if not self.validate_input(captcha_data):
                return None
            
            website_url = str(captcha_data['website_url'])
            
            cache_data = {
                'captcha_type': captcha_data['captcha_type'].value if hasattr(captcha_data['captcha_type'], 'value') else str(captcha_data['captcha_type']),
                'website_url': website_url,
                'datadome_url': captcha_data.get('datadome_url'),
                'additional_data': captcha_data.get('additional_data', {}),
                'timeout': captcha_data.get('timeout', 120)
            }
            
            cached_result = await cache_manager.get_cached_solution(cache_data)
            if cached_result:
                logger.debug("Using cached DataDome solution")
                return TokenSolution(**cached_result)
            
            proxy = captcha_data.get('proxy')
            
            if not proxy and proxy_manager.working_proxies:
                proxy = await proxy_manager.get_proxy()
            
            device = iOSDeviceGenerator.generate_device_profile()
            
            for attempt in range(self.max_attempts):
                try:
                    logger.info(f"Solving DataDome attempt {attempt + 1}/{self.max_attempts}")
                    
                    result = await self._solve_datadome_challenge(
                        website_url, device, proxy, captcha_data, attempt
                    )
                    
                    if result:
                        logger.info(f"DataDome result: {result}")
                        
                        solution = TokenSolution(
                            token=result.get('token', ''),
                            cookies=result.get('cookies', {}),
                            confidence=0.95
                        )
                        
                        logger.info(f"Created solution: {solution.model_dump()}")
                        
                        await cache_manager.cache_captcha_solution(
                            cache_data, solution.model_dump(), expire_minutes=30
                        )
                        
                        logger.info(f"DataDome CAPTCHA solved successfully")
                        return solution
                    
                except Exception as e:
                    logger.warning(f"DataDome attempt {attempt + 1} failed: {e}")
                    
                    if proxy:
                        proxy_manager.mark_proxy_failed(proxy)
                        proxy = await proxy_manager.get_proxy()
                    
                    if attempt < self.max_attempts - 1:
                        await asyncio.sleep(random.uniform(2, 4))
            
            logger.error("All DataDome solving attempts failed")
            return None
            
        except Exception as e:
            logger.error(f"Error solving DataDome CAPTCHA: {e}")
            return None
    
    async def _solve_datadome_challenge(
        self,
        website_url: str,
        device: DeviceProfile,
        proxy: Optional[str],
        captcha_data: Dict[str, Any],
        attempt: int
    ) -> Optional[Dict[str, Any]]:
        """Solve DataDome challenge using comprehensive fingerprinting."""
        try:
            start_time = time.time()
            logger.debug(f"Starting DataDome solve for URL: {website_url}")
            
            proxies = None
            if proxy:
                proxies = {'http': proxy, 'https': proxy}
            
            headers = self.get_ios_headers(device, request_type="initial")
            risk_data = self._generate_risk_data(device)
            
            logger.debug("Making initial request to trigger DataDome")
            
            if CURL_CFFI_AVAILABLE:
                response = self.session.get(
                    website_url,
                    headers=headers,
                    proxies=proxies,
                    timeout=self.timeout_seconds,
                    impersonate=self.impersonate_profile,
                    allow_redirects=True
                )
            else:
                response = self.session.get(
                    website_url,
                    headers=headers,
                    proxies=proxies,
                    timeout=self.timeout_seconds,
                    allow_redirects=True
                )
            
            if self._is_datadome_challenge(response):
                logger.debug("DataDome challenge detected, solving...")
                
                dd_params = self._extract_datadome_params(response)
                if not dd_params:
                    logger.error("Failed to extract DataDome parameters")
                    return None
                
                solution = await self._submit_fingerprint_to_datadome(
                    dd_params, device, risk_data, headers, proxies
                )
                
                if solution:
                    elapsed_time = round(time.time() - start_time, 3)
                    logger.info(f"DataDome challenge solved in {elapsed_time}s")
                    return solution
            else:
                logger.debug("No DataDome challenge detected")
                return {
                    'token': 'no_challenge_required',
                    'cookies': dict(response.cookies) if hasattr(response, 'cookies') else {}
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error in DataDome challenge solving: {e}")
            return None
    
    def _is_datadome_challenge(self, response) -> bool:
        """Check if response contains DataDome challenge."""
        try:
            content = response.text.lower() if hasattr(response, 'text') else str(response.content).lower()
            
            datadome_indicators = [
                'datadome',
                'geo.captcha-delivery.com',
                'dd_challenge',
                'dd_captcha',
                'interstitial',
                'challenge.html'
            ]
            
            return any(indicator in content for indicator in datadome_indicators)
            
        except Exception as e:
            logger.debug(f"Error checking DataDome challenge: {e}")
            return False
    
    def _extract_datadome_params(self, response) -> Optional[Dict[str, str]]:
        """Extract DataDome parameters from challenge response."""
        try:
            content = response.text if hasattr(response, 'text') else str(response.content)
            
            params = {}
            
            import re
            
            cid_match = re.search(r'cid["\']?\s*[:=]\s*["\']([^"\']+)["\']', content, re.IGNORECASE)
            if cid_match:
                params['cid'] = cid_match.group(1)
            
            initial_cid_match = re.search(r'initialCid["\']?\s*[:=]\s*["\']([^"\']+)["\']', content, re.IGNORECASE)
            if initial_cid_match:
                params['initialCid'] = initial_cid_match.group(1)
            
            hash_match = re.search(r'hash["\']?\s*[:=]\s*["\']([^"\']+)["\']', content, re.IGNORECASE)
            if hash_match:
                params['hash'] = hash_match.group(1)
            
            t_match = re.search(r'["\']t["\']?\s*[:=]\s*["\']?(\d+)["\']?', content)
            if t_match:
                params['t'] = t_match.group(1)
            
            s_match = re.search(r'["\']s["\']?\s*[:=]\s*["\']([^"\']+)["\']', content)
            if s_match:
                params['s'] = s_match.group(1)
            
            e_match = re.search(r'["\']e["\']?\s*[:=]\s*["\']([^"\']+)["\']', content)
            if e_match:
                params['e'] = e_match.group(1)
            
            if params:
                logger.debug(f"Extracted DataDome parameters: {list(params.keys())}")
                return params
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting DataDome parameters: {e}")
            return None
    
    async def _submit_fingerprint_to_datadome(
        self,
        dd_params: Dict[str, str],
        device: DeviceProfile,
        risk_data: str,
        headers: Dict[str, str],
        proxies: Optional[Dict[str, str]]
    ) -> Optional[Dict[str, Any]]:
        """Submit device fingerprint to DataDome for verification."""
        try:
            api_headers = self.get_ios_headers(device, request_type="api")
            api_headers.update({
                'Origin': 'https://geo.captcha-delivery.com',
                'Referer': 'https://geo.captcha-delivery.com/',
            })
            
            payload = {
                'cid': dd_params.get('cid', ''),
                'initialCid': dd_params.get('initialCid', ''),
                'hash': dd_params.get('hash', ''),
                't': dd_params.get('t', str(int(time.time()))),
                's': dd_params.get('s', ''),
                'e': dd_params.get('e', ''),
                'riskData': risk_data,
                'jsData': {
                    'ttst': random.uniform(10, 50),
                    'ifov': False,
                    'wdifts': False,
                    'wdifrm': False,
                    'wdif': False,
                    'br_oh': device.screen_height,
                    'br_ow': device.screen_width,
                    'ua': api_headers['User-Agent'],
                    'hc': random.choice([4, 6, 8]),
                    'br_h': device.screen_height,
                    'br_w': device.screen_width,
                    'nddc': 0,
                    'rs_h': device.screen_height,
                    'rs_w': device.screen_width,
                    'rs_cd': 24,
                    'phe': False,
                    'nm': False,
                    'jsf': False,
                    'lg': device.locale.replace('_', '-'),
                    'pr': device.scale,
                    'ars_h': device.screen_height - 44,
                    'ars_w': device.screen_width,
                    'tz': -int(time.timezone / 60),
                    'str_ss': True,
                    'str_ls': True,
                    'str_idb': True,
                    'str_odb': True,
                    'plgod': False,
                    'plg': 0,
                    'plgne': True,
                    'plgre': True,
                    'plgof': False,
                    'plggt': False,
                    'pltod': False,
                    'lb': False,
                    'eva': 33,
                    'lo': False,
                    'ts_mtp': device.scale,
                    'ts_tec': True,
                    'ts_tsa': True,
                    'vnd': api_headers['User-Agent'].split(') ')[0].split('(')[1] if '(' in api_headers['User-Agent'] else '',
                    'bid': str(uuid.uuid4()),
                    'mmt': 'application/pdf,text/pdf',
                    'plu': 'PDF Viewer,Chrome PDF Viewer,Chromium PDF Viewer,Microsoft Edge PDF Viewer,WebKit built-in PDF',
                    'hdn': False,
                    'awe': False,
                    'geb': False,
                    'dat': False,
                    'med': 'defined',
                    'aco': 'probably',
                    'acots': False,
                    'acmp': 1024,
                    'acmch': 2,
                    'acsr': 44100,
                    'acsu': 'suspended',
                }
            }
            
            datadome_url = 'https://geo.captcha-delivery.com/captcha/'
            
            if CURL_CFFI_AVAILABLE:
                response = self.session.post(
                    datadome_url,
                    headers=api_headers,
                    json=payload,
                    proxies=proxies,
                    timeout=self.timeout_seconds,
                    impersonate=self.impersonate_profile
                )
            else:
                response = self.session.post(
                    datadome_url,
                    headers=api_headers,
                    json=payload,
                    proxies=proxies,
                    timeout=self.timeout_seconds
                )
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    
                    if result.get('cookie'):
                        cookies_dict = {'datadome': result.get('cookie', '')}
                        if hasattr(response, 'cookies'):
                            cookies_dict.update(dict(response.cookies))
                        
                        return {
                            'token': result.get('cookie', ''),
                            'cookies': cookies_dict
                        }
                    
                except json.JSONDecodeError:
                    logger.debug("DataDome response is not JSON, checking cookies")
                
                if hasattr(response, 'cookies'):
                    cookies = dict(response.cookies)
                    if 'datadome' in cookies:
                        return {
                            'token': cookies['datadome'],
                            'cookies': cookies
                        }
            
            logger.warning(f"DataDome fingerprint submission failed: {response.status_code}")
            return None
            
        except Exception as e:
            logger.error(f"Error submitting fingerprint to DataDome: {e}")
            return None
    
    def validate_input(self, captcha_data: Dict[str, Any]) -> bool:
        """Validate input data for DataDome solver."""
        try:
            required_fields = ['website_url']
            
            for field in required_fields:
                if field not in captcha_data:
                    logger.error(f"Missing required field: {field}")
                    return False
            
            website_url = str(captcha_data['website_url'])
            if not website_url.startswith(('http://', 'https://')):
                logger.error("Invalid website URL format")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating DataDome input: {e}")
            return False
    
    async def _cleanup(self) -> None:
        """Clean up DataDome solver resources."""
        try:
            if self.session:
                if hasattr(self.session, 'close'):
                    if CURL_CFFI_AVAILABLE:
                        self.session.close()
                    else:
                        self.session.close()
                self.session = None
            logger.debug("DataDome solver cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up DataDome solver: {e}")
    
    def get_solver_info(self) -> Dict[str, Any]:
        """Get information about the DataDome solver."""
        return {
            'name': self.solver_name,
            'captcha_type': self.captcha_type,
            'initialized': self.is_initialized,
            'description': 'Advanced DataDome bypass using device fingerprinting and Safari iOS impersonation',
            'features': [
                'iOS device fingerprinting',
                'Safari browser impersonation',
                'curl_cffi JA3 fingerprint matching',
                'Comprehensive device profiling',
                'Anti-detection techniques',
                'Proxy support'
            ],
            'curl_cffi_available': CURL_CFFI_AVAILABLE,
            'max_attempts': self.max_attempts,
            'timeout_seconds': self.timeout_seconds
        }