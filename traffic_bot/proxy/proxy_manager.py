"""Proxy manager for loading and managing proxies"""
import os
import json
import random
import logging
from typing import List, Dict, Optional
import requests
from .proxy_validator import ProxyValidator

logger = logging.getLogger(__name__)


class ProxyManager:
    """Manages proxy loading, validation, and rotation"""
    
    def __init__(self, config: dict, proxy_list: Optional[List[str]] = None):
        """
        Initialize proxy manager
        
        Args:
            config: Configuration dictionary
            proxy_list: Optional list of proxies to use instead of loading from API/file.
                       If provided, this subset will be used directly.
        """
        self.config = config
        self.proxies: List[str] = []
        self.valid_proxies: List[str] = []
        self.dead_proxies: set = set()
        self.proxy_stats: Dict[str, Dict] = {}
        self.proxy_index = 0
        
        # Proxy settings
        proxy_config = config.get('proxy_rotation', {})
        self.proxy_rotation_strategy = proxy_config.get('strategy', 'smart')
        self.proxy_health_check = proxy_config.get('health_check', True)
        self.proxy_health_timeout = proxy_config.get('health_check_timeout', 5)
        self.proxy_max_failures = proxy_config.get('max_failures_before_remove', 3)
        self.consecutive_failures_threshold = proxy_config.get('consecutive_failures_before_remove', 3)
        self.failure_rate_threshold = proxy_config.get('failure_rate_threshold', 0.7)
        self.auto_remove_failing = proxy_config.get('auto_remove_failing_proxies', True)
        self.proxy_fallback_to_direct = proxy_config.get('fallback_to_direct', True)
        self.validate_at_startup = proxy_config.get('validate_at_startup', True)
        self.validation_timeout = proxy_config.get('validation_timeout', 10)
        self.validation_test_url = proxy_config.get('validation_test_url', 'https://www.google.com')
        
        # Load proxies
        if proxy_list is not None:
            # Use provided proxy list directly (for batch mode subsets)
            self.proxies = proxy_list.copy()
            self.valid_proxies = proxy_list.copy()
            logger.info(f"ProxyManager initialized with {len(proxy_list)} proxies from provided list")
            # Skip validation for subset proxies to avoid delays
        elif config.get('enable_proxy_rotation', True):
            self._load_proxies()
            
            # Validate proxies at startup if enabled
            if self.validate_at_startup and self.valid_proxies:
                self._validate_proxies_at_startup()
    
    def _load_proxies_from_api(self, api_config: dict) -> List[str]:
        """Load proxies from API endpoint"""
        # Check environment variable first, then config file
        api_key = os.getenv('PROXY_API_KEY') or api_config.get('api_key', '')
        api_type = api_config.get('api_type', 'generic')
        api_endpoint = api_config.get('api_endpoint', '')
        
        if not api_key or api_key == 'YOUR_API_KEY_HERE' or api_key == '':
            logger.warning("Proxy API key not configured. Please set PROXY_API_KEY environment variable or api_key in config.json")
            return []
        
        proxies = []
        
        try:
            if api_type == 'webshare':
                endpoint = api_endpoint or 'https://proxy.webshare.io/api/v2/proxy/list/'
                headers = {'Authorization': f'Token {api_key}'}
                
                # Get max_proxies limit from config
                max_proxies = api_config.get('max_proxies', 100)
                
                # Fetch all proxies with pagination
                page = 1
                total_fetched = 0
                has_more = True
                pagination_params = {}  # Store params that work for pagination
                
                while has_more and total_fetched < max_proxies:
                    # Try different modes if first request fails
                    if page == 1:
                        response = requests.get(endpoint, headers=headers, timeout=10)
                        if response.status_code == 400:
                            modes_to_try = ['direct', 'residential', 'static_residential']
                            for mode in modes_to_try:
                                pagination_params = {'mode': mode, 'page': page}
                                response = requests.get(endpoint, headers=headers, params=pagination_params, timeout=10)
                                if response.status_code == 200:
                                    logger.debug(f"Webshare API mode '{mode}' works")
                                    break
                        else:
                            # First request succeeded without mode param
                            pagination_params = {'page': page}
                    else:
                        # For subsequent pages, use same params as first successful request
                        pagination_params['page'] = page
                        response = requests.get(endpoint, headers=headers, params=pagination_params, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        page_proxies = []
                        
                        if isinstance(data, dict):
                            # Check if results exist
                            if 'results' in data:
                                page_proxies = data['results']
                                # Check pagination info
                                has_next = data.get('next') is not None
                                total_count = data.get('count', len(page_proxies))
                                logger.debug(f"Page {page}: Found {len(page_proxies)} proxies (Total available: {total_count})")
                            elif isinstance(data, list):
                                page_proxies = data
                            else:
                                # Single proxy object
                                if 'proxy_address' in data or 'ip' in data:
                                    page_proxies = [data]
                        elif isinstance(data, list):
                            page_proxies = data
                        
                        # Process proxies from this page
                        for proxy_obj in page_proxies:
                            if total_fetched >= max_proxies:
                                break
                                
                            if isinstance(proxy_obj, dict):
                                proxy_address = proxy_obj.get('proxy_address', proxy_obj.get('ip'))
                                port = proxy_obj.get('port')
                                username = proxy_obj.get('username')
                                password = proxy_obj.get('password')
                                
                                if proxy_address and port:
                                    if username and password:
                                        proxy_url = f"http://{username}:{password}@{proxy_address}:{port}"
                                    else:
                                        proxy_url = f"http://{proxy_address}:{port}"
                                    proxies.append(proxy_url)
                                    total_fetched += 1
                        
                        # Check if there are more pages
                        if isinstance(data, dict):
                            has_more = data.get('next') is not None and total_fetched < max_proxies
                        else:
                            has_more = len(page_proxies) > 0 and total_fetched < max_proxies
                        
                        if has_more:
                            page += 1
                        else:
                            break
                    elif response.status_code == 401:
                        logger.error("Invalid Webshare API key. Please check your API key in config.json")
                        break
                    else:
                        logger.warning(f"Webshare API error on page {page}: Status {response.status_code}")
                        break
                
                logger.info(f"Fetched {len(proxies)} proxies from Webshare API (across {page} page{'s' if page > 1 else ''})")
            
            elif api_type == 'smartproxy':
                endpoint = api_config.get('alternatives', {}).get('smartproxy', api_endpoint)
                headers = {'Authorization': f'Basic {api_key}'}
                response = requests.get(endpoint, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, dict):
                        proxies = [f"http://{api_key}@{data.get('host')}:{data.get('port')}"]
            
            elif api_type == 'brightdata':
                endpoint = api_config.get('alternatives', {}).get('brightdata', api_endpoint)
                proxies = [endpoint]
            
            elif api_type == 'oxylabs':
                endpoint = api_config.get('alternatives', {}).get('oxylabs', api_endpoint)
                proxies = [endpoint.replace('USERNAME:PASSWORD', api_key)]
            
            elif api_type == 'generic' or api_type == 'custom':
                headers = {'Authorization': f'Bearer {api_key}', 'X-API-Key': api_key}
                params = {'key': api_key}
                response = requests.get(api_endpoint, headers=headers, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        proxies = data
                    elif isinstance(data, dict):
                        proxies = data.get('proxies', []) or data.get('data', [])
                        if not proxies and 'proxy' in data:
                            proxies = [data['proxy']]
                        if not proxies and 'ip' in data and 'port' in data:
                            proxy_format = api_config.get('proxy_format', 'http://{ip}:{port}')
                            proxy = proxy_format.replace('{ip}', str(data['ip'])).replace('{port}', str(data['port']))
                            if '{username}' in proxy_format:
                                proxy = proxy.replace('{username}', data.get('username', api_key))
                            if '{password}' in proxy_format:
                                proxy = proxy.replace('{password}', data.get('password', api_key))
                            proxies = [proxy]
            
            # Validate proxy format
            valid_proxies = []
            for proxy in proxies:
                if isinstance(proxy, str):
                    if proxy.startswith('http://') or proxy.startswith('https://') or proxy.startswith('socks5://'):
                        valid_proxies.append(proxy)
                    elif ':' in proxy:
                        parts = proxy.split(':')
                        if len(parts) == 2:
                            try:
                                int(parts[1])  # Validate port
                                valid_proxies.append(f"http://{proxy}")
                            except:
                                pass
            
            # Limit proxies if max_proxies is set (safety check - Webshare already limits during pagination)
            max_proxies = api_config.get('max_proxies', None)
            if max_proxies and isinstance(max_proxies, int) and max_proxies > 0:
                if len(valid_proxies) > max_proxies:
                    logger.info(f"Limiting to {max_proxies} proxies (received {len(valid_proxies)})")
                    valid_proxies = valid_proxies[:max_proxies]
            
            if valid_proxies:
                logger.info(f"✓ Loaded {len(valid_proxies)} proxies from API")
            else:
                logger.warning("⚠ No valid proxies received from API")
            
            return valid_proxies
            
        except Exception as e:
            logger.error(f"Error loading proxies from API: {e}")
            return []
    
    def _load_proxies_from_file(self, proxy_file: str) -> List[str]:
        """Load proxies from JSON file"""
        if not os.path.exists(proxy_file):
            return []
        
        try:
            with open(proxy_file, 'r') as f:
                proxy_data = json.load(f)
                proxies = proxy_data.get('proxies', [])
                if proxies:
                    logger.info(f"✓ Loaded {len(proxies)} proxies from {proxy_file}")
                return proxies
        except Exception as e:
            logger.warning(f"Could not load proxies from file: {e}")
            return []
    
    def _load_proxies(self):
        """Load proxies from API or file"""
        api_config = self.config.get('proxy_api', {})
        if api_config.get('enabled', False):
            api_proxies = self._load_proxies_from_api(api_config)
            if api_proxies:
                self.proxies = api_proxies
                self.valid_proxies = api_proxies.copy()
                logger.info(f"Using {len(self.valid_proxies)} proxies from API")
                return
        
        proxy_file = self.config.get('proxy_file', 'proxies.json')
        file_proxies = self._load_proxies_from_file(proxy_file)
        if file_proxies:
            self.proxies = file_proxies
            self.valid_proxies = file_proxies.copy()
            logger.info(f"Using {len(self.valid_proxies)} proxies from file")
            return
        
        logger.info("⚠ No proxies found. Using direct connection (consider setting up proxy API)")
        self.proxies = []
        self.valid_proxies = []
    
    def get_proxy(self) -> Optional[str]:
        """Get a proxy using rotation strategy"""
        if not self.valid_proxies:
            return None
        
        # Filter out dead proxies
        available_proxies = [p for p in self.valid_proxies if p not in self.dead_proxies]
        
        if not available_proxies:
            if self.proxy_fallback_to_direct:
                logger.warning("All proxies dead, resetting and using direct connection")
                self.dead_proxies.clear()
                available_proxies = self.valid_proxies.copy()
            else:
                return None
        
        # Rotation strategy
        if self.proxy_rotation_strategy == 'smart':
            if random.random() < 0.7:
                proxy_url = available_proxies[self.proxy_index % len(available_proxies)]
                self.proxy_index += 1
            else:
                proxy_url = random.choice(available_proxies)
        elif self.proxy_rotation_strategy == 'random':
            proxy_url = random.choice(available_proxies)
        else:  # round-robin
            proxy_url = available_proxies[self.proxy_index % len(available_proxies)]
            self.proxy_index += 1
        
        # Track proxy usage
        if proxy_url not in self.proxy_stats:
            self.proxy_stats[proxy_url] = {'success': 0, 'failed': 0, 'last_used': None}
        
        return proxy_url
    
    def mark_proxy_dead(self, proxy_url: str):
        """Mark a proxy as dead"""
        if proxy_url not in self.dead_proxies:
            self.dead_proxies.add(proxy_url)
            logger.warning(f"⚠ Marked proxy as dead: {proxy_url[:60]}...")
    
    def update_proxy_stats(self, proxy_url: str, success: bool):
        """Update proxy performance statistics"""
        if not proxy_url:
            return
        
        if proxy_url not in self.proxy_stats:
            self.proxy_stats[proxy_url] = {
                'success': 0,
                'failed': 0,
                'last_used': None,
                'consecutive_failures': 0
            }
        
        stats = self.proxy_stats[proxy_url]
        
        if success:
            stats['success'] += 1
            stats['consecutive_failures'] = 0  # Reset consecutive failures
        else:
            stats['failed'] += 1
            stats['consecutive_failures'] += 1
            
            if self.auto_remove_failing:
                # Mark as dead if too many consecutive failures
                if stats['consecutive_failures'] >= self.consecutive_failures_threshold:
                    self.mark_proxy_dead(proxy_url)
                    logger.warning(f"⚠ Proxy failed {stats['consecutive_failures']} times consecutively - marked as dead")
                
                # Mark as dead if failure rate is too high
                total = stats['success'] + stats['failed']
                if total >= self.proxy_max_failures:
                    failure_rate = stats['failed'] / total
                    if failure_rate > self.failure_rate_threshold:
                        self.mark_proxy_dead(proxy_url)
                        logger.warning(f"⚠ Proxy has {failure_rate*100:.1f}% failure rate ({stats['failed']}/{total}) - marked as dead")
    
    def get_proxy_performance_report(self) -> Dict[str, Dict]:
        """Get performance report for all proxies"""
        report = {}
        for proxy_url, stats in self.proxy_stats.items():
            total = stats['success'] + stats['failed']
            if total > 0:
                success_rate = (stats['success'] / total) * 100
                report[proxy_url] = {
                    'total_requests': total,
                    'success': stats['success'],
                    'failed': stats['failed'],
                    'success_rate': round(success_rate, 2),
                    'status': 'dead' if proxy_url in self.dead_proxies else 'active'
                }
        return report
    
    def get_working_proxies(self) -> List[str]:
        """Get list of working (non-dead) proxies"""
        return [p for p in self.valid_proxies if p not in self.dead_proxies]
    
    def get_dead_proxies(self) -> List[str]:
        """Get list of dead proxies"""
        return list(self.dead_proxies)
    
    def _validate_proxies_at_startup(self):
        """Validate all proxies at startup"""
        if not self.valid_proxies:
            return
        
        logger.info("")
        logger.info("="*60)
        logger.info("🔍 PROXY HEALTH CHECK")
        logger.info("="*60)
        
        # Create validator
        validator = ProxyValidator(
            timeout=self.validation_timeout,
            test_url=self.validation_test_url
        )
        
        # Validate all proxies
        validation_results = validator.validate_proxies_batch(
            self.valid_proxies,
            max_workers=10
        )
        
        # Get summary
        summary = validator.get_proxy_validation_summary(validation_results)
        
        # Filter out invalid proxies
        valid_proxies = summary['valid_proxies']
        invalid_proxies = summary['invalid_proxies']
        
        # Mark invalid proxies as dead
        for invalid_proxy in invalid_proxies:
            self.mark_proxy_dead(invalid_proxy)
        
        # Update valid_proxies list
        self.valid_proxies = valid_proxies
        
        # Log summary
        logger.info("")
        logger.info("="*60)
        logger.info("📊 VALIDATION SUMMARY")
        logger.info("="*60)
        logger.info(f"✅ Valid Proxies: {summary['valid']}/{summary['total']}")
        logger.info(f"❌ Invalid Proxies: {summary['invalid']}/{summary['total']}")
        logger.info(f"📈 Success Rate: {summary['success_rate']:.1f}%")
        if summary['valid'] > 0:
            logger.info(f"⏱️  Average Response Time: {summary['average_response_time']}s")
        
        if invalid_proxies:
            logger.info("")
            logger.info("❌ Invalid Proxies (will be skipped):")
            for invalid_proxy in invalid_proxies[:5]:  # Show first 5
                result = validation_results.get(invalid_proxy, {})
                error = result.get('error', 'Unknown error')
                logger.info(f"   • {invalid_proxy[:50]}... - {error}")
            if len(invalid_proxies) > 5:
                logger.info(f"   ... and {len(invalid_proxies) - 5} more invalid proxies")
        
        logger.info("")
        logger.info(f"✅ Using {len(self.valid_proxies)} validated proxies")
        logger.info("="*60)
        logger.info("")
        
        # Warn if too many proxies are invalid
        if summary['success_rate'] < 50:
            logger.warning(f"⚠️  Warning: Only {summary['success_rate']:.1f}% of proxies are valid!")
            logger.warning("   Consider checking your proxy API or configuration.")
        
        if len(self.valid_proxies) == 0:
            logger.error("❌ No valid proxies found! Bot cannot run.")
            logger.error("   Please check your proxy configuration or API key.")
    
    def get_all_proxies(self) -> List[str]:
        """Get all valid proxies"""
        return self.valid_proxies.copy()
    
    def get_proxy_count(self) -> int:
        """Get number of valid proxies"""
        return len(self.valid_proxies)

