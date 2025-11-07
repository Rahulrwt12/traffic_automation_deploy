"""Parallel visitor module - visits URLs with multiple browsers simultaneously"""
import asyncio
import random
import logging
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import urlparse
from traffic_bot.browser.browser_manager import BrowserManager
from traffic_bot.proxy.proxy_manager import ProxyManager
from traffic_bot.analytics.traffic_tracker import TrafficTracker
from traffic_bot.utils import ErrorHandler, RequestThrottler

logger = logging.getLogger(__name__)


class ParallelVisitor:
    """Visits URLs in parallel using multiple browser instances"""
    
    def __init__(self, config: dict, urls: List[str], url_metadata: Dict[str, Dict], proxy_manager: Optional[ProxyManager] = None, bot_instance=None):
        """
        Initialize parallel visitor
        
        Args:
            config: Configuration dictionary
            urls: List of URLs to visit
            url_metadata: Metadata for URLs
            proxy_manager: Optional ProxyManager instance (if None, will create one)
            bot_instance: Optional reference to parent TrafficBot for progress tracking
        """
        self.config = config
        self.urls = urls
        self.url_metadata = url_metadata
        self.bot_instance = bot_instance
        
        # Parallel mode settings
        parallel_config = config.get('parallel_mode', {})
        self.max_concurrent_proxies = parallel_config.get('max_concurrent_proxies', 10)
        self.parallel_distribution = parallel_config.get('distribution', 'round-robin')
        
        # Batch mode settings
        batch_config = config.get('batch_mode', {})
        self.batch_delay = batch_config.get('delay_between_urls_seconds', 7)
        self.batch_delay_variation = batch_config.get('delay_variation_seconds', 4)
        self.batch_reading_min = batch_config.get('reading_time_min', 3)
        self.batch_reading_max = batch_config.get('reading_time_max', 8)
        
        # Proxy manager - use provided one or create new
        if proxy_manager is not None:
            self.proxy_manager = proxy_manager
        else:
            # Only create ProxyManager if not provided (normal parallel mode)
            self.proxy_manager = ProxyManager(config)
        
        # Traffic tracker (shared across threads)
        self.tracker = TrafficTracker(config)
        
        # Request throttler
        self.throttler = RequestThrottler(config)
        
        # Browser config
        self.browser_config = config.get('browser', {})
        
        # Thread-safe locks
        self.stats_lock = asyncio.Lock()
        
        # Semaphore to limit concurrent browser startups (prevent resource exhaustion)
        # Start with 10 concurrent browsers, then scale up
        max_concurrent_browser_starts = config.get('parallel_mode', {}).get('max_concurrent_browser_starts', 10)
        self.browser_start_semaphore = asyncio.Semaphore(max_concurrent_browser_starts)
    
    async def _proxy_worker(self, proxy_url: str, proxy_index: int, urls_for_proxy: List[str], results: dict):
        """Worker coroutine that visits URLs using a specific proxy"""
        thread_name = f"Proxy-{proxy_index}"
        successful_count = 0
        failed_count = 0
        
        browser_manager = None
        
        try:
            logger.info(f"[{thread_name}] 🚀 Starting with proxy {proxy_index}")
            logger.info(f"[{thread_name}] 📋 Assigned {len(urls_for_proxy)} URLs to visit")
            
            # Create browser with proxy
            logger.info(f"[{thread_name}] 🔧 Creating browser manager...")
            browser_manager = BrowserManager(self.browser_config, proxy=proxy_url)
            
            # Start browser with better error handling and semaphore to limit concurrent starts
            logger.info(f"[{thread_name}] 🚀 Attempting to start browser...")
            async with self.browser_start_semaphore:
                # Only allow limited number of browsers to start simultaneously
                try:
                    # Add timeout to browser startup (30 seconds max)
                    await asyncio.wait_for(browser_manager.start(), timeout=30.0)
                    # Verify browser actually started
                    if not browser_manager.browser or not browser_manager.page:
                        raise Exception("Browser failed to start - browser or page is None")
                    logger.info(f"[{thread_name}] ✅ Browser started successfully")
                except asyncio.TimeoutError:
                    error_msg = "Browser startup timed out after 30 seconds"
                    logger.error(f"[{thread_name}] ❌ {error_msg}")
                    logger.error(f"[{thread_name}] This may indicate browser installation issues or resource constraints")
                    # Mark all URLs as failed since we can't visit them
                    failed_count = len(urls_for_proxy)
                    results[proxy_index] = {
                        'successful': 0,
                        'failed': failed_count,
                        'proxy': proxy_url,
                        'error': error_msg
                    }
                    # Update proxy stats to mark this proxy as problematic
                    self.proxy_manager.update_proxy_stats(proxy_url, False)
                    return  # Exit early since browser didn't start
                except Exception as browser_error:
                    error_msg = f"Failed to start browser: {str(browser_error)}"
                    logger.error(f"[{thread_name}] ❌ {error_msg}")
                    logger.exception(f"[{thread_name}] Browser startup error details:")
                    # Mark all URLs as failed since we can't visit them
                    failed_count = len(urls_for_proxy)
                    results[proxy_index] = {
                        'successful': 0,
                        'failed': failed_count,
                        'proxy': proxy_url,
                        'error': error_msg
                    }
                    # Update proxy stats to mark this proxy as problematic
                    self.proxy_manager.update_proxy_stats(proxy_url, False)
                    return  # Exit early since browser didn't start
            
            for url_idx, url in enumerate(urls_for_proxy, 1):
                try:
                    # Check for stop signal
                    if hasattr(self, '_should_stop') and callable(self._should_stop) and self._should_stop():
                        logger.info(f"[{thread_name}] ⚠️  Stop signal received, stopping worker...")
                        break
                    
                    # Check if current task is cancelled
                    current_task = asyncio.current_task()
                    if current_task and current_task.cancelled():
                        logger.info(f"[{thread_name}] ⚠️  Task cancelled, stopping worker...")
                        break
                    
                    metadata = self.url_metadata.get(url, {})
                    product_name = metadata.get('product_name', 'Unknown Product')
                    
                    logger.info(f"[{thread_name}] [{url_idx}/{len(urls_for_proxy)}] 🌐 Visiting: {product_name}")
                    logger.info(f"[{thread_name}]    🔗 URL: {url}")
                    
                    # Apply throttling before request
                    parsed_url = urlparse(url)
                    domain = parsed_url.netloc
                    wait_time = await self.throttler.wait_if_needed(domain=domain)
                    if wait_time > 0:
                        logger.debug(f"[{thread_name}]    ⏳ Throttled: waited {wait_time:.1f}s")
                    
                    # Check again before visiting
                    if hasattr(self, '_should_stop') and callable(self._should_stop) and self._should_stop():
                        logger.info(f"[{thread_name}] ⚠️  Stop signal received, stopping before visit...")
                        break
                    
                    # Visit the URL with retry logic
                    visit_start = datetime.now()
                    reading_time = random.uniform(self.batch_reading_min, self.batch_reading_max)
                    
                    try:
                        # Use error handler for retry logic
                        success = await ErrorHandler.retry_async(
                            lambda: browser_manager.visit_url(url, reading_time),
                            max_retries=2,
                            delay=2.0,
                            exceptions=(Exception,),
                            error_context=f"{thread_name} visiting {url[:50]}"
                        )
                    except asyncio.CancelledError:
                        logger.info(f"[{thread_name}] ⚠️  Visit cancelled")
                        break
                    except Exception as e:
                        logger.error(f"[{thread_name}] Error visiting URL: {e}")
                        success = False
                    
                    visit_duration = (datetime.now() - visit_start).total_seconds()
                    
                    # Update progress after visiting URL (thread-safe callback)
                    if self.bot_instance and hasattr(self.bot_instance, 'update_progress'):
                        self.bot_instance.update_progress(1)
                    
                    # Record response for adaptive throttling
                    self.throttler.record_response(visit_duration, success)
                    
                    # Log visit (async, non-blocking file I/O)
                    async with self.stats_lock:
                        await self.tracker.log_visit_async(url, success, visit_duration, proxy_url)
                    
                    if success:
                        successful_count += 1
                        logger.info(f"[{thread_name}] ✅ SUCCESS - Status: OK | Time: {visit_duration:.1f}s")
                    else:
                        failed_count += 1
                        logger.warning(f"[{thread_name}] ❌ FAILED - Status: Error | Time: {visit_duration:.1f}s")
                    
                    # Update proxy stats
                    self.proxy_manager.update_proxy_stats(proxy_url, success)
                    
                    # If proxy failed, check if it should be replaced
                    if not success:
                        # Check if proxy is now dead
                        if proxy_url in self.proxy_manager.dead_proxies:
                            logger.warning(f"[{thread_name}] ⚠ Proxy marked as dead - continuing with remaining URLs")
                            # Continue with remaining URLs but proxy is dead
                    
                    # Check for stop before delay
                    if hasattr(self, '_should_stop') and callable(self._should_stop) and self._should_stop():
                        logger.info(f"[{thread_name}] ⚠️  Stop signal received, stopping before delay...")
                        break
                    
                    # Delay between URLs (with adaptive throttling)
                    if url_idx < len(urls_for_proxy):
                        base_delay = self.batch_delay + random.uniform(-self.batch_delay_variation, self.batch_delay_variation)
                        delay = self.throttler.get_adaptive_delay(base_delay)
                        delay = max(2, delay)
                        try:
                            # Check for cancellation periodically during sleep
                            elapsed = 0
                            check_interval = 0.5  # Check every 0.5 seconds
                            while elapsed < delay:
                                await asyncio.sleep(min(check_interval, delay - elapsed))
                                elapsed += check_interval
                                
                                # Check for stop signal during sleep
                                if hasattr(self, '_should_stop') and callable(self._should_stop) and self._should_stop():
                                    logger.info(f"[{thread_name}] ⚠️  Stop signal received during delay, stopping...")
                                    break
                                
                                # Check if task is cancelled
                                current_task = asyncio.current_task()
                                if current_task and current_task.cancelled():
                                    logger.info(f"[{thread_name}] ⚠️  Task cancelled during delay, stopping...")
                                    break
                        except asyncio.CancelledError:
                            logger.info(f"[{thread_name}] ⚠️  Delay cancelled, stopping...")
                            break
                
                except Exception as e:
                    failed_count += 1
                    is_recoverable = ErrorHandler.handle_browser_error(e, context=f"{thread_name}")
                    logger.error(f"[{thread_name}]    URL: {url}")
                    if not is_recoverable:
                        logger.error(f"[{thread_name}]    Full error: {str(e)[:200]}")
            
            # Update results
            results[proxy_index] = {
                'successful': successful_count,
                'failed': failed_count,
                'proxy': proxy_url
            }
            
            logger.info(f"[{thread_name}] 🏁 COMPLETED")
            logger.info(f"[{thread_name}]    ✅ Success: {successful_count} | ❌ Failed: {failed_count}")
        
        except Exception as e:
            error_msg = f"Critical error in worker: {str(e)}"
            logger.error(f"[{thread_name}] ❌ CRITICAL ERROR: {error_msg}")
            logger.exception(f"[{thread_name}] Full error traceback:")
            # If browser never started, mark all URLs as failed
            if successful_count == 0 and failed_count == 0:
                failed_count = len(urls_for_proxy)
            results[proxy_index] = {
                'successful': successful_count,
                'failed': failed_count,
                'proxy': proxy_url,
                'error': error_msg
            }
        
        finally:
            # Close browser
            if browser_manager:
                await browser_manager.close()
    
    async def visit_all(self):
        """Visit all URLs in parallel using multiple browsers"""
        try:
            # Prepare URLs
            urls_to_visit = list(self.urls)
            total_urls = len(urls_to_visit)
            
            # Check if we have URLs
            if total_urls == 0:
                logger.error("❌ No URLs to visit! Cannot proceed.")
                logger.error("Please check that your Excel file contains valid URLs.")
                return {
                    'total_successful': 0,
                    'total_failed': 0,
                    'total_visits': 0,
                    'results': {}
                }
            
            # Get proxies from the proxy manager (respects max_concurrent_proxies)
            proxies = self.proxy_manager.get_all_proxies()
            
            if not proxies:
                logger.warning("⚠ No proxies available. Falling back to sequential mode.")
                from traffic_bot.visitors.batch_visitor import BatchVisitor
                batch_visitor = BatchVisitor(self.config, self.urls, self.url_metadata)
                batch_result = await batch_visitor.visit_all()
                # Return compatible format
                return {
                    'total_successful': 0,  # BatchVisitor doesn't return stats, will be tracked separately
                    'total_failed': 0,
                    'total_visits': 0,
                    'results': {}
                }
            
            # Limit to max concurrent proxies (important for batch mode)
            # If proxy_manager was provided with a subset, it already has limited proxies
            # But we still respect max_concurrent_proxies setting
            num_proxies = min(len(proxies), self.max_concurrent_proxies)
            proxies_to_use = proxies[:num_proxies]
            
            logger.info(f"📊 Using {num_proxies} proxies (from {len(proxies)} available, max_concurrent={self.max_concurrent_proxies})")
            
            # Log parallel mode start
            logger.info("="*80)
            logger.info("🚀 PARALLEL MODE - All Proxies Visit ALL URLs Simultaneously")
            logger.info("="*80)
            logger.info(f"📊 URLs Per Proxy: {total_urls} (each proxy visits all URLs)")
            logger.info(f"🌐 Proxies Used: {num_proxies}")
            logger.info(f"📈 Total Visits: {num_proxies} proxies × {total_urls} URLs = {num_proxies * total_urls}")
            logger.info("="*80)
            logger.info("")
            
            # Distribute URLs (each proxy gets all URLs)
            url_distribution = {}
            for idx, proxy_url in enumerate(proxies_to_use):
                urls_copy = urls_to_visit.copy()
                if self.parallel_distribution == 'random':
                    random.shuffle(urls_copy)
                url_distribution[idx] = urls_copy
            
            # Log distribution
            logger.info("📋 Proxy Assignment (Each Proxy Visits ALL URLs):")
            for proxy_idx, proxy_url in enumerate(proxies_to_use):
                urls_count = len(url_distribution[proxy_idx])
                logger.info(f"   Proxy-{proxy_idx}: Visiting all {urls_count} URLs")
            logger.info("")
            
            # Create tasks for all proxies
            start_time = datetime.now()
            results = {}
            tasks = []
            
            for proxy_idx, proxy_url in enumerate(proxies_to_use):
                urls_for_proxy = url_distribution[proxy_idx]
                task = asyncio.create_task(
                    self._proxy_worker(proxy_url, proxy_idx, urls_for_proxy, results)
                )
                tasks.append(task)
            
            # Wait for all tasks to complete
            logger.info("🚀 Starting all proxy workers...")
            logger.info("")
            
            try:
                await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                logger.warning("⚠️  Parallel execution cancelled - waiting for tasks to cleanup...")
                # Wait a bit for tasks to complete their finally blocks
                # Use gather with return_exceptions=True to ensure all tasks complete cleanup
                await asyncio.gather(*tasks, return_exceptions=True)
                logger.info("✅ Cleanup completed")
                raise
            except Exception as e:
                logger.error(f"Error in parallel execution: {e}")
                # Ensure all tasks complete cleanup even on error
                await asyncio.gather(*tasks, return_exceptions=True)
                raise
            
            # Calculate final stats
            end_time = datetime.now()
            total_duration = (end_time - start_time).total_seconds()
            
            total_successful = sum(r.get('successful', 0) for r in results.values())
            total_failed = sum(r.get('failed', 0) for r in results.values())
            total_visits = total_successful + total_failed
            
            # Final summary
            logger.info("")
            logger.info("="*80)
            logger.info("🎉 PARALLEL EXECUTION COMPLETED")
            logger.info("="*80)
            logger.info(f"⏱️  Total Duration: {total_duration:.1f} seconds ({total_duration/60:.1f} minutes)")
            logger.info(f"📊 Total Visits: {total_visits} ({num_proxies} proxies × {total_urls} URLs)")
            logger.info(f"✅ Successful: {total_successful}/{total_visits}")
            logger.info(f"❌ Failed: {total_failed}/{total_visits}")
            logger.info(f"⚡ Speed: ~{total_visits/(total_duration/60):.1f} visits per minute")
            logger.info("")
            logger.info("📊 Results Per Proxy:")
            for proxy_idx in sorted(results.keys()):
                result = results[proxy_idx]
                proxy_url = result.get('proxy', 'Unknown')
                proxy_status = "❌ DEAD" if proxy_url in self.proxy_manager.dead_proxies else "✅ ACTIVE"
                logger.info(f"   Proxy-{proxy_idx} ({proxy_status}): ✅ {result.get('successful', 0)}/{total_urls} | ❌ {result.get('failed', 0)}/{total_urls}")
            
            # Proxy performance report
            logger.info("")
            logger.info("📈 Proxy Performance Report:")
            performance_report = self.proxy_manager.get_proxy_performance_report()
            working_proxies = self.proxy_manager.get_working_proxies()
            dead_proxies = self.proxy_manager.get_dead_proxies()
            
            logger.info(f"   ✅ Working Proxies: {len(working_proxies)}/{num_proxies}")
            logger.info(f"   ❌ Dead Proxies: {len(dead_proxies)}/{num_proxies}")
            
            if performance_report:
                logger.info("")
                logger.info("   Proxy Success Rates:")
                # Sort by success rate
                sorted_proxies = sorted(performance_report.items(), key=lambda x: x[1]['success_rate'], reverse=True)
                for proxy_url, stats in sorted_proxies[:10]:  # Show top 10
                    status_icon = "❌" if stats['status'] == 'dead' else "✅"
                    logger.info(f"   {status_icon} {stats['success_rate']:.1f}% success ({stats['success']}/{stats['total_requests']}) - {proxy_url[:50]}...")
            
            if dead_proxies:
                logger.info("")
                logger.info("   ⚠️  Dead Proxies (will be skipped in future runs):")
                for dead_proxy in dead_proxies[:5]:  # Show first 5 dead proxies
                    logger.info(f"   ❌ {dead_proxy[:60]}...")
                if len(dead_proxies) > 5:
                    logger.info(f"   ... and {len(dead_proxies) - 5} more dead proxies")
            
            logger.info("="*80)
            
            # Update traffic stats
            self.tracker.update_stats()
            self.tracker.generate_report()
            
            # Return results for batch statistics
            return {
                'total_successful': total_successful,
                'total_failed': total_failed,
                'total_visits': total_visits,
                'results': results
            }
        
        except Exception as e:
            logger.error(f"Error in parallel mode: {e}")
            raise

