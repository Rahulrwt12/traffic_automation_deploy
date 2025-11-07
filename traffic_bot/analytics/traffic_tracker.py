"""Traffic tracking and analytics module"""
import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class TrafficTracker:
    """Tracks traffic visits and generates statistics"""
    
    def __init__(self, config: dict):
        """
        Initialize traffic tracker
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.traffic_enabled = config.get('track_traffic', True)
        self.traffic_log_file = config.get('traffic_log_file', 'traffic_history.json')
        self.traffic_stats_file = config.get('traffic_stats_file', 'traffic_stats.json')
        
        # History retention: keep last 7 days (aligns with window calculations)
        # This ensures rolling windows (5/10/60 min) always have consistent data
        self.history_retention_days = config.get('history_retention_days', 7)
        # Fallback: also limit to max visits to prevent excessive memory usage
        self.max_history_visits = config.get('max_history_visits', 50000)
        
        # Database support
        self.db = None
        self.db_session_id = None
        self.use_database = config.get('database', {}).get('enabled', False)
        
        if self.use_database:
            try:
                from traffic_bot.database.db_manager import DatabaseManager
                self.db = DatabaseManager(config)
                if self.db.enabled:
                    # Create/verify database tables
                    self.db.create_tables()
                    
                    # Create a session for this bot run
                    self.db_session_id = self.db.create_session()
                    logger.info(f"✅ Database session created: Session ID #{self.db_session_id}")
                    logger.info("")
                else:
                    self.use_database = False
                    logger.info("Database manager initialized but disabled, using JSON fallback")
            except Exception as e:
                logger.warning(f"⚠️  Failed to initialize database, using JSON fallback: {e}")
                logger.warning("")
                self.use_database = False
        
        # Session stats
        self.session_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'blocked_requests': 0,
            'urls_visited': [],
            'start_time': datetime.now().isoformat()
        }
        
        if self.traffic_enabled:
            self._init_traffic_tracking()
    
    def _init_traffic_tracking(self):
        """Initialize traffic tracking files (only if database is not enabled)"""
        # Only create JSON files if database is not enabled
        # If database is enabled, we'll use PostgreSQL and only fall back to JSON on errors
        if self.use_database and self.db and self.db.enabled:
            logger.debug("Database enabled, skipping JSON file initialization")
            return
        
        # Only initialize JSON files if database is disabled
        if not os.path.exists(self.traffic_log_file):
            with open(self.traffic_log_file, 'w') as f:
                json.dump([], f)
        
        if not os.path.exists(self.traffic_stats_file):
            default_stats = {
                'total_sessions': 0,
                'total_visits': 0,
                'total_unique_urls': 0,
                'first_visit': None,
                'last_visit': None,
                'sessions': [],
                'daily_stats': {}
            }
            with open(self.traffic_stats_file, 'w') as f:
                json.dump(default_stats, f, indent=2)
    
    def log_visit(self, url: str, success: bool, duration: float, proxy: Optional[str] = None):
        """Log a visit to traffic history (PostgreSQL or JSON)"""
        if not self.traffic_enabled:
            return
        
        # Try PostgreSQL first
        if self.use_database and self.db and self.db.enabled:
            try:
                self.db.log_visit(
                    url=url,
                    success=success,
                    duration=duration,
                    proxy=proxy,
                    session_id=self.db_session_id
                )
                # Update session stats (in-memory)
                self._update_session_stats(url, success)
                # Don't write to JSON if database succeeds
                return
            except Exception as e:
                logger.warning(f"Failed to log visit to database, falling back to JSON: {e}")
        
        # Fallback to JSON if database fails or is disabled
        visit_record = {
            'timestamp': datetime.now().isoformat(),
            'url': url,
            'success': success,
            'duration_seconds': round(duration, 2),
            'proxy': proxy[:50] + '...' if proxy and len(proxy) > 50 else proxy
        }
        
        # Load existing history
        try:
            with open(self.traffic_log_file, 'r') as f:
                history = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not load traffic history: {e}. Starting with empty history.")
            history = []
        
        # Add new visit
        history.append(visit_record)
        
        # Truncate history using TIME-BASED approach (not count-based)
        # This ensures window calculations are stable and don't jump
        now = datetime.now()
        cutoff_time = now - timedelta(days=self.history_retention_days)
        
        # Filter by timestamp first (time-based truncation)
        filtered_history = []
        for visit in history:
            try:
                visit_time = datetime.fromisoformat(visit.get('timestamp', ''))
                if visit_time >= cutoff_time:
                    filtered_history.append(visit)
            except (ValueError, TypeError):
                # Skip invalid timestamps (shouldn't happen, but handle gracefully)
                logger.debug(f"Skipping visit with invalid timestamp: {visit}")
                continue
        
        # Fallback: Also limit by count to prevent excessive memory usage
        # This ensures we don't keep millions of visits even if they're recent
        if len(filtered_history) > self.max_history_visits:
            # Keep most recent visits if we exceed max count
            filtered_history = filtered_history[-self.max_history_visits:]
        
        history = filtered_history
        
        # Save updated history
        try:
            # Use atomic write to prevent corruption
            temp_file = self.traffic_log_file + '.tmp'
            with open(temp_file, 'w') as f:
                json.dump(history, f, indent=2)
            os.replace(temp_file, self.traffic_log_file)
        except (IOError, OSError, PermissionError) as e:
            logger.error(f"Could not save traffic log: {e}")
            # Try to clean up temp file if it exists
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
        
        # Update session stats (in-memory tracking)
        self._update_session_stats(url, success)
    
    def _update_session_stats(self, url: str, success: bool):
        """Update in-memory session statistics"""
        self.session_stats['total_requests'] += 1
        # Track ALL URLs (both successful and failed) for proper analytics
        self.session_stats['urls_visited'].append(url)
        if success:
            self.session_stats['successful_requests'] += 1
        else:
            self.session_stats['failed_requests'] += 1
    
    async def log_visit_async(self, url: str, success: bool, duration: float, proxy: Optional[str] = None):
        """
        Async wrapper for log_visit that moves blocking I/O off the event loop.
        
        Uses PostgreSQL if enabled (fast), falls back to JSON file I/O.
        
        Args:
            url: URL that was visited
            success: Whether the visit was successful
            duration: Duration of the visit in seconds
            proxy: Optional proxy URL used for the visit
        """
        # If using database, log directly (non-blocking)
        if self.use_database and self.db and self.db.enabled:
            try:
                # Database operations are already async-safe with connection pooling
                await asyncio.to_thread(
                    self.db.log_visit,
                    url, success, duration, proxy, self.db_session_id
                )
                # Update in-memory stats
                self._update_session_stats(url, success)
                return
            except Exception as e:
                logger.warning(f"Failed to log visit to database, falling back to JSON: {e}")
        
        # Fallback: Run blocking JSON file I/O in a thread pool to avoid blocking event loop
        await asyncio.to_thread(self.log_visit, url, success, duration, proxy)
    
    def update_stats(self):
        """Update traffic statistics (PostgreSQL or JSON)"""
        if not self.traffic_enabled:
            return
        
        # If using database, update session
        if self.use_database and self.db and self.db.enabled and self.db_session_id:
            try:
                self.db.update_session(
                    self.db_session_id,
                    end_time=datetime.now(),
                    total_requests=self.session_stats['total_requests'],
                    successful_requests=self.session_stats['successful_requests'],
                    failed_requests=self.session_stats['failed_requests'],
                    blocked_requests=self.session_stats['blocked_requests'],
                    unique_urls_count=len(set(self.session_stats['urls_visited'])),
                    status='completed'
                )
                logger.info("✅ Session stats updated in database")
                return
            except Exception as e:
                logger.warning(f"Failed to update stats in database, falling back to JSON: {e}")
        
        try:
            # Load existing stats
            with open(self.traffic_stats_file, 'r') as f:
                stats = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not load traffic stats: {e}. Starting with default stats.")
            stats = {
                'total_sessions': 0,
                'total_visits': 0,
                'total_unique_urls': 0,
                'first_visit': None,
                'last_visit': None,
                'sessions': [],
                'daily_stats': {}
            }
        
        # Update session stats
        session_record = {
            'start_time': self.session_stats['start_time'],
            'end_time': datetime.now().isoformat(),
            'total_requests': self.session_stats['total_requests'],
            'successful_requests': self.session_stats['successful_requests'],
            'failed_requests': self.session_stats['failed_requests'],
            'blocked_requests': self.session_stats['blocked_requests'],
            'urls_visited': len(set(self.session_stats['urls_visited']))
        }
        
        stats['sessions'].append(session_record)
        stats['total_sessions'] = len(stats['sessions'])
        stats['total_visits'] += self.session_stats['total_requests']
        
        # Update first/last visit
        if stats['first_visit'] is None:
            stats['first_visit'] = self.session_stats['start_time']
        stats['last_visit'] = datetime.now().isoformat()
        
        # Update daily stats
        today = datetime.now().strftime('%Y-%m-%d')
        if today not in stats['daily_stats']:
            stats['daily_stats'][today] = {
                'visits': 0,
                'successful': 0,
                'failed': 0,
                'unique_urls': set()
            }
        
        stats['daily_stats'][today]['visits'] += self.session_stats['total_requests']
        stats['daily_stats'][today]['successful'] += self.session_stats['successful_requests']
        stats['daily_stats'][today]['failed'] += self.session_stats['failed_requests']
        
        # Add unique URLs from this session to daily stats
        session_unique_urls = set(self.session_stats['urls_visited'])
        if isinstance(stats['daily_stats'][today].get('unique_urls'), set):
            stats['daily_stats'][today]['unique_urls'].update(session_unique_urls)
        elif isinstance(stats['daily_stats'][today].get('unique_urls'), list):
            # Convert to set, update, then convert back
            existing_urls = set(stats['daily_stats'][today]['unique_urls'])
            existing_urls.update(session_unique_urls)
            stats['daily_stats'][today]['unique_urls'] = list(existing_urls)
        else:
            stats['daily_stats'][today]['unique_urls'] = list(session_unique_urls)
        
        # Update total unique URLs count across all sessions
        all_unique_urls = set()
        for day_stats in stats['daily_stats'].values():
            if isinstance(day_stats.get('unique_urls'), list):
                all_unique_urls.update(day_stats['unique_urls'])
            elif isinstance(day_stats.get('unique_urls'), set):
                all_unique_urls.update(day_stats['unique_urls'])
        stats['total_unique_urls'] = len(all_unique_urls)
        
        # Convert sets to lists for JSON serialization
        for day, day_stats in stats['daily_stats'].items():
            if isinstance(day_stats.get('unique_urls'), set):
                day_stats['unique_urls'] = list(day_stats['unique_urls'])
        
        # Keep last 100 sessions
        if len(stats['sessions']) > 100:
            stats['sessions'] = stats['sessions'][-100:]
        
        # Keep last 90 days of daily stats
        if len(stats['daily_stats']) > 90:
            sorted_days = sorted(stats['daily_stats'].keys())
            for old_day in sorted_days[:-90]:
                del stats['daily_stats'][old_day]
        
        # Save updated stats
        try:
            # Use atomic write to prevent corruption
            temp_file = self.traffic_stats_file + '.tmp'
            with open(temp_file, 'w') as f:
                json.dump(stats, f, indent=2)
            os.replace(temp_file, self.traffic_stats_file)
        except (IOError, OSError, PermissionError) as e:
            logger.error(f"Could not save traffic stats: {e}")
            # Try to clean up temp file if it exists
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
    
    def generate_report(self):
        """Generate and display traffic report"""
        if not self.traffic_enabled:
            return
        
        stats = None
        history = []
        
        # Try to load from database first if enabled
        if self.use_database and self.db and self.db.enabled:
            try:
                from sqlalchemy import text
                with self.db.get_session() as session:
                    # Get total visits
                    total_visits = session.execute(text("SELECT COUNT(*) FROM visit_logs")).scalar() or 0
                    
                    # Get total sessions
                    total_sessions = session.execute(text("SELECT COUNT(*) FROM sessions")).scalar() or 0
                    
                    # Get daily stats
                    daily_results = session.execute(text("""
                        SELECT 
                            TO_CHAR(date, 'YYYY-MM-DD') as date,
                            total_visits,
                            successful_visits,
                            failed_visits
                        FROM daily_stats
                        ORDER BY date DESC
                        LIMIT 7
                    """)).fetchall()
                    
                    daily_stats = {}
                    for row in daily_results:
                        daily_stats[row[0]] = {
                            'visits': row[1],
                            'successful': row[2],
                            'failed': row[3]
                        }
                    
                    # Get first and last visit
                    first_visit = session.execute(text(
                        "SELECT MIN(timestamp) FROM visit_logs"
                    )).scalar()
                    
                    last_visit = session.execute(text(
                        "SELECT MAX(timestamp) FROM visit_logs"
                    )).scalar()
                    
                    stats = {
                        'total_visits': total_visits,
                        'total_sessions': total_sessions,
                        'first_visit': first_visit.isoformat() if first_visit else None,
                        'last_visit': last_visit.isoformat() if last_visit else None,
                        'daily_stats': daily_stats,
                        'sessions': []
                    }
                    
                    # Get recent visits
                    history = self.db.get_recent_visits(limit=10)
            except Exception as e:
                logger.warning(f"Failed to load from database, falling back to JSON: {e}")
        
        # Fallback to JSON if database is not enabled or failed
        if stats is None:
            try:
                # Load stats
                with open(self.traffic_stats_file, 'r') as f:
                    stats = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError, IOError) as e:
                logger.warning(f"No traffic statistics available yet: {e}")
                return
            
            # Load recent history
            try:
                with open(self.traffic_log_file, 'r') as f:
                    history = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not load traffic history: {e}")
                history = []
        
        logger.info("")
        logger.info("="*60)
        logger.info("📈 TRAFFIC INCREASE REPORT")
        logger.info("="*60)
        
        # Overall stats
        logger.info(f"Total Sessions: {stats['total_sessions']}")
        logger.info(f"Total Visits: {stats['total_visits']}")
        
        if stats['first_visit']:
            first = datetime.fromisoformat(stats['first_visit'])
            logger.info(f"First Visit: {first.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if stats['last_visit']:
            last = datetime.fromisoformat(stats['last_visit'])
            logger.info(f"Last Visit: {last.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Current session stats
        logger.info("")
        logger.info("Current Session:")
        logger.info(f"  Visits: {self.session_stats['total_requests']}")
        logger.info(f"  Successful: {self.session_stats['successful_requests']}")
        logger.info(f"  Failed: {self.session_stats['failed_requests']}")
        logger.info(f"  Unique URLs: {len(set(self.session_stats['urls_visited']))}")
        
        # Daily stats
        if stats['daily_stats']:
            logger.info("")
            logger.info("Daily Statistics (Last 7 Days):")
            sorted_days = sorted(stats['daily_stats'].keys(), reverse=True)[:7]
            for day in sorted_days:
                day_stats = stats['daily_stats'][day]
                logger.info(f"  {day}: {day_stats['visits']} visits ({day_stats['successful']} successful)")
        
        # Recent visits (last 10)
        if history:
            logger.info("")
            logger.info("Recent Visits (Last 10):")
            for visit in history[-10:]:
                timestamp = datetime.fromisoformat(visit['timestamp']).strftime('%H:%M:%S')
                status = "✓" if visit['success'] else "✗"
                logger.info(f"  {timestamp} {status} {visit['url'][:60]}...")
        
        logger.info("="*60)
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get current session statistics"""
        return self.session_stats.copy()

