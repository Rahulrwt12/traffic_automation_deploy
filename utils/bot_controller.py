"""
Bot Controller for Streamlit app
Handles bot instance management and control
"""
import asyncio
import threading
import logging
import json
from typing import Optional, Dict
import sys
import os
import importlib.util
from datetime import datetime

# Add parent directory to path to import traffic_bot
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Import TrafficBot from traffic_bot.py file (not the package)
traffic_bot_file = os.path.join(parent_dir, 'traffic_bot.py')
spec = importlib.util.spec_from_file_location("traffic_bot_module", traffic_bot_file)
traffic_bot_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(traffic_bot_module)
TrafficBot = traffic_bot_module.TrafficBot


class BotController:
    """Controller for managing TrafficBot instance in Streamlit"""
    
    STATUS_FILE = 'bot_status.json'
    
    def __init__(self):
        self.bot: Optional[TrafficBot] = None
        self.bot_thread: Optional[threading.Thread] = None
        self.bot_loop: Optional[asyncio.AbstractEventLoop] = None
        self.is_running = False
        self.is_paused = False
        self.error_message: Optional[str] = None
        self._stop_flag = threading.Event()
        self._lock = threading.Lock()
        
        # Restore state from file if exists (for persistence across refreshes)
        self._restore_state()
        
    def start_bot(self, config_file: str = 'config.json') -> bool:
        """Start the bot in a separate thread"""
        if self.is_running:
            return False
        
        try:
            # Reset stop flag
            self._stop_flag.clear()
            
            # Initialize bot - this will load Excel file and URLs
            logging.info("Initializing TrafficBot...")
            self.bot = TrafficBot(config_file)
            
            # Check if bot has URLs loaded
            if not hasattr(self.bot, 'urls') or len(self.bot.urls) == 0:
                error_msg = "Bot initialized but no URLs were loaded. Please check Excel file configuration."
                logging.error(error_msg)
                self.error_message = error_msg
                self.is_running = False
                self._save_state()
                return False
            
            logging.info(f"Bot initialized successfully with {len(self.bot.urls)} URLs")
            self.is_running = True
            self.is_paused = False
            self.error_message = None
            
            # Run bot in a separate thread
            def run_bot():
                loop = None
                try:
                    # Create new event loop for this thread
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    self.bot_loop = loop
                    
                    # Run the bot
                    loop.run_until_complete(self.bot.run())
                except asyncio.CancelledError:
                    logging.info("Bot execution cancelled")
                except Exception as e:
                    self.error_message = str(e)
                    logging.error(f"Bot error: {e}")
                finally:
                    self.is_running = False
                    self.bot_loop = None
                    # Update state file when bot finishes
                    self._save_state()
                    if loop and not loop.is_closed():
                        try:
                            # Cancel any remaining tasks
                            pending = asyncio.all_tasks(loop)
                            for task in pending:
                                task.cancel()
                            if pending:
                                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                            loop.close()
                        except Exception as e:
                            logging.warning(f"Error closing event loop: {e}")
            
            # Use daemon=False to prevent thread from being killed on refresh
            # The thread will continue running even if Streamlit refreshes
            self.bot_thread = threading.Thread(target=run_bot, daemon=False)
            self.bot_thread.start()
            
            # Save state to file for persistence
            self._save_state()
            return True
            
        except Exception as e:
            self.error_message = str(e)
            self.is_running = False
            logging.error(f"Failed to start bot: {e}")
            return False
    
    def stop_bot(self) -> bool:
        """Stop the bot by cancelling all async tasks"""
        if not self.is_running:
            return False
        
        # Mark as stopping IMMEDIATELY before any async operations
        # This ensures UI updates immediately, preventing double-clicks
        self.is_running = False
        self.is_paused = False
        
        try:
            logging.info("Stop signal received, cancelling bot tasks...")
            
            # Set stop flag
            self._stop_flag.set()
            
            # Cancel all tasks in the event loop
            if self.bot_loop and not self.bot_loop.is_closed():
                try:
                    # Use call_soon_threadsafe to schedule cancellation from another thread
                    def cancel_all_tasks():
                        try:
                            loop = asyncio.get_event_loop()
                            tasks = [t for t in asyncio.all_tasks(loop) if not t.done()]
                            for task in tasks:
                                task.cancel()
                            logging.info(f"Cancelled {len(tasks)} running tasks")
                        except Exception as e:
                            logging.warning(f"Error cancelling tasks: {e}")
                    
                    self.bot_loop.call_soon_threadsafe(cancel_all_tasks)
                except Exception as e:
                    logging.warning(f"Error scheduling cancellation: {e}")
            
            logging.info("Stop signal sent - bot should stop within 0.5-2 seconds")
            
            # Update state file
            self._save_state()
            return True
            
        except Exception as e:
            self.error_message = str(e)
            logging.error(f"Failed to stop bot: {e}")
            # State already set to False above, but ensure it's still False
            self.is_running = False
            return False
    
    def get_status(self) -> Dict:
        """Get current bot status"""
        return {
            'is_running': self.is_running,
            'is_paused': self.is_paused,
            'error': self.error_message,
            'has_bot': self.bot is not None
        }
    
    def get_progress(self) -> Dict:
        """Get bot progress information (thread-safe)"""
        if not self.bot:
            return {
                'current_url_index': 0,
                'total_urls': 0,
                'progress_percent': 0.0
            }
        
        # Use thread-safe properties if available
        if hasattr(self.bot, 'current_url_index') and hasattr(self.bot, 'total_urls'):
            return {
                'current_url_index': self.bot.current_url_index,
                'total_urls': self.bot.total_urls,
                'progress_percent': self.bot.progress_percent
            }
        
        # Fallback for older bot instances
        total_urls = len(self.bot.urls) if hasattr(self.bot, 'urls') else 0
        current_index = getattr(self.bot, '_current_url_index', 0)
        progress = (current_index / total_urls * 100) if total_urls > 0 else 0.0
        
        return {
            'current_url_index': current_index,
            'total_urls': total_urls,
            'progress_percent': progress
        }
    
    def _save_state(self):
        """Save bot state to file for persistence across refreshes"""
        try:
            with self._lock:
                state = {
                    'is_running': self.is_running,
                    'is_paused': self.is_paused,
                    'error_message': self.error_message,
                    'last_updated': datetime.now().isoformat()
                }
                with open(self.STATUS_FILE, 'w') as f:
                    json.dump(state, f)
        except Exception as e:
            logging.warning(f"Failed to save bot state: {e}")
    
    def _restore_state(self):
        """Restore bot state from file if it exists"""
        try:
            if os.path.exists(self.STATUS_FILE):
                with open(self.STATUS_FILE, 'r') as f:
                    state = json.load(f)
                    # Restore state but don't recreate bot instance
                    # The bot thread might still be running from previous session
                    if state.get('is_running', False):
                        # Verify thread is actually running
                        if self.bot_thread and self.bot_thread.is_alive():
                            self.is_running = True
                            logging.info("Restored bot running state - bot is still running")
                        else:
                            self.is_running = False
                            logging.warning("Bot state file says running, but thread not found - resetting state")
                    else:
                        self.is_running = False
        except Exception as e:
            logging.warning(f"Failed to restore bot state: {e}")
            self.is_running = False

