"""Memory optimization module for browser instance management"""
import gc
import logging
import asyncio
from typing import Dict, Optional, List
from collections import deque
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class MemoryOptimizer:
    """Optimizes memory usage through browser pooling and cleanup"""
    
    def __init__(self, config: dict):
        """
        Initialize memory optimizer
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        memory_config = config.get('memory_optimization', {})
        
        # Memory optimization settings
        self.enabled = memory_config.get('enabled', True)
        self.browser_pool_size = memory_config.get('browser_pool_size', 5)
        self.max_browser_idle_time = memory_config.get('max_browser_idle_time_seconds', 300)
        self.cleanup_interval = memory_config.get('cleanup_interval_seconds', 60)
        self.force_gc_after_cleanup = memory_config.get('force_gc_after_cleanup', True)
        
        # Browser pool
        self.browser_pool: deque = deque(maxlen=self.browser_pool_size)
        self.active_browsers: Dict[str, Dict] = {}
        
        # Cleanup task
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # Statistics
        self.browsers_created = 0
        self.browsers_reused = 0
        self.browsers_closed = 0
        self.memory_freed_mb = 0.0
    
    async def get_browser_from_pool(self, proxy: Optional[str] = None):
        """
        Get browser from pool or create new one
        
        Args:
            proxy: Optional proxy URL
            
        Returns:
            Browser instance or None
        """
        if not self.enabled:
            return None
        
        # Try to find matching browser in pool
        for browser_entry in list(self.browser_pool):
            browser_data = browser_entry.get('browser')
            browser_proxy = browser_entry.get('proxy')
            last_used = browser_entry.get('last_used')
            
            # Check if browser matches proxy requirement
            if proxy == browser_proxy:
                # Check if browser is still usable
                if (datetime.now() - last_used).total_seconds() < self.max_browser_idle_time:
                    # Remove from pool
                    self.browser_pool.remove(browser_entry)
                    # Update last used
                    browser_entry['last_used'] = datetime.now()
                    self.active_browsers[id(browser_data)] = browser_entry
                    self.browsers_reused += 1
                    logger.debug(f"Reusing browser from pool (proxy: {proxy})")
                    return browser_data
        
        # No suitable browser in pool
        self.browsers_created += 1
        return None
    
    def return_browser_to_pool(self, browser, proxy: Optional[str] = None):
        """
        Return browser to pool for reuse
        
        Args:
            browser: Browser instance
            proxy: Proxy URL used by browser
        """
        if not self.enabled:
            return
        
        browser_id = id(browser)
        
        # Remove from active browsers
        if browser_id in self.active_browsers:
            del self.active_browsers[browser_id]
        
        # Add to pool if pool not full
        if len(self.browser_pool) < self.browser_pool_size:
            self.browser_pool.append({
                'browser': browser,
                'proxy': proxy,
                'last_used': datetime.now()
            })
            logger.debug(f"Browser returned to pool (pool size: {len(self.browser_pool)})")
        else:
            # Pool is full, close oldest browser
            oldest = self.browser_pool.popleft()
            self._close_browser_safe(oldest['browser'])
            # Add new browser to pool
            self.browser_pool.append({
                'browser': browser,
                'proxy': proxy,
                'last_used': datetime.now()
            })
    
    async def cleanup_idle_browsers(self):
        """Clean up idle browsers from pool"""
        if not self.enabled:
            return
        
        now = datetime.now()
        browsers_to_close = []
        
        # Find idle browsers
        for browser_entry in list(self.browser_pool):
            last_used = browser_entry.get('last_used')
            idle_time = (now - last_used).total_seconds()
            
            if idle_time > self.max_browser_idle_time:
                browsers_to_close.append(browser_entry)
        
        # Close idle browsers
        for browser_entry in browsers_to_close:
            self.browser_pool.remove(browser_entry)
            browser = browser_entry.get('browser')
            self._close_browser_safe(browser)
            self.browsers_closed += 1
            logger.debug(f"Closed idle browser (idle for {idle_time:.0f}s)")
        
        # Force garbage collection if enabled
        if self.force_gc_after_cleanup and browsers_to_close:
            collected = gc.collect()
            logger.debug(f"Garbage collection: {collected} objects collected")
    
    async def cleanup_loop(self):
        """Background cleanup loop"""
        if not self.enabled:
            return
        
        logger.info("🧹 Memory optimizer cleanup started")
        
        while True:
            try:
                await self.cleanup_idle_browsers()
                await asyncio.sleep(self.cleanup_interval)
            except asyncio.CancelledError:
                logger.info("Memory optimizer cleanup stopped")
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(self.cleanup_interval)
    
    def start_cleanup(self):
        """Start background cleanup task"""
        if self.enabled and self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self.cleanup_loop())
            logger.info("✅ Memory optimizer enabled")
    
    def stop_cleanup(self):
        """Stop background cleanup task"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            self.cleanup_task = None
            logger.info("Memory optimizer stopped")
    
    async def close_all_browsers(self):
        """Close all browsers in pool and active browsers"""
        # Close pool browsers
        for browser_entry in list(self.browser_pool):
            self.browser_pool.remove(browser_entry)
            browser = browser_entry.get('browser')
            await self._close_browser_safe_async(browser)
        
        # Close active browsers
        for browser_id, browser_entry in list(self.active_browsers.items()):
            browser = browser_entry.get('browser')
            await self._close_browser_safe_async(browser)
            del self.active_browsers[browser_id]
        
        logger.info("All browsers closed")
    
    def _close_browser_safe(self, browser):
        """Safely close browser (sync)"""
        try:
            # Browser should be closed via async method
            # This is a fallback for sync contexts
            pass
        except Exception as e:
            logger.debug(f"Error closing browser: {e}")
    
    async def _close_browser_safe_async(self, browser):
        """Safely close browser (async)"""
        try:
            if browser:
                if hasattr(browser, 'close'):
                    await browser.close()
                elif hasattr(browser, 'browser') and browser.browser:
                    await browser.browser.close()
        except Exception as e:
            logger.debug(f"Error closing browser: {e}")
    
    def get_memory_stats(self) -> Dict[str, any]:
        """
        Get memory optimization statistics
        
        Returns:
            Dictionary with memory stats
        """
        return {
            'pool_size': len(self.browser_pool),
            'active_browsers': len(self.active_browsers),
            'browsers_created': self.browsers_created,
            'browsers_reused': self.browsers_reused,
            'browsers_closed': self.browsers_closed,
            'reuse_rate': self.browsers_reused / max(1, self.browsers_created + self.browsers_reused)
        }

