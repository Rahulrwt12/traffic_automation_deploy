"""Cookie and session management for browser automation"""
import json
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CookieManager:
    """Manages cookies and sessions for browser automation"""
    
    def __init__(self, config: dict):
        """
        Initialize cookie manager
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        cookie_config = config.get('cookies', {})
        self.enabled = cookie_config.get('enabled', True)
        self.persist_cookies = cookie_config.get('persist_cookies', True)
        self.cookie_file = cookie_config.get('cookie_file', 'cookies.json')
        self.returning_user_ratio = cookie_config.get('returning_user_ratio', 0.3)
        
        # Load existing cookies
        self.cookies_by_domain: Dict[str, List[Dict[str, Any]]] = {}
        if self.enabled and self.persist_cookies:
            self._load_cookies()
    
    def _load_cookies(self):
        """Load cookies from file"""
        if not os.path.exists(self.cookie_file):
            return
        
        try:
            with open(self.cookie_file, 'r') as f:
                cookie_data = json.load(f)
                if isinstance(cookie_data, dict):
                    self.cookies_by_domain = cookie_data
                elif isinstance(cookie_data, list):
                    # Old format - convert to domain-based
                    for cookie in cookie_data:
                        domain = cookie.get('domain', '')
                        if domain not in self.cookies_by_domain:
                            self.cookies_by_domain[domain] = []
                        self.cookies_by_domain[domain].append(cookie)
            logger.debug(f"Loaded cookies for {len(self.cookies_by_domain)} domains")
        except Exception as e:
            logger.warning(f"Could not load cookies: {e}")
            self.cookies_by_domain = {}
    
    def _save_cookies(self):
        """Save cookies to file"""
        if not self.persist_cookies:
            return
        
        try:
            with open(self.cookie_file, 'w') as f:
                json.dump(self.cookies_by_domain, f, indent=2)
            logger.debug(f"Saved cookies for {len(self.cookies_by_domain)} domains")
        except Exception as e:
            logger.warning(f"Could not save cookies: {e}")
    
    def get_cookies_for_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Get cookies for a domain"""
        if not self.enabled:
            return []
        
        # Extract base domain
        base_domain = self._extract_base_domain(domain)
        
        # Get cookies for this domain or parent domain
        cookies = []
        for cookie_domain, domain_cookies in self.cookies_by_domain.items():
            if base_domain in cookie_domain or cookie_domain in base_domain:
                cookies.extend(domain_cookies)
        
        return cookies
    
    def _extract_base_domain(self, domain: str) -> str:
        """Extract base domain from URL"""
        if domain.startswith('http://') or domain.startswith('https://'):
            from urllib.parse import urlparse
            parsed = urlparse(domain)
            domain = parsed.netloc
        
        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        
        return domain
    
    def save_cookies_from_browser(self, domain: str, cookies: List[Dict[str, Any]]):
        """Save cookies from browser for a domain"""
        if not self.enabled or not cookies:
            return
        
        base_domain = self._extract_base_domain(domain)
        
        # Filter valid cookies
        valid_cookies = []
        for cookie in cookies:
            if 'name' in cookie and 'value' in cookie:
                # Check expiration
                if 'expires' in cookie:
                    expires = cookie['expires']
                    if isinstance(expires, (int, float)):
                        if expires > 0 and expires < datetime.now().timestamp():
                            continue  # Expired cookie
                
                valid_cookies.append(cookie)
        
        if valid_cookies:
            self.cookies_by_domain[base_domain] = valid_cookies
            self._save_cookies()
    
    def should_use_returning_user(self) -> bool:
        """Determine if this visit should use returning user cookies"""
        import random
        return random.random() < self.returning_user_ratio
    
    def get_returning_user_cookies(self, domain: str) -> Optional[List[Dict[str, Any]]]:
        """Get cookies for returning user"""
        if not self.should_use_returning_user():
            return None
        
        cookies = self.get_cookies_for_domain(domain)
        return cookies if cookies else None

