"""
Log Viewer Component for Streamlit
Handles reading and displaying log files
"""
import os
from typing import List
import streamlit as st


@st.cache_data(ttl=0.1, show_spinner=False)  # Cache for 0.1 seconds for near real-time updates
def read_log_file(log_file: str = 'traffic_bot.log', lines: int = 500, _file_mtime: float = 0.0) -> List[str]:
    """
    Read last N lines from log file with minimal caching for real-time viewing.
    
    Uses file modification time as a cache key parameter to automatically invalidate
    cache when the log file changes. This ensures logs are always up-to-date.
    
    Args:
        log_file: Path to log file
        lines: Number of lines to read
        _file_mtime: File modification time (used as cache key, don't pass manually)
    """
    if not os.path.exists(log_file):
        return ["Log file not found. Start the bot to generate logs."]
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
            selected_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            # Ensure all lines are strings and strip trailing newlines
            result = [line.rstrip('\n\r') if isinstance(line, str) else str(line).rstrip('\n\r') for line in selected_lines]
            return result
    except (IOError, PermissionError) as e:
        return [f"Error reading log file: {e}"]


def read_log_file_realtime(log_file: str = 'traffic_bot.log', lines: int = 500) -> List[str]:
    """
    Read log file with automatic cache invalidation based on file modification time.
    
    This wrapper function gets the file modification time and passes it to the cached
    function, ensuring the cache is invalidated whenever the file changes.
    """
    if not os.path.exists(log_file):
        return ["Log file not found. Start the bot to generate logs."]
    
    try:
        # Get file modification time - this will be used as cache key
        # When file changes, mtime changes, cache invalidates automatically
        file_mtime = os.path.getmtime(log_file)
        return read_log_file(log_file, lines, _file_mtime=file_mtime)
    except (IOError, PermissionError):
        # If we can't get mtime, fall back to reading without cache key
        return read_log_file(log_file, lines, _file_mtime=0.0)


def filter_logs(logs: List[str], filter_type: str = "all") -> List[str]:
    """Filter logs by type and remove invalid entries"""
    filtered = []
    for line in logs:
        # Ensure line is a string - convert if necessary
        if not isinstance(line, str):
            line = str(line)
        
        # Skip lines that contain [object Object] or are just commas/spaces
        if "[object Object]" in line or line.strip() in [",", ", [object Object],", ""]:
            continue
        
        # Skip empty lines after stripping
        if not line.strip():
            continue
        
        # Apply type filter
        if filter_type == "all":
            filtered.append(line)
        else:
            line_lower = line.lower()
            if filter_type == "error" and ("error" in line_lower or "exception" in line_lower):
                filtered.append(line)
            elif filter_type == "warning" and "warning" in line_lower:
                filtered.append(line)
            elif filter_type == "info" and "info" in line_lower:
                filtered.append(line)
            elif filter_type == "success" and ("success" in line_lower or "✓" in line or "✅" in line):
                filtered.append(line)
    
    return filtered


def get_log_stats(logs: List[str]) -> dict:
    """Get statistics about logs"""
    total_lines = len(logs)
    error_count = sum(1 for line in logs if "error" in line.lower() or "exception" in line.lower())
    warning_count = sum(1 for line in logs if "warning" in line.lower())
    info_count = sum(1 for line in logs if "info" in line.lower())
    
    return {
        'total_lines': total_lines,
        'errors': error_count,
        'warnings': warning_count,
        'info': info_count
    }

