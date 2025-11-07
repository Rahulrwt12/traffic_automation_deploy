"""Browser manager using Playwright for real browser automation"""
import asyncio
import logging
import os
import random
from typing import Optional, Dict, Any, List
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from .fingerprint import FingerprintGenerator
from .interaction import UserBehavior
from traffic_bot.utils import EnhancedStealth

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages browser instances with Playwright"""
    
    def __init__(self, config: dict, proxy: Optional[str] = None):
        """
        Initialize browser manager
        
        Args:
            config: Browser configuration
            proxy: Optional proxy URL (format: http://user:pass@host:port)
        """
        self.config = config
        self.proxy = proxy
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # Browser settings
        self.headless = config.get('headless', False)
        self.browser_type = config.get('browser_type', 'chromium')
        self.timeout = config.get('timeout', 30000)
        self.wait_until = config.get('wait_until', 'networkidle')
        self.stealth_mode = config.get('stealth_mode', True)
        self.fingerprint_randomization = config.get('fingerprint_randomization', True)
        
        # Authentication settings
        auth_config = config.get('authentication', {})
        self.auth_enabled = auth_config.get('enabled', False)
        self.auth_username = auth_config.get('username', '')
        self.auth_password = auth_config.get('password', '')
        self.auth_domain = auth_config.get('domain', '')
        
        # Behavior simulation
        behavior_config = config.get('behavior', {})
        self.behavior = UserBehavior(behavior_config) if behavior_config else None
        
        # Fingerprint generator
        device_type = random.choice(['desktop', 'mobile', 'tablet'])
        self.fingerprint_gen = FingerprintGenerator(device_type) if self.fingerprint_randomization else None
        
        # Enhanced stealth module
        self.enhanced_stealth = EnhancedStealth(config) if self.stealth_mode else None
    
    async def start(self):
        """Start browser instance"""
        try:
            # Check if browsers are installed (helpful for Docker/Render debugging)
            # Render uses /opt/render/.cache/ms-playwright, Docker uses /ms-playwright
            browsers_path = os.environ.get('PLAYWRIGHT_BROWSERS_PATH')

            # Treat blank or sentinel values ("0") as "unset", but try local cache first
            sentinel_values = {'', '0', 'None', None}
            if browsers_path in sentinel_values:
                # Prefer the current working directory install when Playwright was run with PLAYWRIGHT_BROWSERS_PATH=0
                cwd_candidate = os.path.join(os.getcwd(), 'ms-playwright')
                if os.path.exists(cwd_candidate):
                    browsers_path = cwd_candidate
                    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = browsers_path
                else:
                    browsers_path = None
                    # Try to detect environment
                    if os.path.exists('/opt/render'):
                        # Render environment
                        candidate_paths = [
                            '/opt/render/project/src/ms-playwright',
                            '/opt/render/project/src/.cache/ms-playwright',
                            '/opt/render/project/.cache/ms-playwright',
                            '/opt/render/.cache/ms-playwright'
                        ]
                        for candidate in candidate_paths:
                            if os.path.exists(candidate):
                                browsers_path = candidate
                                break
                        if browsers_path:
                            os.environ['PLAYWRIGHT_BROWSERS_PATH'] = browsers_path
                    elif os.path.exists('/.dockerenv') or os.path.exists('/app/.dockerenv'):
                        # Docker environment
                        browsers_path = '/ms-playwright'
                        # Set environment variable for Playwright to use
                        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = browsers_path
                    else:
                        # Default location - detect OS
                        import platform
                        system = platform.system()
                        if system == 'Darwin':  # macOS
                            browsers_path = os.path.expanduser('~/Library/Caches/ms-playwright')
                        elif system == 'Windows':
                            browsers_path = os.path.expanduser('~/AppData/Local/ms-playwright')
                        else:  # Linux and others
                            browsers_path = os.path.expanduser('~/.cache/ms-playwright')

            if browsers_path and not os.path.exists(browsers_path):
                # As a last resort, check common Playwright install locations
                fallback_candidates = [
                    os.path.join(os.getcwd(), 'ms-playwright'),
                    '/ms-playwright',
                    os.path.expanduser('~/.cache/ms-playwright'),
                ]
                for candidate in fallback_candidates:
                    if candidate and os.path.exists(candidate):
                        browsers_path = candidate
                        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = candidate
                        break

            if browsers_path and os.path.exists(browsers_path):
                logger.debug(f"✅ Playwright browsers found at: {browsers_path}")
            else:
                logger.warning("⚠️  Playwright browsers cache not found on disk.")
                if os.path.exists('/opt/render'):
                    logger.warning("   Render environment detected - ensure build command runs 'python -m playwright install' during deployment.")
                elif os.path.exists('/.dockerenv'):
                    logger.warning("   Docker environment detected - install browsers in Docker image.")
                else:
                    logger.warning(f"   Run locally: playwright install {self.browser_type}")
            
            self.playwright = await async_playwright().start()
            
            # Select browser type
            if self.browser_type == 'chromium':
                browser_launcher = self.playwright.chromium
            elif self.browser_type == 'firefox':
                browser_launcher = self.playwright.firefox
            elif self.browser_type == 'webkit':
                browser_launcher = self.playwright.webkit
            else:
                browser_launcher = self.playwright.chromium
            
            # Browser launch options
            launch_options = {
                'headless': self.headless,
                'args': []
            }
            
            # Docker/container-specific options (detect if running in container)
            is_docker = os.path.exists('/.dockerenv') or os.path.exists('/app/.dockerenv')
            
            # Stealth mode options for Chromium
            if self.browser_type == 'chromium' and self.stealth_mode:
                launch_options['args'].extend([
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                ])
                # Additional Docker-specific args
                if is_docker:
                    launch_options['args'].extend([
                        '--disable-gpu',
                        '--disable-software-rasterizer',
                        '--single-process',  # May help in low-memory environments
                    ])
            
            # Firefox-specific options for Docker
            if self.browser_type == 'firefox':
                if is_docker:
                    # Firefox in Docker needs special handling
                    launch_options['args'].extend([
                        '--headless',
                    ])
                    # Force headless in Docker even if config says otherwise
                    # (Firefox headful mode doesn't work well in containers)
                    if not self.headless:
                        logger.warning("⚠️  Firefox headful mode not supported in Docker - forcing headless")
                        launch_options['headless'] = True
            
            # Proxy configuration with authentication
            # Important: For Chromium, credentials must be set separately from server URL
            if self.proxy:
                from urllib.parse import urlparse
                parsed_proxy = urlparse(self.proxy)
                
                # Extract server without credentials
                if parsed_proxy.hostname and parsed_proxy.port:
                    proxy_server = f"{parsed_proxy.scheme}://{parsed_proxy.hostname}:{parsed_proxy.port}"
                    
                    # Set up proxy with proper authentication
                    if parsed_proxy.username and parsed_proxy.password:
                        # Credentials must be set separately for reliable authentication
                        launch_options['proxy'] = {
                            'server': proxy_server,
                            'username': parsed_proxy.username,
                            'password': parsed_proxy.password
                        }
                        logger.debug(f"Proxy configured with authentication: {parsed_proxy.hostname}:{parsed_proxy.port}")
                    else:
                        # Proxy without credentials
                        launch_options['proxy'] = {
                            'server': proxy_server
                        }
                        logger.debug(f"Proxy configured without authentication: {proxy_server}")
                else:
                    logger.warning(f"⚠️ Invalid proxy format: {self.proxy}")
            
            # Launch browser
            self.browser = await browser_launcher.launch(**launch_options)
            
            # Create context with fingerprint
            context_options = await self._get_context_options()
            self.context = await self.browser.new_context(**context_options)
            
            # Add stealth scripts (enhanced if available)
            if self.stealth_mode:
                if self.enhanced_stealth:
                    await self._add_enhanced_stealth_scripts()
                else:
                    await self._add_stealth_scripts()
            
            # Create page
            self.page = await self.context.new_page()
            self.page.set_default_timeout(self.timeout)
            
            # Proxy authentication is handled automatically by Playwright
            # when credentials are included in the proxy URL (which is done at launch)
            if self.proxy:
                from urllib.parse import urlparse
                parsed_proxy = urlparse(self.proxy)
                if parsed_proxy.username and parsed_proxy.password:
                    logger.info(f"✅ Proxy authentication configured for {parsed_proxy.hostname}:{parsed_proxy.port}")
                    # Note: Playwright handles proxy auth natively - no manual header injection needed
            
            # Set up HTTP Basic Authentication via route interception (only if enabled and credentials provided)
            if self.auth_enabled:
                # Check if credentials are provided
                if not self.auth_username or not self.auth_password:
                    logger.info(
                        "ℹ️  Authentication is enabled but no credentials provided.\n"
                        "   The bot will try to access the site without authentication.\n"
                        "   If you get authentication errors, you can:\n"
                        "   1. Set credentials in config.json → browser.authentication\n"
                        "   2. Run: python3 get_credentials.py\n"
                        "   3. Or disable authentication: set enabled to false"
                    )
                elif self.auth_username == 'YOUR_USERNAME' or self.auth_password == 'YOUR_PASSWORD':
                    logger.info(
                        "ℹ️  Authentication credentials are placeholders.\n"
                        "   The bot will try to access the site without authentication.\n"
                        "   To enable authentication, update config.json with real credentials."
                    )
                else:
                    # Valid credentials provided - set up authentication
                    auth_header = f'Basic {self._encode_basic_auth(self.auth_username, self.auth_password)}'
                    
                    # Intercept all requests and add Authorization header
                    async def handle_route(route):
                        # Get the request
                        request = route.request
                        url = request.url
                        
                        # Check if this is the target domain
                        from urllib.parse import urlparse
                        parsed = urlparse(url)
                        target_domain = self.auth_domain.replace('www-', '').replace('www.', '')
                        current_domain = parsed.netloc.replace('www-', '').replace('www.', '')
                        
                        if target_domain in current_domain or current_domain.endswith(target_domain):
                            # Add Authorization header
                            headers = request.headers.copy()
                            headers['Authorization'] = auth_header
                            await route.continue_(headers=headers)
                        else:
                            # Continue without modification
                            await route.continue_()
                    
                    # Set up route handler
                    await self.page.route('**/*', handle_route)
                    logger.info(f"✅ HTTP Basic Auth configured for domain: {self.auth_domain}")
            else:
                logger.debug("Authentication disabled - accessing site without credentials")
            
            logger.debug(f"Browser started: {self.browser_type} (headless={self.headless})")
        
        except Exception as e:
            logger.error(f"Error starting browser: {e}")
            raise
    
    async def _get_context_options(self) -> Dict[str, Any]:
        """Get browser context options with fingerprint"""
        options = {
            'viewport': None,
            'user_agent': None,
            'timezone_id': None,
            'locale': None,
            'permissions': [],
            'geolocation': None,
            'color_scheme': random.choice(['light', 'dark']),
            'extra_http_headers': {}
        }
        
        # Apply fingerprint if enabled
        if self.fingerprint_gen:
            fingerprint = self.fingerprint_gen.generate_full_fingerprint()
            
            # Viewport
            viewport = fingerprint['viewport']
            options['viewport'] = {
                'width': viewport['width'],
                'height': viewport['height']
            }
            
            # User agent
            options['user_agent'] = self._generate_user_agent(fingerprint)
            
            # Timezone
            options['timezone_id'] = fingerprint['timezone']
            
            # Locale
            options['locale'] = fingerprint['language']
        
        return options
    
    def _generate_user_agent(self, fingerprint: Dict[str, Any]) -> str:
        """Generate user agent based on fingerprint"""
        device_type = fingerprint.get('device_type', 'desktop')
        
        if device_type == 'mobile':
            # Mobile user agents
            mobile_agents = [
                'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
                'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
                'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36',
                'Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            ]
            return random.choice(mobile_agents)
        elif device_type == 'tablet':
            # Tablet user agents
            tablet_agents = [
                'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
                'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            ]
            return random.choice(tablet_agents)
        else:
            # Desktop user agents
            desktop_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
            ]
            return random.choice(desktop_agents)
    
    async def _add_stealth_scripts(self):
        """Add basic scripts to prevent bot detection"""
        if not self.context:
            return
        
        # Script to remove webdriver property
        stealth_script = """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        // Override plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        
        // Override languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });
        
        // Override chrome
        window.chrome = {
            runtime: {}
        };
        
        // Override permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        """
        
        await self.context.add_init_script(stealth_script)
    
    async def _add_enhanced_stealth_scripts(self):
        """Add enhanced stealth scripts for advanced detection avoidance"""
        if not self.context or not self.enhanced_stealth:
            return
        
        stealth_script = self.enhanced_stealth.get_enhanced_stealth_script()
        await self.context.add_init_script(stealth_script)
        
        # Also set up randomized headers
        if self.enhanced_stealth.randomize_headers:
            await self.context.set_extra_http_headers(
                self.enhanced_stealth.generate_random_headers()
            )
    
    def _encode_basic_auth(self, username: str, password: str) -> str:
        """Encode username:password for HTTP Basic Authentication"""
        import base64
        credentials = f"{username}:{password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return encoded
    
    async def visit_url(self, url: str, reading_time: float = 5.0) -> bool:
        """
        Visit a URL with realistic behavior
        
        Args:
            url: URL to visit
            reading_time: Time to spend on page (seconds)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.page:
                await self.start()
            
            # Navigate to URL (authentication is handled by route interception)
            # Authentication is automatically added via route handler
            response = await self.page.goto(
                url,
                wait_until=self.wait_until,
                timeout=self.timeout
            )
            
            if not response:
                logger.warning(f"No response for {url}")
                return False
            
            status = response.status
            
            if status >= 200 and status < 300:
                # Wait for page to fully load (including analytics)
                await asyncio.sleep(2)
                
                # Simulate realistic user behavior
                if self.behavior:
                    await self.behavior.simulate_full_session(self.page, reading_time)
                else:
                    # Default: just wait
                    await asyncio.sleep(reading_time)
                
                logger.info(f"✓ Successfully visited {url} (Status: {status})")
                return True
            else:
                logger.warning(f"✗ Failed to visit {url} (Status: {status})")
                return False
        
        except Exception as e:
            logger.error(f"Error visiting {url}: {e}")
            return False
    
    async def get_cookies(self) -> List[Dict[str, Any]]:
        """Get cookies from current context"""
        if self.context:
            return await self.context.cookies()
        return []
    
    async def set_cookies(self, cookies: List[Dict[str, Any]]):
        """Set cookies in current context"""
        if self.context and cookies:
            await self.context.add_cookies(cookies)
    
    async def close(self):
        """Close browser instance with proper error handling for EPIPE errors"""
        try:
            # Close in proper order: page -> context -> browser -> playwright
            # Add small delays to allow cleanup to complete
            
            if self.page:
                try:
                    await asyncio.wait_for(self.page.close(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Page close timed out, forcing close")
                except Exception as e:
                    # EPIPE and similar errors are common when closing browsers
                    # These are usually harmless and can be ignored
                    if 'EPIPE' not in str(e) and 'closed' not in str(e).lower():
                        logger.debug(f"Error closing page (may be harmless): {e}")
            
            # Small delay to allow page cleanup
            await asyncio.sleep(0.1)
            
            if self.context:
                try:
                    await asyncio.wait_for(self.context.close(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Context close timed out, forcing close")
                except Exception as e:
                    if 'EPIPE' not in str(e) and 'closed' not in str(e).lower():
                        logger.debug(f"Error closing context (may be harmless): {e}")
            
            # Small delay to allow context cleanup
            await asyncio.sleep(0.1)
            
            if self.browser:
                try:
                    await asyncio.wait_for(self.browser.close(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Browser close timed out, forcing close")
                except Exception as e:
                    if 'EPIPE' not in str(e) and 'closed' not in str(e).lower():
                        logger.debug(f"Error closing browser (may be harmless): {e}")
            
            # Small delay before stopping playwright
            await asyncio.sleep(0.1)
            
            if self.playwright:
                try:
                    await asyncio.wait_for(self.playwright.stop(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Playwright stop timed out")
                except Exception as e:
                    # EPIPE errors from Node.js processes are common and harmless
                    # when browsers are being closed during shutdown
                    if 'EPIPE' not in str(e) and 'closed' not in str(e).lower():
                        logger.debug(f"Error stopping playwright (may be harmless): {e}")
            
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None
            
            logger.debug("Browser closed successfully")
        
        except Exception as e:
            # Catch-all for any unexpected errors
            # EPIPE errors from Node.js are expected during browser shutdown
            if 'EPIPE' not in str(e):
                logger.error(f"Error closing browser: {e}")
            else:
                logger.debug(f"EPIPE error during browser close (harmless): {e}")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

