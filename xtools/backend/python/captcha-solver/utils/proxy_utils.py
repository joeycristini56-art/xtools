import random
import asyncio
import aiohttp
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse
from .logger import get_logger

logger = get_logger(__name__)


class ProxyManager:
    """Proxy management and rotation system."""
    
    def __init__(self, proxy_list: List[str] = None):
        self.proxy_list = proxy_list or []
        self.working_proxies: List[str] = []
        self.failed_proxies: List[str] = []
        self.proxy_stats: Dict[str, Dict[str, Any]] = {}
        self._current_index = 0
        self._lock = asyncio.Lock()
    
    def add_proxy(self, proxy: str) -> None:
        """Add a proxy to the list."""
        if proxy not in self.proxy_list:
            self.proxy_list.append(proxy)
            self.proxy_stats[proxy] = {
                'success_count': 0,
                'failure_count': 0,
                'last_used': None,
                'response_time': None,
                'status': 'untested'
            }
    
    def add_proxies(self, proxies: List[str]) -> None:
        """Add multiple proxies to the list."""
        for proxy in proxies:
            self.add_proxy(proxy)
    
    async def test_proxy(self, proxy: str, test_url: str = "http://httpbin.org/ip", timeout: int = 10) -> bool:
        """Test if a proxy is working."""
        try:
            proxy_config = self._parse_proxy(proxy)
            if not proxy_config:
                return False
            
            start_time = asyncio.get_event_loop().time()
            
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False),
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as session:
                async with session.get(test_url, proxy=proxy_config['url']) as response:
                    if response.status == 200:
                        response_time = asyncio.get_event_loop().time() - start_time
                        self.proxy_stats[proxy].update({
                            'status': 'working',
                            'response_time': response_time,
                            'success_count': self.proxy_stats[proxy]['success_count'] + 1
                        })
                        return True
                    else:
                        self.proxy_stats[proxy]['status'] = 'failed'
                        return False
        
        except Exception as e:
            logger.debug(f"Proxy {proxy} test failed: {e}")
            self.proxy_stats[proxy].update({
                'status': 'failed',
                'failure_count': self.proxy_stats[proxy]['failure_count'] + 1
            })
            return False
    
    def _parse_proxy(self, proxy: str) -> Optional[Dict[str, str]]:
        """Parse proxy string into usable format."""
        try:
            if '://' not in proxy:
                proxy = f'http://{proxy}'
            
            parsed = urlparse(proxy)
            
            if not parsed.hostname or not parsed.port:
                return None
            
            proxy_url = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
            
            result = {'url': proxy_url}
            
            if parsed.username and parsed.password:
                result['auth'] = aiohttp.BasicAuth(parsed.username, parsed.password)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to parse proxy {proxy}: {e}")
            return None
    
    async def test_all_proxies(self, test_url: str = "http://httpbin.org/ip", max_concurrent: int = 10) -> None:
        """Test all proxies concurrently."""
        logger.info(f"Testing {len(self.proxy_list)} proxies")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def test_with_semaphore(proxy):
            async with semaphore:
                return await self.test_proxy(proxy, test_url)
        
        tasks = [test_with_semaphore(proxy) for proxy in self.proxy_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        self.working_proxies = []
        self.failed_proxies = []
        
        for proxy, result in zip(self.proxy_list, results):
            if isinstance(result, bool) and result:
                self.working_proxies.append(proxy)
            else:
                self.failed_proxies.append(proxy)
        
        logger.info(f"Proxy testing completed: {len(self.working_proxies)} working, {len(self.failed_proxies)} failed")
    
    async def get_proxy(self, rotation: bool = True) -> Optional[str]:
        """Get a working proxy."""
        async with self._lock:
            if not self.working_proxies:
                logger.warning("No working proxies available")
                return None
            
            if rotation:
                proxy = self.working_proxies[self._current_index % len(self.working_proxies)]
                self._current_index += 1
            else:
                proxy = random.choice(self.working_proxies)
            
            self.proxy_stats[proxy]['last_used'] = asyncio.get_event_loop().time()
            return proxy
    
    def mark_proxy_failed(self, proxy: str) -> None:
        """Mark a proxy as failed and remove from working list."""
        if proxy in self.working_proxies:
            self.working_proxies.remove(proxy)
            self.failed_proxies.append(proxy)
            self.proxy_stats[proxy]['status'] = 'failed'
            self.proxy_stats[proxy]['failure_count'] += 1
            logger.debug(f"Marked proxy {proxy} as failed")
    
    def mark_proxy_success(self, proxy: str) -> None:
        """Mark a proxy as successful."""
        if proxy in self.proxy_stats:
            self.proxy_stats[proxy]['success_count'] += 1
            self.proxy_stats[proxy]['status'] = 'working'
    
    def get_proxy_stats(self) -> Dict[str, Any]:
        """Get proxy statistics."""
        return {
            'total_proxies': len(self.proxy_list),
            'working_proxies': len(self.working_proxies),
            'failed_proxies': len(self.failed_proxies),
            'success_rate': len(self.working_proxies) / len(self.proxy_list) if self.proxy_list else 0,
            'proxy_details': self.proxy_stats
        }
    
    async def create_session_with_proxy(self, proxy: Optional[str] = None) -> aiohttp.ClientSession:
        """Create an aiohttp session with proxy configuration."""
        if not proxy:
            proxy = await self.get_proxy()
        
        if not proxy:
            return aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False),
                timeout=aiohttp.ClientTimeout(total=30)
            )
        
        proxy_config = self._parse_proxy(proxy)
        if not proxy_config:
            return aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False),
                timeout=aiohttp.ClientTimeout(total=30)
            )
        
        session_kwargs = {
            'connector': aiohttp.TCPConnector(ssl=False),
            'timeout': aiohttp.ClientTimeout(total=30)
        }
        
        if 'auth' in proxy_config:
            session_kwargs['auth'] = proxy_config['auth']
        
        session = aiohttp.ClientSession(**session_kwargs)
        
        session._proxy_url = proxy_config['url']
        
        return session
    
    def load_proxies_from_file(self, file_path: str) -> None:
        """Load proxies from a text file."""
        try:
            with open(file_path, 'r') as f:
                proxies = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            
            self.add_proxies(proxies)
            logger.info(f"Loaded {len(proxies)} proxies from {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to load proxies from {file_path}: {e}")
    
    def save_working_proxies(self, file_path: str) -> None:
        """Save working proxies to a file."""
        try:
            with open(file_path, 'w') as f:
                for proxy in self.working_proxies:
                    f.write(f"{proxy}\n")
            
            logger.info(f"Saved {len(self.working_proxies)} working proxies to {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to save working proxies to {file_path}: {e}")
    
    async def refresh_proxy_list(self, test_url: str = "http://httpbin.org/ip") -> None:
        """Refresh the proxy list by retesting failed proxies."""
        logger.info("Refreshing proxy list")
        
        retest_proxies = self.failed_proxies.copy()
        self.failed_proxies = []
        
        for proxy in retest_proxies:
            if await self.test_proxy(proxy, test_url):
                self.working_proxies.append(proxy)
            else:
                self.failed_proxies.append(proxy)
        
        logger.info(f"Proxy refresh completed: {len(self.working_proxies)} working proxies available")


proxy_manager = ProxyManager()