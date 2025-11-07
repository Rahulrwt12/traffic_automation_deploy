#!/usr/bin/env python3
"""
Traffic Bot v2.0 - Browser-based traffic generation with analytics tracking
Uses Playwright for real browser automation with JavaScript execution
"""

import pandas as pd
import asyncio
import logging
import os
import json
import threading
from typing import List, Dict, Optional
from datetime import datetime, timedelta

# Load environment variables from .env file first (before any other imports that might need them)
try:
    from dotenv import load_dotenv
    # Try to load .env from current directory
    env_path = os.path.join(os.getcwd(), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not installed, will use environment variables directly

# Import modules
from traffic_bot.config.config_manager import ConfigManager
from traffic_bot.visitors.batch_visitor import BatchVisitor
from traffic_bot.visitors.parallel_visitor import ParallelVisitor
from traffic_bot.utils import ResourceMonitor, MemoryOptimizer
from traffic_bot.utils.url_utils import looks_like_url_series

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('traffic_bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Constants for timeout values
DEFAULT_EXECUTION_TIMEOUT = 86400  # 24 hours in seconds
DEFAULT_SHUTDOWN_TIMEOUT = 30.0  # 30 seconds

# Constants for batch delays
MINIMUM_BATCH_DELAY_MINUTES = 30  # Minimum delay between batches
COUNTDOWN_LOG_INTERVAL_SECONDS = 60  # Log countdown every minute
SLEEP_CHUNK_SECONDS = 60  # Sleep in 60s chunks for countdown


class TrafficBot:
    """Main Traffic Bot class using browser automation"""
    
    def __init__(self, config_file: str = 'config.json'):
        """
        Initialize the Traffic Bot from configuration file
        
        Args:
            config_file: Path to configuration JSON file
        """
        # Load configuration
        self.config_manager = ConfigManager(config_file)
        self.config = self.config_manager.config
        
        # Excel file settings
        excel_file_config = self.config.get('excel_file', '')
        if not excel_file_config:
            raise ValueError(
                "Excel file not configured in config.json.\n"
                "Please upload an Excel file through the web interface and click 'Save & Apply Excel File' before starting the bot."
            )
        
        # Resolve Excel file path (handle both relative and absolute paths)
        if os.path.isabs(excel_file_config):
            self.excel_file = excel_file_config
        else:
            # Try multiple possible locations
            config_dir = os.path.dirname(os.path.abspath(config_file))
            possible_paths = [
                excel_file_config,  # Current directory
                os.path.join(config_dir, excel_file_config),  # Same dir as config
                os.path.join(os.getcwd(), excel_file_config),  # Working directory
                os.path.join('/app', excel_file_config),  # Docker container path
            ]
            
            self.excel_file = None
            for path in possible_paths:
                if os.path.exists(path):
                    self.excel_file = path
                    logger.info(f"Found Excel file at: {path}")
                    break
            
            if not self.excel_file:
                # Use the first path as default (will show error in read_excel)
                self.excel_file = possible_paths[0]
                logger.warning(f"Excel file not found in any of these locations: {possible_paths}")
        
        self.product_url_column = self.config.get('product_url_column', 'Product URL')
        self.read_columns = self.config.get('read_columns', ['Product URL', 'product_url', 'URL', 'url'])
        
        # Mode settings
        self.mode = self.config.get('mode', 'batch')
        
        # URLs and metadata
        self.urls: List[str] = []
        self.url_metadata: Dict[str, Dict] = {}
        
        # Progress tracking with thread safety
        self._progress_lock = threading.Lock()
        self._current_url_index = 0
        self._total_urls = 0
        
        # Resource monitoring
        self.resource_monitor = ResourceMonitor(self.config)
        
        # Memory optimization
        self.memory_optimizer = MemoryOptimizer(self.config)
        
        # Load URLs from Excel
        self.read_excel()
    
    def resolve_mode(self) -> str:
        """
        Centralize mode resolution logic
        
        Returns:
            "parallel_batches" if automated batches enabled
            "parallel" if parallel mode enabled
            "batch" otherwise
        """
        p = self.config.get("parallel_mode", {})
        if p.get("enabled") and p.get("automated_batches", {}).get("enabled"):
            return "parallel_batches"
        if p.get("enabled"):
            return "parallel"
        return "batch"
    
    # ========================================================================
    # PROGRESS TRACKING (Thread-Safe)
    # ========================================================================
    
    def reset_progress(self):
        """Reset progress counters (call at start of bot run)"""
        with self._progress_lock:
            self._current_url_index = 0
            self._total_urls = len(self.urls) if self.urls else 0
            logger.debug(f"Progress reset: 0/{self._total_urls}")
    
    def update_progress(self, increment: int = 1):
        """
        Thread-safe progress update callback for visitors
        
        Args:
            increment: Number to increment progress by (default: 1)
        """
        with self._progress_lock:
            self._current_url_index += increment
            logger.debug(f"Progress updated: {self._current_url_index}/{self._total_urls}")
    
    @property
    def current_url_index(self) -> int:
        """Thread-safe getter for current progress"""
        with self._progress_lock:
            return self._current_url_index
    
    @property
    def total_urls(self) -> int:
        """Thread-safe getter for total URLs"""
        with self._progress_lock:
            return self._total_urls
    
    @property
    def progress_percent(self) -> float:
        """Calculate current progress percentage (thread-safe)"""
        with self._progress_lock:
            if self._total_urls == 0:
                return 0.0
            return (self._current_url_index / self._total_urls) * 100
    
    # ========================================================================
    
    def read_excel(self) -> List[str]:
        """
        Read product URLs from Excel file
        
        Returns:
            List of product URLs
            
        Raises:
            FileNotFoundError: If Excel file doesn't exist
        """
        try:
            logger.info(f"Reading Excel file: {self.excel_file}")
            logger.info(f"Current working directory: {os.getcwd()}")
            logger.info(f"Excel file exists: {os.path.exists(self.excel_file)}")
            
            # List files in current directory for debugging
            try:
                files_in_dir = os.listdir('.')
                excel_files = [f for f in files_in_dir if f.endswith(('.xlsx', '.xls'))]
                logger.info(f"Excel files found in current directory: {excel_files}")
            except Exception as e:
                logger.warning(f"Could not list directory: {e}")
            
            # Require Excel file to exist - no fallback
            if not os.path.exists(self.excel_file):
                error_msg = (
                    f"Excel file not found: {self.excel_file}\n"
                    f"Current directory: {os.getcwd()}\n"
                    f"Please upload an Excel file through the web interface and click 'Save & Apply Excel File' before starting the bot."
                )
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)
            
            # Try reading with different methods
            try:
                df = pd.read_excel(self.excel_file, engine='openpyxl')
            except Exception as e1:
                try:
                    df = pd.read_excel(self.excel_file, engine='xlrd')
                except Exception as e2:
                    raise Exception(f"Could not read Excel file. Tried openpyxl: {e1}, xlrd: {e2}")
            
            logger.info(f"Excel file loaded. Shape: {df.shape}")
            logger.info(f"Columns found: {df.columns.tolist()}")
            
            # Find URL column using hybrid approach: config first, then robust detection
            url_column = None
            
            # Step 1: Check exact match from config
            if self.product_url_column in df.columns:
                url_column = self.product_url_column
                logger.info(f"Found exact match: '{url_column}'")
            else:
                # Step 2: Try case-insensitive match
                for col in df.columns:
                    if col.strip().lower() == self.product_url_column.lower():
                        url_column = col
                        logger.info(f"Found case-insensitive match: '{url_column}'")
                        break
            
            # Step 3: Check from read_columns list
            if url_column is None:
                for possible_col in self.read_columns:
                    if possible_col in df.columns:
                        url_column = possible_col
                        logger.info(f"Found alternative column: '{url_column}'")
                        break
            
            # Step 4: Fallback to robust content-based detection
            if url_column is None:
                logger.warning(f"'{self.product_url_column}' column not found. Scanning columns for URL-like data...")
                for col in df.columns:
                    if len(df) > 0 and looks_like_url_series(df[col], sample=25):
                        url_column = col
                        logger.info(f"Found URL-like column: '{url_column}'")
                        break
            
            if url_column is None:
                raise ValueError(
                    f"Could not find any URL column.\n"
                    f"Available columns: {df.columns.tolist()}\n"
                    f"Please ensure your Excel file has a column containing URLs."
                )
            
            # Extract URLs and metadata
            urls = df[url_column].dropna().astype(str).tolist()
            
            # Try to extract product metadata if available
            product_name_col = None
            category_col = None
            
            if 'Product Name' in df.columns:
                product_name_col = 'Product Name'
            elif 'Product' in df.columns:
                product_name_col = 'Product'
            
            if 'Category' in df.columns:
                category_col = 'Category'
            
            # Filter valid URLs and store metadata
            valid_urls = []
            for idx, url in enumerate(urls):
                url = url.strip()
                
                # Skip invalid entries
                if url.lower() in ['nan', 'none', '', 'null']:
                    continue
                
                # Validate and normalize URL
                if url.startswith('http://') or url.startswith('https://'):
                    valid_url = url
                elif url.startswith('www.') or url.startswith('//'):
                    valid_url = 'https://' + url.lstrip('/')
                elif 'advancedenergy.com' in url.lower():
                    valid_url = 'https://' + url.lstrip('/')
                else:
                    logger.warning(f"Skipping invalid URL at row {idx + 1}: {url}")
                    continue
                
                valid_urls.append(valid_url)
                
                # Store metadata if available
                metadata = {'row_index': idx + 1}
                if product_name_col:
                    metadata['product_name'] = str(df[product_name_col].iloc[idx]) if idx < len(df) else 'Unknown'
                if category_col:
                    metadata['category'] = str(df[category_col].iloc[idx]) if idx < len(df) else 'Unknown'
                
                self.url_metadata[valid_url] = metadata
            
            self.urls = valid_urls
            
            if len(self.urls) == 0:
                raise ValueError(
                    f"No valid URLs found in Excel file.\n"
                    f"Column used: '{url_column}'\n"
                    f"Total rows: {len(df)}\n"
                    f"Please check that your Excel file contains valid Product URLs."
                )
            
            logger.info(f"✓ Successfully loaded {len(self.urls)} valid product URLs from column '{url_column}'")
            
            # Log sample URLs
            if len(self.urls) > 0:
                logger.info(f"Sample URLs:")
                for i, url in enumerate(self.urls[:3]):
                    metadata = self.url_metadata.get(url, {})
                    product_name = metadata.get('product_name', 'N/A')
                    logger.info(f"  {i+1}. {product_name}: {url}")
                if len(self.urls) > 3:
                    logger.info(f"  ... and {len(self.urls) - 3} more")
            
            return self.urls
            
        except FileNotFoundError as e:
            logger.error(f"File error: {e}")
            raise
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error reading Excel file: {e}")
            logger.exception("Full error trace:")
            raise
    
    async def _cancel_background_tasks_with_timeout(self, timeout: float):
        """
        Cancel background tasks (monitor, cleanup) with timeout protection
        
        Args:
            timeout: Maximum time to wait for cancellation
        """
        tasks_to_cancel = []
        
        # Collect background tasks
        if self.resource_monitor.monitoring_task and not self.resource_monitor.monitoring_task.done():
            tasks_to_cancel.append(self.resource_monitor.monitoring_task)
        if self.memory_optimizer.cleanup_task and not self.memory_optimizer.cleanup_task.done():
            tasks_to_cancel.append(self.memory_optimizer.cleanup_task)
        
        if not tasks_to_cancel:
            return
        
        # Cancel all background tasks
        for task in tasks_to_cancel:
            task.cancel()
        
        # Wait for cancellation with timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks_to_cancel, return_exceptions=True),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning("⚠️  Background tasks didn't cancel cleanly, forcing browser kill...")
            await self._force_kill_browsers()
    
    async def _force_kill_browsers(self):
        """Force kill all browsers if they hang during shutdown"""
        try:
            logger.warning("⚠️  Force killing browsers due to timeout/hang...")
            # Force close all browsers through memory optimizer
            await self.memory_optimizer.close_all_browsers()
            
            # Also try to kill browser processes directly via resource monitor
            import psutil
            browser_pids = getattr(self.resource_monitor, 'browser_processes', [])
            for pid in browser_pids[:]:
                try:
                    proc = psutil.Process(pid)
                    proc.terminate()
                    logger.warning(f"   Terminated browser process PID: {pid}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass  # Process already dead
                except Exception as e:
                    logger.debug(f"   Error killing process {pid}: {e}")
        except Exception as e:
            logger.error(f"Error during force browser kill: {e}")
    
    async def _run_visitor_with_timeout(self, visitor_task: asyncio.Task, timeout_seconds: Optional[float] = None):
        """
        Run visitor task with timeout protection and graceful shutdown
        
        Args:
            visitor_task: Task to execute (created from visitor.visit_all())
            timeout_seconds: Maximum time to wait (None = no timeout)
        
        Returns:
            Result from visitor or None if timeout/cancelled
        """
        if timeout_seconds is None:
            # Use config or default timeout (24 hours max)
            timeout_seconds = self.config.get('shutdown_timeout_seconds', DEFAULT_EXECUTION_TIMEOUT)
        
        try:
            return await asyncio.wait_for(visitor_task, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.error(f"❌ Visitor execution timed out after {timeout_seconds}s")
            logger.error("   This may indicate hung browsers or network issues")
            visitor_task.cancel()
            # Give it a moment to cancel gracefully
            try:
                await asyncio.wait_for(asyncio.gather(visitor_task, return_exceptions=True), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("   Task didn't cancel cleanly, forcing browser kill...")
            await self._force_kill_browsers()
            raise
        except asyncio.CancelledError:
            logger.warning("⚠️  Visitor execution cancelled")
            await self._force_kill_browsers()
            raise
        except Exception as e:
            logger.error(f"❌ Visitor execution error: {e}")
            visitor_task.cancel()
            try:
                await asyncio.wait_for(asyncio.gather(visitor_task, return_exceptions=True), timeout=5.0)
            except asyncio.TimeoutError:
                await self._force_kill_browsers()
            raise
    
    async def run(self):
        """
        Main entry point - routes to appropriate mode with timeout protection
        
        Uses asyncio.gather with return_exceptions=True to handle all tasks safely.
        All tasks are wrapped with timeout protection and can be cancelled cleanly.
        """
        # Get shutdown timeout from config
        shutdown_timeout = self.config.get('shutdown_timeout_seconds', DEFAULT_SHUTDOWN_TIMEOUT)
        execution_timeout = self.config.get('execution_timeout_seconds', DEFAULT_EXECUTION_TIMEOUT)
        
        # Start background tasks (monitor and cleanup)
        self.resource_monitor.start_monitoring()
        self.memory_optimizer.start_cleanup()
        
        visitor_task = None
        
        try:
            # Resolve execution mode using centralized logic
            execution_mode = self.resolve_mode()
            
            # Check if we have URLs before starting
            if len(self.urls) == 0:
                error_msg = (
                    "No URLs loaded from Excel file. Cannot start bot.\n"
                    f"Excel file: {self.excel_file}\n"
                    "Please ensure:\n"
                    "1. Excel file exists and is accessible\n"
                    "2. Excel file contains a column with URLs\n"
                    "3. URLs are valid (start with http:// or https://)"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            logger.info(f"✅ Bot initialized with {len(self.urls)} URLs")
            
            # Reset progress tracking for this run
            self.reset_progress()
            
            # Create visitor task based on mode
            if execution_mode == "parallel_batches":
                logger.info("🚀 Starting AUTOMATED BATCH MODE - Multiple sessions with delays")
                visitor_task = asyncio.create_task(self._run_automated_batches())
            elif execution_mode == "parallel":
                logger.info("🚀 Starting PARALLEL mode with browser automation")
                parallel_visitor = ParallelVisitor(self.config, self.urls, self.url_metadata, bot_instance=self)
                visitor_task = asyncio.create_task(parallel_visitor.visit_all())
            else:  # execution_mode == "batch"
                logger.info("🚀 Starting BATCH mode with browser automation")
                batch_visitor = BatchVisitor(self.config, self.urls, self.url_metadata, bot_instance=self)
                visitor_task = asyncio.create_task(batch_visitor.visit_all())
            
            # Execute visitor with timeout protection
            if visitor_task:
                try:
                    await asyncio.wait_for(visitor_task, timeout=execution_timeout)
                except asyncio.TimeoutError:
                    logger.error(f"❌ Visitor execution timed out after {execution_timeout}s")
                    logger.error("   This may indicate hung browsers or network issues")
                    visitor_task.cancel()
                    # Wait for cancellation with timeout
                    try:
                        await asyncio.wait_for(
                            asyncio.gather(visitor_task, return_exceptions=True),
                            timeout=shutdown_timeout
                        )
                    except asyncio.TimeoutError:
                        logger.warning("   Visitor didn't cancel cleanly, forcing browser kill...")
                        await self._force_kill_browsers()
                    raise
        
        except KeyboardInterrupt:
            logger.info("\n" + "="*60)
            logger.info("⚠️  Bot stopped by user")
            logger.info("="*60)
            if visitor_task:
                visitor_task.cancel()
                await self._cancel_background_tasks_with_timeout(shutdown_timeout)
        
        except asyncio.CancelledError:
            logger.info("\n" + "="*60)
            logger.info("⚠️  Bot execution cancelled")
            logger.info("="*60)
            if visitor_task:
                visitor_task.cancel()
                await self._cancel_background_tasks_with_timeout(shutdown_timeout)
            raise
        
        except Exception as e:
            logger.error(f"❌ Fatal error: {e}")
            logger.exception("Full error trace:")
            if visitor_task:
                visitor_task.cancel()
                await self._cancel_background_tasks_with_timeout(shutdown_timeout)
            raise
        
        finally:
            # Stop resource monitoring
            self.resource_monitor.stop_monitoring()
            
            # Stop memory optimizer and close browsers
            self.memory_optimizer.stop_cleanup()
            await self.memory_optimizer.close_all_browsers()
            
            # Log final resource summary
            summary = self.resource_monitor.get_summary()
            if summary.get('status') == 'active':
                logger.info("")
                logger.info("📊 Final Resource Summary:")
                logger.info(f"   CPU Avg: {summary['cpu_avg']:.1f}% | Max: {summary['cpu_max']:.1f}%")
                logger.info(f"   Memory Avg: {summary['memory_avg']:.1f}% | Max: {summary['memory_max']:.1f}%")
                logger.info(f"   Browser Instances: {summary['browser_count']}")
            
            # Log memory optimization stats
            memory_stats = self.memory_optimizer.get_memory_stats()
            logger.info("")
            logger.info("💾 Memory Optimization Stats:")
            logger.info(f"   Browsers Created: {memory_stats['browsers_created']}")
            logger.info(f"   Browsers Reused: {memory_stats['browsers_reused']}")
            logger.info(f"   Reuse Rate: {memory_stats['reuse_rate']*100:.1f}%")
    
    async def _run_automated_batches(self):
        """Run proxies in automated batches with delays between batches"""
        import random
        from traffic_bot.proxy.proxy_manager import ProxyManager
        
        # Get configuration
        parallel_config = self.config.get('parallel_mode', {})
        automated_batches = parallel_config.get('automated_batches', {})
        proxies_per_batch = automated_batches.get('proxies_per_batch', 25)
        delay_minutes = automated_batches.get('delay_between_batches_minutes', 45)
        delay_variation = automated_batches.get('delay_variation_minutes', 15)
        
        # Load all proxies
        proxy_manager = ProxyManager(self.config)
        all_proxies = proxy_manager.get_all_proxies()
        
        if not all_proxies:
            logger.error("❌ No proxies available! Cannot run automated batches.")
            return
        
        total_proxies = len(all_proxies)
        total_batches = (total_proxies + proxies_per_batch - 1) // proxies_per_batch  # Ceiling division
        
        logger.info("="*80)
        logger.info("🔄 AUTOMATED BATCH MODE - Sequential Proxy Batches")
        logger.info("="*80)
        logger.info(f"📊 Total Proxies: {total_proxies}")
        logger.info(f"📦 Proxies Per Batch: {proxies_per_batch}")
        logger.info(f"🔢 Total Batches: {total_batches}")
        logger.info(f"⏱️  Delay Between Batches: {delay_minutes} min ± {delay_variation} min")
        logger.info(f"📈 URLs Per Batch: {len(self.urls)}")
        logger.info(f"🎯 Total Visits: {total_proxies} proxies × {len(self.urls)} URLs = {total_proxies * len(self.urls)}")
        logger.info("="*80)
        logger.info("")
        
        # Track overall statistics
        overall_start_time = datetime.now()
        total_successful = 0
        total_failed = 0
        
        # Process each batch
        for batch_num in range(total_batches):
            start_idx = batch_num * proxies_per_batch
            end_idx = min(start_idx + proxies_per_batch, total_proxies)
            batch_proxies = all_proxies[start_idx:end_idx]
            
            logger.info("")
            logger.info("="*80)
            logger.info(f"📦 BATCH {batch_num + 1}/{total_batches}")
            logger.info("="*80)
            logger.info(f"🔢 Proxies in this batch: {len(batch_proxies)} (Proxy {start_idx + 1} to {end_idx})")
            logger.info(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("="*80)
            logger.info("")
            
            # Create a temporary config with only this batch's proxies
            batch_config = self.config.copy()
            batch_config['parallel_mode'] = batch_config.get('parallel_mode', {}).copy()
            batch_config['parallel_mode']['max_concurrent_proxies'] = len(batch_proxies)
            
            # Create ProxyManager with subset of proxies for this batch
            # This gives us all the features: smart rotation, failure tracking, stats, etc.
            batch_proxy_manager = ProxyManager(batch_config, proxy_list=batch_proxies)
            
            # Create parallel visitor with batch proxy manager (pass it directly to avoid creating another)
            parallel_visitor = ParallelVisitor(batch_config, self.urls, self.url_metadata, proxy_manager=batch_proxy_manager, bot_instance=self)
            
            # Run this batch
            batch_start_time = datetime.now()
            visitor_results = await parallel_visitor.visit_all()
            batch_duration = (datetime.now() - batch_start_time).total_seconds()
            
            # Get batch statistics from visitor results (most accurate)
            if visitor_results:
                batch_successful = visitor_results.get('total_successful', 0)
                batch_failed = visitor_results.get('total_failed', 0)
            else:
                # Fallback to proxy stats if visitor didn't return results
                batch_successful = sum(stats.get('success', 0) for stats in batch_proxy_manager.proxy_stats.values())
                batch_failed = sum(stats.get('failed', 0) for stats in batch_proxy_manager.proxy_stats.values())
            
            # If batch shows 0 visits, check if there were any errors in browser startup
            # This handles cases where browsers fail to start silently
            if batch_successful == 0 and batch_failed == 0:
                logger.warning("⚠️  Batch completed with 0 visits - this may indicate browser startup failures")
                logger.warning("   Check logs above for browser startup errors")
                logger.warning("   In Docker environments, ensure browsers are properly installed")
                logger.warning("   Consider using Chromium instead of Firefox for better Docker compatibility")
                logger.warning("   Firefox headful mode is not supported in Docker - use headless mode or Chromium")
            
            total_successful += batch_successful
            total_failed += batch_failed
            
            logger.info("")
            logger.info("="*80)
            logger.info(f"✅ BATCH {batch_num + 1}/{total_batches} COMPLETED")
            logger.info("="*80)
            logger.info(f"⏱️  Batch Duration: {batch_duration/60:.1f} minutes")
            logger.info(f"✅ Successful: {batch_successful} | ❌ Failed: {batch_failed}")
            logger.info(f"📊 Overall Progress: {total_successful} successful, {total_failed} failed")
            logger.info("="*80)
            
            # Wait before next batch (except for the last batch)
            if batch_num < total_batches - 1:
                delay = delay_minutes + random.uniform(-delay_variation, delay_variation)
                delay = max(MINIMUM_BATCH_DELAY_MINUTES, delay)  # Minimum delay
                delay_seconds = delay * 60
                
                logger.info("")
                logger.info("="*80)
                logger.info(f"⏳ WAITING {delay:.1f} MINUTES BEFORE NEXT BATCH...")
                logger.info(f"📅 Next batch will start at: {(datetime.now() + timedelta(seconds=delay_seconds)).strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info("="*80)
                logger.info("")
                
                # Show countdown
                remaining = delay_seconds
                while remaining > 0:
                    minutes = int(remaining // COUNTDOWN_LOG_INTERVAL_SECONDS)
                    seconds = int(remaining % COUNTDOWN_LOG_INTERVAL_SECONDS)
                    if remaining % COUNTDOWN_LOG_INTERVAL_SECONDS == 0 or remaining == delay_seconds:  # Log every minute
                        logger.info(f"⏳ Waiting... {minutes}m {seconds}s remaining")
                    await asyncio.sleep(min(SLEEP_CHUNK_SECONDS, remaining))  # Sleep in chunks
                    remaining -= min(SLEEP_CHUNK_SECONDS, remaining)
        
        # Final summary
        total_duration = (datetime.now() - overall_start_time).total_seconds()
        logger.info("")
        logger.info("="*80)
        logger.info("🎉 ALL BATCHES COMPLETED!")
        logger.info("="*80)
        logger.info(f"📊 Total Batches: {total_batches}")
        logger.info(f"⏱️  Total Duration: {total_duration/3600:.1f} hours ({total_duration/60:.1f} minutes)")
        logger.info(f"✅ Total Successful: {total_successful}")
        logger.info(f"❌ Total Failed: {total_failed}")
        logger.info(f"📈 Total Visits: {total_successful + total_failed}")
        logger.info("="*80)


def main():
    """Main entry point"""
    try:
        config_file = 'config.json'
        
        if not os.path.exists(config_file):
            logger.warning(f"Config file {config_file} not found. Creating default config...")
            # Create default config
            default_config = {
                "excel_file": "advanced_energy_products_dynamic.xlsx",
                "product_url_column": "Product URL",
                "delay_minutes": 5,
                "target_domain": "www-qa.advancedenergy.com",
                "min_delay_seconds": 120,
                "max_retries": 3,
                "timeout_seconds": 30,
                "enable_proxy_rotation": True,
                "proxy_file": "proxies.json",
                "log_file": "traffic_bot.log",
                "log_level": "INFO",
                "mode": "batch",
                "batch_mode": {
                    "enabled": True,
                    "delay_between_urls_seconds": 7,
                    "delay_variation_seconds": 4,
                    "reading_time_min": 3,
                    "reading_time_max": 8,
                    "pre_request_delay_min": 1,
                    "pre_request_delay_max": 3,
                    "shuffle_urls": True,
                    "batch_size": None
                },
                "parallel_mode": {
                    "enabled": True,
                    "max_concurrent_proxies": 10,
                    "distribution": "round-robin"
                },
                "browser": {
                    "headless": False,
                    "browser_type": "chromium",
                    "timeout": 30000,
                    "wait_until": "networkidle",
                    "stealth_mode": True,
                    "fingerprint_randomization": True
                },
                "behavior": {
                    "mouse_movements": True,
                    "scrolling": True,
                    "click_interactions": True,
                    "scroll_pattern": "progressive",
                    "mouse_movement_chance": 0.7,
                    "click_chance": 0.3,
                    "scroll_delay_min": 0.5,
                    "scroll_delay_max": 2.0
                },
                "track_traffic": True,
                "traffic_log_file": "traffic_history.json",
                "traffic_stats_file": "traffic_stats.json"
            }
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            logger.info(f"Created default config file: {config_file}")
        
        # Initialize bot with config
        bot = TrafficBot(config_file)
        
        # Run bot (async)
        asyncio.run(bot.run())
        
    except KeyboardInterrupt:
        logger.info("\nBot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.exception("Full error trace:")
        raise


if __name__ == '__main__':
    main()

