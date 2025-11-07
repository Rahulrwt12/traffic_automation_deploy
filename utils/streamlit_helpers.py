"""
Helper functions for Streamlit dashboard
Handles data loading, formatting, and processing
"""
import json
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import streamlit as st
from pydantic import ValidationError

# Set up logging
logger = logging.getLogger(__name__)

# Constants
CACHE_TTL_SECONDS = 5  # Streamlit cache TTL for data refresh (traffic stats/history)
CACHE_TTL_CONFIG_SECONDS = 30  # Streamlit cache TTL for config (changes rarely)


def utc_to_local(utc_dt: datetime) -> datetime:
    """
    Convert UTC datetime to local timezone
    
    Args:
        utc_dt: UTC datetime (naive or timezone-aware)
        
    Returns:
        Local datetime (naive)
    """
    # If datetime is naive, assume it's UTC
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    
    # Convert to local time
    local_dt = utc_dt.astimezone()
    
    # Return as naive datetime (for compatibility with existing code)
    return local_dt.replace(tzinfo=None)

# Load environment variables from .env file first
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.getcwd(), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not installed

# Import config schema for validation
try:
    from traffic_bot.config.config_schema import TrafficBotConfig
except ImportError:
    # Fallback if import fails (shouldn't happen in normal usage)
    TrafficBotConfig = None


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)  # Cache for production stability
def load_traffic_stats(stats_file: str = 'traffic_stats.json') -> Optional[Dict]:
    """
    Load traffic statistics from PostgreSQL or JSON file (cached for 5 seconds)
    Tries PostgreSQL first, falls back to JSON if database is disabled
    """
    # Try PostgreSQL first
    try:
        config = load_config()
        if config and config.get('database', {}).get('enabled', False):
            from traffic_bot.database.db_manager import DatabaseManager
            db = DatabaseManager(config)
            
            if db.enabled:
                # Get stats from database
                # Calculate total visits and sessions from database
                from sqlalchemy import text
                with db.get_session() as session:
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
                            failed_visits,
                            unique_urls_count
                        FROM daily_stats
                        ORDER BY date DESC
                    """)).fetchall()
                    
                    daily_stats = {}
                    for row in daily_results:
                        daily_stats[row[0]] = {
                            'visits': row[1],
                            'successful': row[2],
                            'failed': row[3],
                            'unique_urls': []  # Simplified for now
                        }
                    
                    # Get first and last visit
                    first_visit = session.execute(text(
                        "SELECT MIN(timestamp) FROM visit_logs"
                    )).scalar()
                    
                    last_visit = session.execute(text(
                        "SELECT MAX(timestamp) FROM visit_logs"
                    )).scalar()
                    
                    result = {
                        'total_visits': total_visits,
                        'total_sessions': total_sessions,
                        'first_visit': first_visit.isoformat() if first_visit else None,
                        'last_visit': last_visit.isoformat() if last_visit else None,
                        'daily_stats': daily_stats,
                        'sessions': [],  # Simplified
                        '_source': 'postgresql'
                    }
                    logger.debug(f"✅ Loaded stats from PostgreSQL: {total_visits} visits, {total_sessions} sessions")
                    return result
    except Exception as e:
        logger.error(f"❌ Failed to load from PostgreSQL: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    # JSON fallback removed - we're using PostgreSQL only
    # Return None if database is not enabled or not available
    return None


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)  # Cache for production stability
def load_traffic_history(history_file: str = 'traffic_history.json', session_id: Optional[int] = None) -> List[Dict]:
    """
    Load traffic history from PostgreSQL or JSON file (cached for 5 seconds)
    Tries PostgreSQL first, falls back to JSON if database is disabled
    
    Args:
        history_file: JSON file path (fallback)
        session_id: Optional session ID to filter by. If None, returns all visits.
                    If provided, only returns visits from that session.
    """
    # Try PostgreSQL first
    try:
        config = load_config()
        if config and config.get('database', {}).get('enabled', False):
            from traffic_bot.database.db_manager import DatabaseManager
            db = DatabaseManager(config)
            
            if db.enabled:
                # Get visits from database, filtered by session_id if provided
                # Use larger limit when filtering by session to get all session data
                limit = 10000 if session_id is None else 50000
                history = db.get_recent_visits(limit=limit, session_id=session_id)
                # Return empty list if no history found (this is normal, not an error)
                return history if history else []
    except Exception as e:
        # Only log actual errors, not empty results
        logger.error(f"❌ Failed to load from PostgreSQL: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Return empty list instead of falling back to JSON
        return []
    
    # JSON fallback removed - we're using PostgreSQL only
    return []


@st.cache_data(ttl=CACHE_TTL_CONFIG_SECONDS, show_spinner=False)  # Config changes rarely, no spinner
def load_config(config_file: str = 'config.json') -> Optional[Dict]:
    """
    Load and validate configuration from JSON file (cached for 30 seconds)
    
    Returns:
        Dict with validated configuration, or None if file doesn't exist or validation fails
        
    Note:
        Validation errors are logged but don't crash the app to allow graceful degradation
    """
    # Try multiple paths
    possible_paths = [
        config_file,
        os.path.join(os.getcwd(), config_file),
        os.path.join('/app', config_file),  # Docker container path
    ]
    
    config_path = None
    for path in possible_paths:
        if os.path.exists(path):
            config_path = path
            break
    
    if not config_path:
        error_msg = f"Config file not found. Tried: {', '.join(possible_paths)}"
        st.error(f"⚠️ {error_msg}")
        print(f"ERROR: {error_msg}")
        print(f"Current working directory: {os.getcwd()}")
        print(f"Files in current directory: {os.listdir('.')}")
        return None
    
    try:
        # Load raw JSON
        with open(config_path, 'r') as f:
            raw_config = json.load(f)
        
        # Only log once at startup, not on every cache hit
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"✅ Config loaded from: {config_path}")
        
        # Validate with Pydantic schema if available
        if TrafficBotConfig is not None:
            try:
                validated_config = TrafficBotConfig(**raw_config)
                # Convert to dict for compatibility
                config_dict = validated_config.model_dump(exclude_none=False)
                logger.debug(f"✅ Configuration validated successfully")
                return config_dict
            except ValidationError as e:
                # Format validation errors
                error_messages = []
                for error in e.errors():
                    field_path = " -> ".join(str(loc) for loc in error["loc"])
                    error_msg = f"{field_path}: {error['msg']}"
                    if "input" in error:
                        error_msg += f" (got: {error['input']})"
                    error_messages.append(error_msg)
                
                error_summary = "\n".join(error_messages)
                # Log error - in Streamlit this will show in console/logs
                st.warning(f"⚠️ Configuration validation failed. Using raw config with warnings:\n```\n{error_summary}\n```")
                print(f"WARNING: Configuration validation failed:\n{error_summary}")
                # Return raw config anyway to allow app to function
                return raw_config
        
        # Fallback: return raw config if Pydantic not available
        return raw_config
        
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in config file {config_path}: {e}"
        st.error(f"❌ {error_msg}")
        print(f"ERROR: {error_msg}")
        return None
    except IOError as e:
        error_msg = f"Error reading config file {config_path}: {e}"
        st.error(f"❌ {error_msg}")
        print(f"ERROR: {error_msg}")
        return None
    except Exception as e:
        error_msg = f"Unexpected error loading config: {e}"
        st.error(f"❌ {error_msg}")
        print(f"ERROR: {error_msg}")
        import traceback
        traceback.print_exc()
        return None


def get_daily_stats_dataframe(stats: Dict, days: int = 30) -> pd.DataFrame:
    """Convert daily stats to pandas DataFrame"""
    if not stats or 'daily_stats' not in stats:
        return pd.DataFrame()
    
    daily_stats = stats['daily_stats']
    sorted_days = sorted(daily_stats.keys(), reverse=True)[:days]
    
    data = []
    for day in sorted_days:
        day_data = daily_stats[day]
        data.append({
            'date': day,
            'visits': day_data.get('visits', 0),
            'successful': day_data.get('successful', 0),
            'failed': day_data.get('failed', 0),
            'unique_urls': len(day_data.get('unique_urls', []))
        })
    
    if not data:
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    return df


def get_recent_visits_dataframe(history: List[Dict], limit: int = 100) -> pd.DataFrame:
    """Convert recent visits to pandas DataFrame with UTC to local time conversion"""
    if not history:
        return pd.DataFrame()
    
    recent = history[-limit:] if len(history) > limit else history
    
    data = []
    for visit in recent:
        # Convert timestamp from UTC to local time before adding to DataFrame
        timestamp_str = visit.get('timestamp', '')
        if timestamp_str:
            try:
                # Parse timestamp (assume UTC if naive)
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                # Convert to local time
                if timestamp.tzinfo is None:
                    timestamp = utc_to_local(timestamp)
                elif timestamp.tzinfo is not None:
                    timestamp = timestamp.astimezone().replace(tzinfo=None)
                timestamp_str = timestamp.isoformat()
            except (ValueError, TypeError):
                pass  # Keep original string if parsing fails
        
        data.append({
            'timestamp': timestamp_str,
            'url': visit.get('url', ''),
            'success': visit.get('success', False),
            'duration_seconds': visit.get('duration_seconds', 0),
            'proxy': visit.get('proxy', 'N/A')
        })
    
    if not data:
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    # Convert timestamps to datetime (now already in local time)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df.sort_values('timestamp', ascending=False)


def get_url_statistics(history: List[Dict]) -> pd.DataFrame:
    """Get statistics per URL"""
    if not history:
        return pd.DataFrame()
    
    url_stats = {}
    for visit in history:
        url = visit.get('url', '')
        if not url:
            continue
        
        if url not in url_stats:
            url_stats[url] = {
                'url': url,
                'total_visits': 0,
                'successful': 0,
                'failed': 0,
                'avg_duration': 0,
                'durations': []
            }
        
        url_stats[url]['total_visits'] += 1
        if visit.get('success', False):
            url_stats[url]['successful'] += 1
        else:
            url_stats[url]['failed'] += 1
        
        duration = visit.get('duration_seconds', 0)
        if duration > 0:
            url_stats[url]['durations'].append(duration)
    
    # Calculate averages
    for url, stats in url_stats.items():
        if stats['durations']:
            stats['avg_duration'] = sum(stats['durations']) / len(stats['durations'])
        del stats['durations']
    
    df = pd.DataFrame(list(url_stats.values()))
    if not df.empty:
        df = df.sort_values('total_visits', ascending=False)
    return df


def calculate_metrics(stats: Optional[Dict], history: List[Dict]) -> Dict:
    """Calculate key metrics for dashboard"""
    if not stats:
        return {
            'total_visits': 0,
            'total_sessions': 0,
            'success_rate': 0.0,
            'unique_urls': 0,
            'total_successful': 0,
            'total_failed': 0,
            'avg_duration': 0.0
        }
    
    total_visits = stats.get('total_visits', 0)
    total_sessions = stats.get('total_sessions', 0)
    
    # Calculate success rate from history
    if history:
        successful = sum(1 for v in history if v.get('success', False))
        total = len(history)
        success_rate = (successful / total * 100) if total > 0 else 0.0
        total_successful = successful
        total_failed = total - successful
        
        # Calculate average duration
        durations = [v.get('duration_seconds', 0) for v in history if v.get('duration_seconds', 0) > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0.0
    else:
        success_rate = 0.0
        total_successful = stats.get('sessions', [{}])[-1].get('successful_requests', 0) if stats.get('sessions') else 0
        total_failed = stats.get('sessions', [{}])[-1].get('failed_requests', 0) if stats.get('sessions') else 0
        avg_duration = 0.0
    
    # Get unique URLs
    unique_urls = len(set(v.get('url', '') for v in history if v.get('url'))) if history else 0
    
    return {
        'total_visits': total_visits,
        'total_sessions': total_sessions,
        'success_rate': success_rate,
        'unique_urls': unique_urls,
        'total_successful': total_successful,
        'total_failed': total_failed,
        'avg_duration': avg_duration
    }


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"


def format_number(num: int) -> str:
    """Format large numbers with commas"""
    return f"{num:,}"


# ============================================================================
# REAL-TIME METRICS FUNCTIONS (Phase 1)
# ============================================================================

@st.cache_data(ttl=3, show_spinner=False)  # Cache for 3 seconds for production stability
def get_realtime_metrics(history: List[Dict], window_minutes: int = 60, bot_running: bool = False) -> Dict:
    """
    Calculate real-time metrics for the dashboard
    
    Args:
        history: List of visit records
        window_minutes: Time window in minutes for real-time calculations
        bot_running: Whether the bot is currently running. If False, returns zeros.
        
    Returns:
        Dictionary with real-time metrics
    """
    # If bot is not running, return zeros for all real-time metrics
    if not bot_running:
        return {
            'visits_per_minute': 0.0,
            'visits_per_second': 0.0,
            'recent_visits_count': 0,
            'recent_success_rate': 0.0,
            'avg_response_time': 0.0,
            'recent_successful': 0,
            'recent_failed': 0
        }
    
    if not history:
        return {
            'visits_per_minute': 0.0,
            'visits_per_second': 0.0,
            'recent_visits_count': 0,
            'recent_success_rate': 0.0,
            'avg_response_time': 0.0,
            'recent_successful': 0,
            'recent_failed': 0
        }
    
    now = datetime.now()
    cutoff = now - timedelta(minutes=window_minutes)
    
    # Filter recent visits
    recent_visits = []
    for visit in history:
        try:
            # Parse timestamp and convert from UTC to local time
            timestamp = datetime.fromisoformat(visit.get('timestamp', ''))
            # If timestamp is naive, assume it's UTC and convert to local
            if timestamp.tzinfo is None:
                timestamp = utc_to_local(timestamp)
            elif timestamp.tzinfo is not None:
                # Already timezone-aware, convert to local
                timestamp = timestamp.astimezone().replace(tzinfo=None)
            if timestamp >= cutoff:
                recent_visits.append(visit)
        except (ValueError, TypeError):
            continue
    
    # If no recent visits in the time window, use ALL available data
    # This ensures metrics show something if data exists, even if it's older
    if not recent_visits and history:
        # Silently use all available data without logging
        recent_visits = history
    
    if not recent_visits:
        return {
            'visits_per_minute': 0.0,
            'visits_per_second': 0.0,
            'recent_visits_count': 0,
            'recent_success_rate': 0.0,
            'avg_response_time': 0.0,
            'recent_successful': 0,
            'recent_failed': 0
        }
    
    # Calculate time span for rate calculations
    try:
        oldest_timestamp = datetime.fromisoformat(recent_visits[0]['timestamp'])
        newest_timestamp = datetime.fromisoformat(recent_visits[-1]['timestamp'])
        time_span_minutes = max(1, (newest_timestamp - oldest_timestamp).total_seconds() / 60)
    except (ValueError, TypeError, KeyError):
        time_span_minutes = window_minutes
    
    visits_per_minute = len(recent_visits) / time_span_minutes
    visits_per_second = visits_per_minute / 60
    
    # Calculate success rate
    successful = sum(1 for v in recent_visits if v.get('success', False))
    recent_success_rate = (successful / len(recent_visits) * 100) if len(recent_visits) > 0 else 0.0
    
    # Calculate average response time
    durations = [v.get('duration_seconds', 0) for v in recent_visits if v.get('duration_seconds', 0) > 0]
    avg_response_time = sum(durations) / len(durations) if durations else 0.0
    
    return {
        'visits_per_minute': round(visits_per_minute, 2),
        'visits_per_second': round(visits_per_second, 3),
        'recent_visits_count': len(recent_visits),
        'recent_success_rate': round(recent_success_rate, 1),
        'avg_response_time': round(avg_response_time, 2),
        'recent_successful': successful,
        'recent_failed': len(recent_visits) - successful
    }


def get_rolling_window_data(history: List[Dict], window_minutes: int = 60, resolution_minutes: int = 1) -> pd.DataFrame:
    """
    Get data aggregated into time buckets for rolling window visualization
    
    Args:
        history: List of visit records
        window_minutes: Time window in minutes
        resolution_minutes: Resolution in minutes for each data point
        
    Returns:
        DataFrame with timestamp and visit counts
    """
    if not history:
        return pd.DataFrame(columns=['timestamp', 'visits', 'successful', 'failed', 'avg_duration'])
    
    now = datetime.now()
    cutoff = now - timedelta(minutes=window_minutes)
    
    # Filter recent visits
    recent_visits = []
    for visit in history:
        try:
            # Parse timestamp and convert from UTC to local time
            timestamp = datetime.fromisoformat(visit.get('timestamp', ''))
            # If timestamp is naive, assume it's UTC and convert to local
            if timestamp.tzinfo is None:
                timestamp = utc_to_local(timestamp)
            elif timestamp.tzinfo is not None:
                # Already timezone-aware, convert to local
                timestamp = timestamp.astimezone().replace(tzinfo=None)
            if timestamp >= cutoff:
                recent_visits.append({
                    'timestamp': timestamp,
                    'success': visit.get('success', False),
                    'duration': visit.get('duration_seconds', 0)
                })
        except (ValueError, TypeError):
            continue
    
    # If no recent visits in the time window, use ALL available data
    if not recent_visits and history:
        for visit in history:
            try:
                # Parse timestamp and convert from UTC to local time
                timestamp = datetime.fromisoformat(visit.get('timestamp', ''))
                # If timestamp is naive, assume it's UTC and convert to local
                if timestamp.tzinfo is None:
                    timestamp = utc_to_local(timestamp)
                elif timestamp.tzinfo is not None:
                    # Already timezone-aware, convert to local
                    timestamp = timestamp.astimezone().replace(tzinfo=None)
                recent_visits.append({
                    'timestamp': timestamp,
                    'success': visit.get('success', False),
                    'duration': visit.get('duration_seconds', 0)
                })
            except (ValueError, TypeError):
                continue
    
    if not recent_visits:
        return pd.DataFrame(columns=['timestamp', 'visits', 'successful', 'failed', 'avg_duration'])
    
    # Create time buckets
    buckets = {}
    for visit in recent_visits:
        # Round timestamp to resolution_minutes
        bucket_time = visit['timestamp'].replace(second=0, microsecond=0)
        bucket_minute = (bucket_time.minute // resolution_minutes) * resolution_minutes
        bucket_time = bucket_time.replace(minute=bucket_minute)
        
        if bucket_time not in buckets:
            buckets[bucket_time] = {
                'visits': 0,
                'successful': 0,
                'failed': 0,
                'durations': []
            }
        
        buckets[bucket_time]['visits'] += 1
        if visit['success']:
            buckets[bucket_time]['successful'] += 1
        else:
            buckets[bucket_time]['failed'] += 1
        
        if visit['duration'] > 0:
            buckets[bucket_time]['durations'].append(visit['duration'])
    
    # Convert to DataFrame
    data = []
    for timestamp, stats in sorted(buckets.items()):
        avg_duration = sum(stats['durations']) / len(stats['durations']) if stats['durations'] else 0.0
        data.append({
            'timestamp': timestamp,
            'visits': stats['visits'],
            'successful': stats['successful'],
            'failed': stats['failed'],
            'avg_duration': round(avg_duration, 2)
        })
    
    df = pd.DataFrame(data)
    return df.sort_values('timestamp')


def get_minute_by_minute_data(history: List[Dict], minutes: int = 30) -> pd.DataFrame:
    """
    Get visits aggregated by minute for the last N minutes
    
    Args:
        history: List of visit records
        minutes: Number of minutes to look back
        
    Returns:
        DataFrame with one row per minute
    """
    return get_rolling_window_data(history, window_minutes=minutes, resolution_minutes=1)


def get_second_by_second_data(history: List[Dict], seconds: int = 300) -> pd.DataFrame:
    """
    Get visits aggregated by second for the last N seconds (for high-frequency updates)
    
    Args:
        history: List of visit records
        seconds: Number of seconds to look back
        
    Returns:
        DataFrame with one row per second
    """
    if not history:
        return pd.DataFrame(columns=['timestamp', 'visits', 'successful', 'failed'])
    
    now = datetime.now()
    cutoff = now - timedelta(seconds=seconds)
    
    # Filter recent visits
    recent_visits = []
    for visit in history:
        try:
            # Parse timestamp and convert from UTC to local time
            timestamp = datetime.fromisoformat(visit.get('timestamp', ''))
            # If timestamp is naive, assume it's UTC and convert to local
            if timestamp.tzinfo is None:
                timestamp = utc_to_local(timestamp)
            elif timestamp.tzinfo is not None:
                # Already timezone-aware, convert to local
                timestamp = timestamp.astimezone().replace(tzinfo=None)
            if timestamp >= cutoff:
                recent_visits.append({
                    'timestamp': timestamp,
                    'success': visit.get('success', False)
                })
        except (ValueError, TypeError):
            continue
    
    # If no recent visits in the time window, use ALL available data
    if not recent_visits and history:
        for visit in history:
            try:
                # Parse timestamp and convert from UTC to local time
                timestamp = datetime.fromisoformat(visit.get('timestamp', ''))
                # If timestamp is naive, assume it's UTC and convert to local
                if timestamp.tzinfo is None:
                    timestamp = utc_to_local(timestamp)
                elif timestamp.tzinfo is not None:
                    # Already timezone-aware, convert to local
                    timestamp = timestamp.astimezone().replace(tzinfo=None)
                recent_visits.append({
                    'timestamp': timestamp,
                    'success': visit.get('success', False)
                })
            except (ValueError, TypeError):
                continue
    
    if not recent_visits:
        return pd.DataFrame(columns=['timestamp', 'visits', 'successful', 'failed'])
    
    # Create second buckets
    buckets = {}
    for visit in recent_visits:
        bucket_time = visit['timestamp'].replace(microsecond=0)
        
        if bucket_time not in buckets:
            buckets[bucket_time] = {
                'visits': 0,
                'successful': 0,
                'failed': 0
            }
        
        buckets[bucket_time]['visits'] += 1
        if visit['success']:
            buckets[bucket_time]['successful'] += 1
        else:
            buckets[bucket_time]['failed'] += 1
    
    # Convert to DataFrame
    data = []
    for timestamp, stats in sorted(buckets.items()):
        data.append({
            'timestamp': timestamp,
            'visits': stats['visits'],
            'successful': stats['successful'],
            'failed': stats['failed']
        })
    
    df = pd.DataFrame(data)
    return df.sort_values('timestamp')


def calculate_rolling_averages(history: List[Dict], windows: List[int] = [5, 10, 60], bot_running: bool = False) -> Dict[str, float]:
    """
    Calculate rolling averages for different time windows
    
    Args:
        history: List of visit records
        windows: List of window sizes in minutes
        bot_running: Whether the bot is currently running. If False, returns zeros.
        
    Returns:
        Dictionary with averages for each window
    """
    # If bot is not running, return zeros for all rolling averages
    if not bot_running:
        return {f'{w}min': 0.0 for w in windows}
    
    if not history:
        return {f'{w}min': 0.0 for w in windows}
    
    now = datetime.now()
    result = {}
    
    for window_minutes in windows:
        cutoff = now - timedelta(minutes=window_minutes)
        
        try:
            recent_visits = []
            for v in history:
                timestamp = datetime.fromisoformat(v.get('timestamp', ''))
                # Convert from UTC to local time
                if timestamp.tzinfo is None:
                    timestamp = utc_to_local(timestamp)
                elif timestamp.tzinfo is not None:
                    timestamp = timestamp.astimezone().replace(tzinfo=None)
                if timestamp >= cutoff:
                    recent_visits.append(v)
        except (ValueError, TypeError):
            recent_visits = []
        
        # If no recent visits in window, use all available data for that window
        if not recent_visits and history:
            recent_visits = history
        
        if recent_visits:
            try:
                oldest = datetime.fromisoformat(recent_visits[0]['timestamp'])
                newest = datetime.fromisoformat(recent_visits[-1]['timestamp'])
                # Convert from UTC to local time if needed
                if oldest.tzinfo is None:
                    oldest = utc_to_local(oldest)
                elif oldest.tzinfo is not None:
                    oldest = oldest.astimezone().replace(tzinfo=None)
                if newest.tzinfo is None:
                    newest = utc_to_local(newest)
                elif newest.tzinfo is not None:
                    newest = newest.astimezone().replace(tzinfo=None)
                time_span = max(1, (newest - oldest).total_seconds() / 60)
                result[f'{window_minutes}min'] = round(len(recent_visits) / time_span, 2)
            except (ValueError, TypeError, KeyError):
                result[f'{window_minutes}min'] = 0.0
        else:
            result[f'{window_minutes}min'] = 0.0
    
    return result


# Import shared URL utility function
from traffic_bot.utils.url_utils import looks_like_url_series as _looks_like_url_series


def extract_urls_from_excel(uploaded_file, config: Optional[Dict] = None) -> Tuple[List[str], Dict, str]:
    """
    Extract URLs from an uploaded Excel file
    
    Uses hybrid approach: checks config column names first (fast, predictable),
    then falls back to content-based detection (robust against blank headers).
    
    Args:
        uploaded_file: Streamlit uploaded file object or file path
        config: Optional configuration dictionary for column names
        
    Returns:
        Tuple of (list of URLs, metadata dict, detected column name)
    """
    if config is None:
        config = load_config() or {}
    
    product_url_column = config.get('product_url_column', 'Product URL')
    read_columns = config.get('read_columns', [
        "Product URL", "product_url", "Product Url",
        "URL", "url", "Link", "link"
    ])
    
    try:
        # Read Excel file - handle both file objects and file paths
        if hasattr(uploaded_file, 'read'):
            # Streamlit UploadedFile object - read from bytes
            df = pd.read_excel(uploaded_file, engine='openpyxl')
        else:
            # File path
            df = pd.read_excel(uploaded_file, engine='openpyxl')
        
        # Find URL column using hybrid approach: config first, then robust detection
        url_column = None
        
        # Step 1: Check exact match from config
        if product_url_column in df.columns:
            url_column = product_url_column
        else:
            # Step 2: Try case-insensitive match
            for col in df.columns:
                if col.strip().lower() == product_url_column.lower():
                    url_column = col
                    break
        
        # Step 3: Check from read_columns list
        if url_column is None:
            for possible_col in read_columns:
                if possible_col in df.columns:
                    url_column = possible_col
                    break
        
        # Step 4: Fallback to robust content-based detection
        if url_column is None:
            for col in df.columns:
                if len(df) > 0 and _looks_like_url_series(df[col], sample=25):
                    url_column = col
                    break
        
        if url_column is None:
            raise ValueError(
                f"Could not find any URL column.\n"
                f"Available columns: {df.columns.tolist()}\n"
                f"Please ensure your Excel file has a column containing URLs."
            )
        
        # Extract URLs
        urls = df[url_column].dropna().astype(str).tolist()
        
        # Filter valid URLs
        valid_urls = []
        invalid_count = 0
        
        for idx, url in enumerate(urls):
            url = url.strip()
            
            # Skip invalid entries
            if url.lower() in ['nan', 'none', '', 'null']:
                invalid_count += 1
                continue
            
            # Validate and normalize URL
            if url.startswith('http://') or url.startswith('https://'):
                valid_url = url
            elif url.startswith('www.') or url.startswith('//'):
                valid_url = 'https://' + url.lstrip('/')
            elif 'advancedenergy.com' in url.lower() or 'http' in url.lower():
                valid_url = 'https://' + url.lstrip('/') if not url.startswith('http') else url
            else:
                invalid_count += 1
                continue
            
            valid_urls.append(valid_url)
        
        # Prepare metadata
        metadata = {
            'total_rows': len(df),
            'total_urls_found': len(urls),
            'valid_urls': len(valid_urls),
            'invalid_urls': invalid_count,
            'columns': df.columns.tolist(),
            'detected_column': url_column
        }
        
        return valid_urls, metadata, url_column
        
    except Exception as e:
        raise Exception(f"Error reading Excel file: {str(e)}")


def save_uploaded_file(uploaded_file, save_path: str) -> bool:
    """
    Save uploaded file to disk
    
    Args:
        uploaded_file: Streamlit uploaded file object
        save_path: Path where to save the file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure save_path is in current directory (not relative paths that might fail)
        if not os.path.isabs(save_path):
            save_path = os.path.join(os.getcwd(), save_path)
        
        # Create directory if it doesn't exist
        save_dir = os.path.dirname(save_path)
        if save_dir and not os.path.exists(save_dir):
            os.makedirs(save_dir, exist_ok=True)
        
        # Save file
        with open(save_path, 'wb') as f:
            f.write(uploaded_file.getbuffer())
        
        # Verify file was saved
        if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            print(f"✅ File saved successfully: {save_path} ({os.path.getsize(save_path)} bytes)")
            return True
        else:
            print(f"❌ File save verification failed: {save_path}")
            return False
    except Exception as e:
        print(f"Error saving file: {e}")
        import traceback
        traceback.print_exc()
        return False


def save_config_updates(config_file: str, updates: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Update config.json with new values
    
    Args:
        config_file: Path to config.json
        updates: Dictionary of config updates (supports nested paths like 'parallel_mode.max_concurrent_proxies')
        
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        config = load_config(config_file)
        if config is None:
            return False, "Could not load existing config"
        
        # Apply updates (support nested paths)
        for key, value in updates.items():
            if '.' in key:
                # Handle nested keys like 'parallel_mode.max_concurrent_proxies'
                keys = key.split('.')
                current = config
                for k in keys[:-1]:
                    if k not in current:
                        current[k] = {}
                    current = current[k]
                current[keys[-1]] = value
            else:
                config[key] = value
        
        # Save config
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Clear config cache after updating
        load_config.clear()
        
        return True, None
    except Exception as e:
        return False, str(e)


def update_config_excel_file(config_file: str, excel_file: str) -> bool:
    """
    Update config.json to use a new Excel file
    
    Args:
        config_file: Path to config.json
        excel_file: Path to Excel file to use (can be relative or absolute)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        config = load_config(config_file)
        if config is None:
            return False
        
        # Convert to absolute path for reliability
        if not os.path.isabs(excel_file):
            # Try current directory first
            if os.path.exists(excel_file):
                excel_file = os.path.abspath(excel_file)
            else:
                # Try relative to config file directory
                config_dir = os.path.dirname(os.path.abspath(config_file))
                excel_file = os.path.join(config_dir, excel_file)
                excel_file = os.path.abspath(excel_file)
        
        # Normalize the path
        excel_file = os.path.normpath(excel_file)
        
        # Verify file exists before updating config
        if not os.path.exists(excel_file):
            print(f"⚠️ Warning: Excel file does not exist at: {excel_file}")
            print(f"   Current directory: {os.getcwd()}")
            print(f"   Files in current directory: {os.listdir('.')}")
            # Still update config, but log warning
        
        # Store as relative path from config file directory for portability
        config_dir = os.path.dirname(os.path.abspath(config_file))
        try:
            excel_rel = os.path.relpath(excel_file, config_dir)
            # Use relative path if it doesn't go outside the directory
            if not excel_rel.startswith('..'):
                config['excel_file'] = excel_rel
                print(f"✅ Updated config with relative path: {excel_rel}")
            else:
                config['excel_file'] = excel_file
                print(f"✅ Updated config with absolute path: {excel_file}")
        except ValueError:
            # On Windows or if relpath fails, use absolute
            config['excel_file'] = excel_file
            print(f"✅ Updated config with absolute path: {excel_file}")
        
        # Write config file
        config_path = os.path.abspath(config_file)
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"✅ Config file updated: {config_path}")
        print(f"   Excel file path: {config['excel_file']}")
        
        # Clear config cache after updating
        load_config.clear()
        
        return True
    except Exception as e:
        print(f"Error updating config: {e}")
        import traceback
        traceback.print_exc()
        return False

