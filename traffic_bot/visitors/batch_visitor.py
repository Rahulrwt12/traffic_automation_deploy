"""Batch visitor module - visits all URLs in sequence"""
import asyncio
import random
import logging
from typing import List, Dict, Optional
from datetime import datetime
from traffic_bot.browser.browser_manager import BrowserManager
from traffic_bot.proxy.proxy_manager import ProxyManager
from traffic_bot.analytics.traffic_tracker import TrafficTracker
from traffic_bot.utils import RequestThrottler
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class BatchVisitor:
    """Visits URLs in batch mode with browser automation"""
    
    def __init__(self, config: dict, urls: List[str], url_metadata: Dict[str, Dict], bot_instance=None):
        """
        Initialize batch visitor
        
        Args:
            config: Configuration dictionary
            urls: List of URLs to visit
            url_metadata: Metadata for URLs
            bot_instance: Optional reference to parent TrafficBot for progress tracking
        """
        self.config = config
        self.urls = urls
        self.url_metadata = url_metadata
        self.bot_instance = bot_instance
        
        # Batch mode settings
        batch_config = config.get('batch_mode', {})
        self.batch_delay = batch_config.get('delay_between_urls_seconds', 7)
        self.batch_delay_variation = batch_config.get('delay_variation_seconds', 4)
        self.batch_shuffle = batch_config.get('shuffle_urls', True)
        self.batch_size = batch_config.get('batch_size', None)
        self.batch_reading_min = batch_config.get('reading_time_min', 3)
        self.batch_reading_max = batch_config.get('reading_time_max', 8)
        self.batch_pre_delay_min = batch_config.get('pre_request_delay_min', 1)
        self.batch_pre_delay_max = batch_config.get('pre_request_delay_max', 3)
        
        # Proxy manager
        self.proxy_manager = ProxyManager(config)
        
        # Traffic tracker
        self.tracker = TrafficTracker(config)
        
        # Request throttler
        self.throttler = RequestThrottler(config)
        
        # Browser config
        self.browser_config = config.get('browser', {})
    
    async def visit_all(self):
        """Visit all URLs in batch mode"""
        try:
            # Prepare URLs
            urls_to_visit = list(self.urls)
            
            # Check if we have URLs
            if len(urls_to_visit) == 0:
                logger.error("❌ No URLs to visit! Cannot proceed.")
                logger.error("Please check that your Excel file contains valid URLs.")
                return
            
            if self.batch_shuffle:
                random.shuffle(urls_to_visit)
                logger.info("✓ URLs shuffled for random order")
            
            if self.batch_size and self.batch_size < len(urls_to_visit):
                urls_to_visit = urls_to_visit[:self.batch_size]
                logger.info(f"✓ Limited to first {self.batch_size} URLs")
            
            total_urls = len(urls_to_visit)
            
            logger.info("="*60)
            logger.info("🚀 BATCH MODE - Browser Automation")
            logger.info("="*60)
            logger.info(f"Total URLs: {total_urls}")
            logger.info(f"Delay Between URLs: {self.batch_delay}s ± {self.batch_delay_variation}s")
            logger.info(f"Proxies: {self.proxy_manager.get_proxy_count()}")
            logger.info("="*60)
            logger.info("")
            
            start_time = datetime.now()
            successful_count = 0
            failed_count = 0
            
            # Create browser instance
            browser_manager = None
            
            try:
                # Get proxy
                proxy = self.proxy_manager.get_proxy()
                
                # Create browser
                browser_manager = BrowserManager(self.browser_config, proxy=proxy)
                await browser_manager.start()
                
                for idx, url in enumerate(urls_to_visit, 1):
                    metadata = self.url_metadata.get(url, {})
                    product_name = metadata.get('product_name', 'Unknown Product')
                    
                    logger.info(f"[{idx}/{total_urls}] Visiting: {product_name}")
                    logger.info(f"  URL: {url}")
                    
                    # Apply throttling before request
                    parsed_url = urlparse(url)
                    domain = parsed_url.netloc
                    wait_time = await self.throttler.wait_if_needed(domain=domain)
                    if wait_time > 0:
                        logger.debug(f"  ⏳ Throttled: waited {wait_time:.1f}s")
                    
                    # Visit the URL
                    visit_start = datetime.now()
                    reading_time = random.uniform(self.batch_reading_min, self.batch_reading_max)
                    
                    success = await browser_manager.visit_url(url, reading_time)
                    visit_duration = (datetime.now() - visit_start).total_seconds()
                    
                    # Update progress after visiting URL (thread-safe callback)
                    if self.bot_instance and hasattr(self.bot_instance, 'update_progress'):
                        self.bot_instance.update_progress(1)
                    
                    # Record response for adaptive throttling
                    self.throttler.record_response(visit_duration, success)
                    
                    # Log visit (async, non-blocking file I/O)
                    await self.tracker.log_visit_async(url, success, visit_duration, proxy)
                    
                    if success:
                        successful_count += 1
                        logger.info(f"  ✓ Success ({visit_duration:.1f}s)")
                    else:
                        failed_count += 1
                        logger.warning(f"  ✗ Failed ({visit_duration:.1f}s)")
                    
                    # Update proxy stats
                    if proxy:
                        self.proxy_manager.update_proxy_stats(proxy, success)
                    
                    # Progress
                    progress = (idx / total_urls) * 100
                    logger.info(f"  Progress: {progress:.1f}% ({successful_count} success, {failed_count} failed)")
                    
                    # Delay before next URL (with adaptive throttling)
                    if idx < total_urls:
                        base_delay = self.batch_delay + random.uniform(-self.batch_delay_variation, self.batch_delay_variation)
                        delay = self.throttler.get_adaptive_delay(base_delay)
                        delay = max(2, delay)
                        logger.info(f"  ⏳ Waiting {delay:.1f}s before next URL...")
                        logger.info("-"*60)
                        await asyncio.sleep(delay)
                    else:
                        logger.info("")
                
                # Final stats
                total_time = (datetime.now() - start_time).total_seconds()
                logger.info("="*60)
                logger.info("📊 BATCH COMPLETE")
                logger.info("="*60)
                logger.info(f"Total URLs: {total_urls}")
                logger.info(f"✓ Successful: {successful_count}")
                logger.info(f"✗ Failed: {failed_count}")
                logger.info(f"Total Time: {total_time/60:.1f} minutes")
                logger.info("="*60)
                
                # Update traffic stats
                self.tracker.update_stats()
                self.tracker.generate_report()
            
            finally:
                # Close browser
                if browser_manager:
                    await browser_manager.close()
        
        except Exception as e:
            logger.error(f"Error in batch mode: {e}")
            raise

