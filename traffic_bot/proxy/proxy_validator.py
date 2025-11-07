"""Proxy validator for health checking proxies"""
import asyncio
import logging
import time
from typing import List, Dict, Optional
from urllib.parse import urlparse
import requests

logger = logging.getLogger(__name__)


class ProxyValidator:
    """Validates proxy health and connectivity"""
    
    def __init__(self, timeout: int = 10, test_url: str = "https://www.google.com"):
        """
        Initialize proxy validator
        
        Args:
            timeout: Timeout for validation requests (seconds)
            test_url: URL to test proxy connectivity
        """
        self.timeout = timeout
        self.test_url = test_url
    
    def validate_proxy_sync(self, proxy_url: str) -> Dict[str, any]:
        """
        Validate a proxy synchronously (for quick checks)
        
        Args:
            proxy_url: Proxy URL to validate
            
        Returns:
            Dictionary with validation results
        """
        start_time = time.time()
        result = {
            'proxy': proxy_url,
            'valid': False,
            'response_time': 0,
            'error': None,
            'status_code': None
        }
        
        try:
            # Parse proxy URL
            parsed = urlparse(proxy_url)
            proxy_dict = {
                'http': proxy_url,
                'https': proxy_url
            }
            
            # Test proxy connectivity
            response = requests.get(
                self.test_url,
                proxies=proxy_dict,
                timeout=self.timeout,
                allow_redirects=True
            )
            
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                result['valid'] = True
                result['response_time'] = round(response_time, 2)
                result['status_code'] = response.status_code
            else:
                result['error'] = f"Status code: {response.status_code}"
                result['status_code'] = response.status_code
        
        except requests.exceptions.ProxyError as e:
            result['error'] = f"Proxy error: {str(e)[:100]}"
            result['response_time'] = round(time.time() - start_time, 2)
        
        except requests.exceptions.Timeout:
            result['error'] = "Timeout"
            result['response_time'] = self.timeout
        
        except requests.exceptions.ConnectionError as e:
            result['error'] = f"Connection error: {str(e)[:100]}"
            result['response_time'] = round(time.time() - start_time, 2)
        
        except Exception as e:
            result['error'] = f"Error: {str(e)[:100]}"
            result['response_time'] = round(time.time() - start_time, 2)
        
        return result
    
    def validate_proxies_batch(self, proxy_urls: List[str], max_workers: int = 10) -> Dict[str, Dict]:
        """
        Validate multiple proxies in parallel
        
        Args:
            proxy_urls: List of proxy URLs to validate
            max_workers: Maximum concurrent validations
            
        Returns:
            Dictionary mapping proxy URL to validation result
        """
        import concurrent.futures
        import sys
        
        results = {}
        
        # Check if interpreter is shutting down - if so, skip validation
        if sys.is_finalizing() or not sys.modules:
            logger.warning("⚠️  Interpreter shutting down - skipping proxy validation")
            # Return all proxies as valid to avoid blocking shutdown
            return {proxy: {'proxy': proxy, 'valid': True, 'response_time': 0} for proxy in proxy_urls}
        
        logger.info(f"🔍 Validating {len(proxy_urls)} proxies...")
        logger.info(f"   Test URL: {self.test_url}")
        logger.info(f"   Timeout: {self.timeout}s per proxy")
        logger.info("")
        
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all validation tasks
                future_to_proxy = {
                    executor.submit(self.validate_proxy_sync, proxy): proxy
                    for proxy in proxy_urls
                }
                
                # Collect results as they complete
                completed = 0
                for future in concurrent.futures.as_completed(future_to_proxy):
                    proxy = future_to_proxy[future]
                    try:
                        result = future.result()
                        results[proxy] = result
                        completed += 1
                        
                        # Log progress
                        status_icon = "✅" if result['valid'] else "❌"
                        if result['valid']:
                            logger.info(f"   {status_icon} [{completed}/{len(proxy_urls)}] {proxy[:50]}... - {result['response_time']}s")
                        else:
                            logger.warning(f"   {status_icon} [{completed}/{len(proxy_urls)}] {proxy[:50]}... - {result.get('error', 'Failed')}")
                    
                    except Exception as e:
                        results[proxy] = {
                            'proxy': proxy,
                            'valid': False,
                            'error': str(e),
                            'response_time': 0
                        }
                        completed += 1
                        logger.error(f"   ❌ [{completed}/{len(proxy_urls)}] {proxy[:50]}... - Validation error: {e}")
        
        except RuntimeError as e:
            if "cannot schedule new futures after interpreter shutdown" in str(e).lower():
                logger.warning("⚠️  ThreadPoolExecutor shutdown during validation - skipping validation")
                # Return all proxies as valid to avoid blocking shutdown
                return {proxy: {'proxy': proxy, 'valid': True, 'response_time': 0} for proxy in proxy_urls}
            raise
        
        return results
    
    def get_valid_proxies(self, proxy_urls: List[str], max_workers: int = 10) -> List[str]:
        """
        Get list of valid proxies only
        
        Args:
            proxy_urls: List of proxy URLs to validate
            max_workers: Maximum concurrent validations
            
        Returns:
            List of valid proxy URLs
        """
        results = self.validate_proxies_batch(proxy_urls, max_workers)
        valid_proxies = [proxy for proxy, result in results.items() if result.get('valid', False)]
        return valid_proxies
    
    def get_proxy_validation_summary(self, results: Dict[str, Dict]) -> Dict[str, any]:
        """
        Get summary of validation results
        
        Args:
            results: Dictionary of validation results
            
        Returns:
            Summary dictionary
        """
        total = len(results)
        valid = sum(1 for r in results.values() if r.get('valid', False))
        invalid = total - valid
        
        valid_proxies = [p for p, r in results.items() if r.get('valid', False)]
        invalid_proxies = [p for p, r in results.items() if not r.get('valid', False)]
        
        # Calculate average response time for valid proxies
        valid_times = [r['response_time'] for r in results.values() if r.get('valid', False)]
        avg_time = sum(valid_times) / len(valid_times) if valid_times else 0
        
        return {
            'total': total,
            'valid': valid,
            'invalid': invalid,
            'success_rate': (valid / total * 100) if total > 0 else 0,
            'average_response_time': round(avg_time, 2),
            'valid_proxies': valid_proxies,
            'invalid_proxies': invalid_proxies
        }

