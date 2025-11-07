"""
Traffic Automation Tool - Streamlit Dashboard
Live dashboard with metrics, charts, bot control, and integrated log viewer
"""
# Load environment variables from .env file first (before any other imports)
import os
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.getcwd(), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not installed

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import logging
from datetime import datetime, timedelta

# Set up logging
logger = logging.getLogger(__name__)

# Import utilities
from utils.streamlit_helpers import (
    load_traffic_stats, load_traffic_history, load_config,
    get_daily_stats_dataframe, get_recent_visits_dataframe,
    get_url_statistics, calculate_metrics, format_number, format_duration,
    get_realtime_metrics, get_minute_by_minute_data, get_second_by_second_data,
    calculate_rolling_averages, extract_urls_from_excel, save_uploaded_file,
    update_config_excel_file, save_config_updates
)
from utils.bot_controller import BotController
from utils.log_viewer import read_log_file_realtime, filter_logs, get_log_stats

# Page configuration
st.set_page_config(
    page_title="Traffic Automation Dashboard",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .status-running {
        color: #00cc00;
        font-weight: bold;
    }
    .status-stopped {
        color: #cc0000;
        font-weight: bold;
    }
    .log-viewer {
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
    }
    .realtime-indicator {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #00cc00;
        animation: pulse 2s infinite;
        margin-right: 5px;
    }
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }
    .kpi-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 0.75rem;
        color: white;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .kpi-value {
        font-size: 2rem;
        font-weight: bold;
        margin: 0.5rem 0;
    }
    .kpi-label {
        font-size: 0.9rem;
        opacity: 0.9;
    }
    .log-viewer-code {
        max-height: 400px;
        overflow-y: auto;
        overflow-x: hidden;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
        background-color: #ffffff;
        color: #262730;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 2px solid #d0d0d0;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
        word-wrap: break-word;
        overflow-wrap: break-word;
        white-space: pre-wrap;
        word-break: break-all;
        position: relative;
        box-sizing: border-box;
    }
    .log-viewer-code:hover {
        border-color: #b0b0b0;
        box-shadow: 0 3px 8px rgba(0, 0, 0, 0.2);
    }
    .log-viewer-code pre {
        margin: 0 !important;
        padding: 0 !important;
        background: transparent !important;
        border: none !important;
        overflow: visible !important;
        max-width: 100% !important;
    }
    .log-viewer-code code {
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
        white-space: pre-wrap !important;
        word-break: break-all !important;
        display: block !important;
        width: 100% !important;
        max-width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
        background: transparent !important;
        border: none !important;
        box-sizing: border-box !important;
    }
    .log-viewer-code::-webkit-scrollbar {
        width: 8px;
    }
    .log-viewer-code::-webkit-scrollbar-track {
        background: #f5f5f5;
        border-radius: 4px;
    }
    .log-viewer-code::-webkit-scrollbar-thumb {
        background: #ccc;
        border-radius: 4px;
    }
    .log-viewer-code::-webkit-scrollbar-thumb:hover {
        background: #aaa;
    }
    /* Completely eliminate flicker - instant updates with no visible transitions */
    .log-viewer-code {
        opacity: 1 !important;
        transition: none !important;
        will-change: auto !important;
    }
    /* Prevent layout shift during updates */
    .element-container {
        transition: none !important;
    }
    /* Smooth updates for metrics and stats */
    [data-testid="stMetricValue"] {
        transition: opacity 0.15s ease-in-out;
    }
    /* Reduce flicker on selectboxes and widgets */
    .stSelectbox > div > div {
        transition: background-color 0.1s ease-in-out;
    }
    /* Preserve scroll position indicator */
    .log-viewer-code:focus-within {
        scroll-behavior: smooth;
    }
    /* Prevent visible re-rendering of log container */
    .log-viewer-wrapper {
        position: relative;
        min-height: 400px;
        contain: layout style paint;
    }
    /* No animations - instant updates */
    .log-viewer-code pre {
        transition: none !important;
        animation: none !important;
    }
    /* Hide fragment updates completely */
    [data-testid="stFragment"] {
        opacity: 1 !important;
    }
    /* Ensure content updates are instant and invisible */
    .log-viewer-code code {
        transition: none !important;
        animation: none !important;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if 'bot_controller' not in st.session_state:
    st.session_state.bot_controller = BotController()

if 'previous_metrics' not in st.session_state:
    st.session_state.previous_metrics = {}

if 'uploaded_urls' not in st.session_state:
    st.session_state.uploaded_urls = []

if 'uploaded_file_metadata' not in st.session_state:
    st.session_state.uploaded_file_metadata = None

if 'uploaded_file_name' not in st.session_state:
    st.session_state.uploaded_file_name = None

if 'log_lines_selected' not in st.session_state:
    st.session_state.log_lines_selected = 20  # Default to 20 lines

# Bot controller instance
bot_controller = st.session_state.bot_controller


def main():
    """Main dashboard function"""
    
    # Header with refresh button
    header_col1, header_col2 = st.columns([4, 1])
    with header_col1:
        st.markdown('<div class="main-header">🚦 Traffic Automation Dashboard</div>', unsafe_allow_html=True)
    with header_col2:
        st.markdown("<br>", unsafe_allow_html=True)  # Spacing
        if st.button("🔄 Refresh Dashboard", key="refresh_dashboard_btn", use_container_width=True, type="secondary"):
            # Clear all caches for fresh data
            load_traffic_stats.clear()
            load_traffic_history.clear()
            load_config.clear()
            get_realtime_metrics.clear()
            # Also clear session state metrics to force recalculation
            if 'previous_metrics' in st.session_state:
                st.session_state.previous_metrics = {}
            st.rerun()
    
    # Sidebar for controls - NEW REDESIGNED STRUCTURE
    with st.sidebar:
        # Load config for sidebar
        config = load_config()
        status = bot_controller.get_status()
        
        # ========================================================================
        # 1. QUICK STATS (TOP)
        # ========================================================================
        stats = load_traffic_stats()
        if stats:
            st.subheader("📊 Quick Stats")
            stats_col1, stats_col2 = st.columns(2)
            with stats_col1:
                st.metric("Total Visits", format_number(stats.get('total_visits', 0)))
            with stats_col2:
                st.metric("Total Sessions", stats.get('total_sessions', 0))
        
        st.divider()
        
        # ========================================================================
        # CONTROL PANEL HEADER
        # ========================================================================
        st.header("⚙️ Control Panel")
        
        st.divider()
        
        # ========================================================================
        # 2. EXCEL FILE UPLOAD
        # ========================================================================
        st.subheader("📁 Excel File Upload")
        st.info("ℹ️ **Required:** Upload an Excel file with URLs before starting the bot. The bot will only work with uploaded files.")
        
        uploaded_file = st.file_uploader(
            "Upload Excel file with URLs",
            type=['xlsx', 'xls'],
            help="Upload an Excel file containing URLs. The system will automatically detect the URL column. This file is required to start the bot.",
            key="excel_uploader"
        )
        
        if uploaded_file is not None:
            # Check if this is a new file upload or if we need to re-extract
            file_key = f"{uploaded_file.name}_{uploaded_file.size}"
            if (st.session_state.uploaded_file_name != file_key or 
                not st.session_state.uploaded_urls):
                try:
                    # Reset file pointer to beginning
                    uploaded_file.seek(0)
                    
                    # Extract URLs from uploaded file
                    with st.spinner("Analyzing Excel file and extracting URLs..."):
                        urls, metadata, detected_column = extract_urls_from_excel(uploaded_file, config)
                        
                        # Store in session state
                        st.session_state.uploaded_urls = urls
                        st.session_state.uploaded_file_metadata = metadata
                        st.session_state.uploaded_file_name = file_key
                        
                        st.success(f"✅ Successfully extracted {len(urls)} URLs from '{detected_column}' column!")
                        
                except Exception as e:
                    st.error(f"❌ Error processing Excel file: {str(e)}")
                    st.session_state.uploaded_urls = []
                    st.session_state.uploaded_file_metadata = None
                    st.session_state.uploaded_file_name = None
            
            # Show preview if URLs were extracted
            if st.session_state.uploaded_urls:
                metadata = st.session_state.uploaded_file_metadata
                
                # Show metadata
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Rows", metadata['total_rows'])
                with col2:
                    st.metric("Valid URLs", metadata['valid_urls'])
                with col3:
                    st.metric("Invalid URLs", metadata['invalid_urls'])
                
                st.caption(f"📊 Detected column: **{metadata['detected_column']}**")
                
                # Show preview of URLs
                with st.expander(f"📋 Preview URLs ({min(10, len(st.session_state.uploaded_urls))} of {len(st.session_state.uploaded_urls)})"):
                    for i, url in enumerate(st.session_state.uploaded_urls[:10], 1):
                        st.write(f"{i}. {url}")
                    if len(st.session_state.uploaded_urls) > 10:
                        st.caption(f"... and {len(st.session_state.uploaded_urls) - 10} more URLs")
                
                # Save and apply button
                if st.button("💾 Save & Apply Excel File", use_container_width=True, type="primary", key="save_excel_btn"):
                    if not status['is_running']:
                        try:
                            # Reset file pointer before saving
                            uploaded_file.seek(0)
                            
                            # Save uploaded file
                            save_path = f"uploaded_{uploaded_file.name}"
                            if save_uploaded_file(uploaded_file, save_path):
                                # Update config
                                if update_config_excel_file('config.json', save_path):
                                    st.success(f"✅ Excel file saved and configured! The bot will use this file when started.")
                                    st.info(f"📝 File saved as: `{save_path}`")
                                    # Clear session state to force reload
                                    st.session_state.uploaded_file_name = None
                                    # Clear config cache to reload new config
                                    load_config.clear()
                                    # Button automatically triggers rerun
                                else:
                                    st.error("❌ Failed to update configuration file.")
                            else:
                                st.error("❌ Failed to save uploaded file.")
                        except Exception as e:
                            st.error(f"❌ Error saving file: {str(e)}")
                    else:
                        st.warning("⚠️ Please stop the bot before changing the Excel file.")
        
        # Show current file if configured
        if config and config.get('excel_file') and not uploaded_file:
            excel_file_path = config.get('excel_file', '')
            if excel_file_path and os.path.exists(excel_file_path):
                st.success(f"✅ Excel file configured: **{excel_file_path}**")
                st.caption("You can now start the bot.")
            elif excel_file_path:
                st.warning(f"⚠️ Configured file not found: **{excel_file_path}**")
                st.caption("Please upload a new Excel file.")
            else:
                st.info("ℹ️ No Excel file configured. Please upload an Excel file to start the bot.")
        
        st.divider()
        
        # ========================================================================
        # 3. CONFIGURATION PANEL
        # ========================================================================
        st.subheader("⚙️ Configuration")
        
        if not config:
            st.warning("⚠️ Configuration not loaded. Please check config.json")
        else:
            # Calculate batch info based on proxy count from config
            # Get max_proxies from config (defaults to 100)
            proxy_api_config = config.get('proxy_api', {})
            TOTAL_PROXIES = proxy_api_config.get('max_proxies', 100)
            
            def calculate_batches(selected_proxy_count: int) -> int:
                """Calculate number of batches: Total proxies / selected_proxy_count"""
                if selected_proxy_count <= 0:
                    return 1
                # Use ceiling division to ensure all proxies are used
                return (TOTAL_PROXIES + selected_proxy_count - 1) // selected_proxy_count
            
            # Proxy Count Selection
            proxy_options = [10, 25, 50, 100]
            current_proxy_count = config.get('parallel_mode', {}).get('max_concurrent_proxies', 25)
            current_proxies_per_batch = config.get('parallel_mode', {}).get('automated_batches', {}).get('proxies_per_batch', 25)
            
            # Use proxies_per_batch if it's in the options, otherwise use max_concurrent_proxies
            if current_proxies_per_batch in proxy_options:
                current_proxy_count = current_proxies_per_batch
            else:
                current_proxy_count = max(proxy_options) if current_proxy_count > max(proxy_options) else current_proxy_count
                current_proxy_count = min(proxy_options) if current_proxy_count < min(proxy_options) else current_proxy_count
            
            # Find closest option
            closest_proxy = min(proxy_options, key=lambda x: abs(x - current_proxy_count))
            proxy_index = proxy_options.index(closest_proxy) if closest_proxy in proxy_options else 0
            
            selected_proxy_count = st.selectbox(
                "Number of Proxies Per Batch",
                proxy_options,
                index=proxy_index,
                help=f"Select number of proxies per batch (total pool: {TOTAL_PROXIES} proxies)",
                disabled=status['is_running'],
                key="proxy_count_select"
            )
            
            # Calculate batches: TOTAL_PROXIES / selected_proxy_count
            num_batches = calculate_batches(selected_proxy_count)
            
            # Display batch calculation
            if num_batches == 1:
                st.info(f"📦 **1 batch** will be created using all {TOTAL_PROXIES} proxies")
            else:
                st.info(f"📦 **{num_batches} batches** will be created ({TOTAL_PROXIES} proxies ÷ {selected_proxy_count} per batch)")
            
            # Mode Selection
            mode_options = {
                'batch': 'Batch Mode',
                'parallel': 'Parallel Mode',
                'parallel_batches': 'Parallel Batches'
            }
            
            current_mode = config.get('mode', 'batch')
            mode_keys = list(mode_options.keys())
            current_mode_index = mode_keys.index(current_mode) if current_mode in mode_keys else 0
            
            selected_mode = st.selectbox(
                "Run Mode",
                mode_keys,
                format_func=lambda x: mode_options[x],
                index=current_mode_index,
                help="Select the mode in which to run the bot",
                disabled=status['is_running'],
                key="mode_select"
            )
            
            # Advanced settings expander
            with st.expander("⚙️ Advanced Settings"):
                # Delay between URLs
                delay_between_urls = config.get('batch_mode', {}).get('delay_between_urls_seconds', 7)
                new_delay = st.number_input(
                    "Delay Between URLs (seconds)",
                    min_value=1.0,
                    max_value=3600.0,
                    value=float(delay_between_urls),
                    step=0.5,
                    help="Delay between visiting each URL",
                    disabled=status['is_running'],
                    key="delay_between_urls"
                )
                
                # Delay between batches
                delay_between_batches = config.get('parallel_mode', {}).get('automated_batches', {}).get('delay_between_batches_minutes', 45)
                new_batch_delay = st.number_input(
                    "Delay Between Batches (minutes)",
                    min_value=0.0,
                    max_value=1440.0,
                    value=float(delay_between_batches),
                    step=1.0,
                    help="Delay between batches in automated batch mode",
                    disabled=status['is_running'],
                    key="delay_between_batches"
                )
                
                # Browser type
                browser_type = config.get('browser', {}).get('browser_type', 'chromium')
                browser_options = ['chromium', 'firefox', 'webkit']
                browser_index = browser_options.index(browser_type) if browser_type in browser_options else 0
                
                new_browser_type = st.selectbox(
                    "Browser Type",
                    browser_options,
                    index=browser_index,
                    help="Browser engine to use",
                    disabled=status['is_running'],
                    key="browser_type_select"
                )
                
                # Headless mode
                headless = config.get('browser', {}).get('headless', False)
                new_headless = st.checkbox(
                    "Headless Mode",
                    value=headless,
                    help="Run browser in headless mode (no GUI)",
                    disabled=status['is_running'],
                    key="headless_checkbox"
                )
            
            # Auto-save configuration when values change (only if bot is not running)
            if not status['is_running']:
                # Track previous values in session state
                if 'last_config_values' not in st.session_state:
                    st.session_state.last_config_values = {
                        'proxy_count': selected_proxy_count,
                        'mode': selected_mode,
                        'delay': new_delay,
                        'batch_delay': new_batch_delay,
                        'browser_type': new_browser_type,
                        'headless': new_headless
                    }
                
                # Check if any values changed
                config_changed = (
                    selected_proxy_count != st.session_state.last_config_values.get('proxy_count') or
                    selected_mode != st.session_state.last_config_values.get('mode') or
                    new_delay != st.session_state.last_config_values.get('delay') or
                    new_batch_delay != st.session_state.last_config_values.get('batch_delay') or
                    new_browser_type != st.session_state.last_config_values.get('browser_type') or
                    new_headless != st.session_state.last_config_values.get('headless')
                )
                
                if config_changed:
                    updates = {}
                    
                    # Update proxy count - set both max_concurrent_proxies and proxies_per_batch
                    if selected_proxy_count != st.session_state.last_config_values.get('proxy_count'):
                        updates['parallel_mode.max_concurrent_proxies'] = selected_proxy_count
                        updates['parallel_mode.automated_batches.proxies_per_batch'] = selected_proxy_count
                    
                    # Update mode
                    if selected_mode != st.session_state.last_config_values.get('mode'):
                        updates['mode'] = selected_mode
                    
                    # Update delays
                    if new_delay != st.session_state.last_config_values.get('delay'):
                        updates['batch_mode.delay_between_urls_seconds'] = new_delay
                    
                    if new_batch_delay != st.session_state.last_config_values.get('batch_delay'):
                        updates['parallel_mode.automated_batches.delay_between_batches_minutes'] = new_batch_delay
                    
                    # Update browser settings
                    if new_browser_type != st.session_state.last_config_values.get('browser_type'):
                        updates['browser.browser_type'] = new_browser_type
                    
                    if new_headless != st.session_state.last_config_values.get('headless'):
                        updates['browser.headless'] = new_headless
                    
                    # Auto-save updates
                    if updates:
                        success, error = save_config_updates('config.json', updates)
                        if success:
                            # Update session state to reflect saved values
                            st.session_state.last_config_values = {
                                'proxy_count': selected_proxy_count,
                                'mode': selected_mode,
                                'delay': new_delay,
                                'batch_delay': new_batch_delay,
                                'browser_type': new_browser_type,
                                'headless': new_headless
                            }
                            # Clear config cache to reload new config
                            load_config.clear()
                            # Show success message without blocking
                            st.success("✅ Configuration auto-saved!")
                            # Rerun to apply changes immediately
                            st.rerun()
                        else:
                            st.error(f"❌ Failed to save configuration: {error}")
            else:
                st.caption("⏸️ Stop the bot to modify configuration")
        
        st.divider()
        
        # ========================================================================
        # 4. BOT CONTROLS
        # ========================================================================
        st.subheader("🎮 Bot Controls")
        
        # Bot status
        if status['is_running']:
            st.success("🟢 Bot Running")
        elif status['error']:
            st.error(f"❌ Error: {status['error']}")
        else:
            st.info("⚪ Bot Stopped")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Check if Excel file is configured before allowing bot start
            excel_file_configured = config and config.get('excel_file') and os.path.exists(config.get('excel_file', ''))
            start_disabled = status['is_running'] or not excel_file_configured
            
            start_clicked = st.button(
                "▶️ Start Bot", 
                use_container_width=True, 
                disabled=start_disabled, 
                key="start_bot_btn",
                help="Upload an Excel file and click 'Save & Apply Excel File' first" if not excel_file_configured else None
            )
            if start_clicked:
                if bot_controller.start_bot():
                    st.success("✅ Bot started successfully!")
                else:
                    st.error("❌ Failed to start bot")
                # Single rerun after state change
                st.rerun()
            elif not excel_file_configured and not status['is_running']:
                st.caption("⚠️ Please upload an Excel file first")
        
        with col2:
            stop_clicked = st.button("⏹️ Stop Bot", use_container_width=True, disabled=not status['is_running'], key="stop_bot_btn")
            if stop_clicked:
                if bot_controller.stop_bot():
                    st.success("✅ Bot stopped successfully!")
                else:
                    st.error("❌ Failed to stop bot")
                # Single rerun after state change
                st.rerun()
    
    # Main content area
    # Get current active session ID if bot is running
    current_session_id = None
    if status['is_running']:
        try:
            config = load_config()
            if config and config.get('database', {}).get('enabled', False):
                from traffic_bot.database.db_manager import DatabaseManager
                db = DatabaseManager(config)
                if db.enabled:
                    current_session_id = db.get_current_active_session()
                    # Session filtering happens silently in the background
        except Exception as e:
            logger.error(f"Failed to get current session: {e}")
    
    # Load data with caching for performance
    # If bot is running, filter by current session; otherwise show all data
    stats = load_traffic_stats()
    history = load_traffic_history(session_id=current_session_id)
    config = load_config()
    
    # Calculate metrics
    metrics = calculate_metrics(stats, history)
    
    # Calculate real-time metrics (only show data if bot is running)
    realtime_metrics = get_realtime_metrics(history, window_minutes=60, bot_running=status['is_running'])
    rolling_avgs = calculate_rolling_averages(history, windows=[5, 10, 60], bot_running=status['is_running'])
    
    # Store previous metrics for delta calculations
    if st.session_state.previous_metrics:
        prev_metrics = st.session_state.previous_metrics
    else:
        prev_metrics = metrics.copy()
    
    # ========================================================================
    # TAB-BASED DASHBOARD STRUCTURE
    # ========================================================================
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["⚡ Live", "📊 Historic", "🔍 Advanced Analytics"])
    
    # ========================================================================
    # TAB 1: LIVE - Real-time metrics, Real-time Analytics, Live log viewer
    # ========================================================================
    with tab1:
        # Pre-fetch data once for the entire Live tab (avoid duplicate fetching)
        minute_data = get_minute_by_minute_data(history, minutes=30)
        second_data = get_second_by_second_data(history, seconds=300)
        
        # Real-time KPI Cards with Sparklines
        st.markdown("### ⚡ Real-Time Metrics")
        rt_col1, rt_col2, rt_col3, rt_col4, rt_col5 = st.columns(5)
        
        with rt_col1:
            visits_per_min = realtime_metrics['visits_per_minute']
            prev_vpm = st.session_state.previous_metrics.get('visits_per_minute', visits_per_min)
            delta_vpm = visits_per_min - prev_vpm
            delta_color = "normal" if delta_vpm >= 0 else "inverse"
            
            # Create mini sparkline for visits per minute (using pre-fetched data)
            sparkline_fig = None
            if not minute_data.empty:
                sparkline_fig = go.Figure()
                sparkline_fig.add_trace(go.Scatter(
                    x=minute_data['timestamp'],
                    y=minute_data['visits'],
                    mode='lines',
                    line=dict(color='#00cc00', width=2),
                    fill='tozeroy',
                    fillcolor='rgba(0, 200, 0, 0.1)',
                    showlegend=False,
                    hovertemplate='%{y} visits<extra></extra>'
                ))
                sparkline_fig.update_layout(
                    height=60,
                    margin=dict(l=0, r=0, t=0, b=0),
                    xaxis=dict(showgrid=False, showticklabels=False),
                    yaxis=dict(showgrid=False, showticklabels=False),
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)'
                )
            
            st.metric(
                "Visits/Min",
                f"{visits_per_min:.1f}",
                delta=f"{delta_vpm:+.1f}" if delta_vpm != 0 else None,
                delta_color=delta_color
            )
            if sparkline_fig:
                st.plotly_chart(sparkline_fig, use_container_width=True, config={'displayModeBar': False})
        
        with rt_col2:
            success_rate = realtime_metrics['recent_success_rate']
            prev_sr = st.session_state.previous_metrics.get('recent_success_rate', success_rate)
            delta_sr = success_rate - prev_sr
            
            # Color code based on success rate
            if success_rate >= 95:
                color = "#00cc00"
            elif success_rate >= 80:
                color = "#ffaa00"
            else:
                color = "#cc0000"
            
            st.markdown(f"""
            <div style="background-color: {color}; padding: 1rem; border-radius: 0.5rem; color: white;">
                <div style="font-size: 0.85rem; opacity: 0.9;">Success Rate</div>
                <div style="font-size: 1.8rem; font-weight: bold;">{success_rate:.1f}%</div>
                <div style="font-size: 0.75rem; opacity: 0.8;">{delta_sr:+.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
        
        with rt_col3:
            avg_response = realtime_metrics['avg_response_time']
            prev_rt = st.session_state.previous_metrics.get('avg_response_time', avg_response)
            delta_rt = avg_response - prev_rt
            
            st.metric(
                "Avg Response",
                f"{avg_response:.2f}s",
                delta=f"{delta_rt:+.2f}s" if delta_rt != 0 else None,
                delta_color="inverse" if delta_rt > 0 else "normal"
            )
        
        with rt_col4:
            recent_visits = realtime_metrics['recent_visits_count']
            st.metric(
                "Recent Visits",
                format_number(recent_visits),
                delta=f"{realtime_metrics['recent_successful']} success"
            )
        
        with rt_col5:
            # Rolling averages display
            st.markdown("**Rolling Averages**")
            st.write(f"5min: {rolling_avgs['5min']:.1f}/min")
            st.write(f"10min: {rolling_avgs['10min']:.1f}/min")
            st.write(f"60min: {rolling_avgs['60min']:.1f}/min")
        
        st.divider()
        
        # ========================================================================
        # REAL-TIME CHARTS SECTION
        # ========================================================================
        st.markdown("### 📈 Real-Time Analytics")
        
        # Display charts only if bot is running and we have history data
        if status['is_running'] and history and len(history) > 0:
            rt_chart_col1, rt_chart_col2 = st.columns(2)
            
            with rt_chart_col1:
                # Real-time visits per minute chart
                if not minute_data.empty:
                    fig = go.Figure()
                
                    # Add visits line
                    fig.add_trace(go.Scatter(
                        x=minute_data['timestamp'],
                        y=minute_data['visits'],
                        mode='lines+markers',
                        name='Visits',
                        line=dict(color='#1f77b4', width=2),
                        fill='tozeroy',
                        fillcolor='rgba(31, 119, 180, 0.1)'
                    ))
                    
                    # Add successful visits
                    fig.add_trace(go.Scatter(
                        x=minute_data['timestamp'],
                        y=minute_data['successful'],
                        mode='lines',
                        name='Successful',
                        line=dict(color='#00cc00', width=2, dash='dash')
                    ))
                    
                    # Add failed visits
                    fig.add_trace(go.Scatter(
                        x=minute_data['timestamp'],
                        y=minute_data['failed'],
                        mode='lines',
                        name='Failed',
                        line=dict(color='#cc0000', width=2, dash='dash')
                    ))
                    
                    fig.update_layout(
                        title='🔄 Real-Time Visits (Last 30 Minutes)',
                        xaxis_title='Time',
                        yaxis_title='Visits',
                        height=350,
                        hovermode='x unified',
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Response time trend chart
                if not minute_data.empty and 'avg_duration' in minute_data.columns:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=minute_data['timestamp'],
                        y=minute_data['avg_duration'],
                        mode='lines+markers',
                        name='Avg Response Time',
                        line=dict(color='#ff7f0e', width=2),
                        fill='tozeroy',
                        fillcolor='rgba(255, 127, 14, 0.1)'
                    ))
                    
                    fig.update_layout(
                        title='⏱️ Response Time Trend (Last 30 Minutes)',
                        xaxis_title='Time',
                        yaxis_title='Seconds',
                        height=300,
                        hovermode='x unified'
                    )
                    st.plotly_chart(fig, use_container_width=True)
            
            with rt_chart_col2:
                # Success vs Failure rate stream
                if not minute_data.empty:
                    minute_data['success_rate'] = (minute_data['successful'] / minute_data['visits'] * 100).fillna(0)
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=minute_data['timestamp'],
                        y=minute_data['success_rate'],
                        mode='lines+markers',
                        name='Success Rate %',
                        line=dict(color='#00cc00', width=3),
                        fill='tozeroy',
                        fillcolor='rgba(0, 200, 0, 0.2)'
                    ))
                    
                    # Add 95% threshold line
                    fig.add_hline(y=95, line_dash="dash", line_color="orange", 
                                 annotation_text="95% Target", annotation_position="right")
                    
                    fig.update_layout(
                        title='✅ Success Rate Stream (Last 30 Minutes)',
                        xaxis_title='Time',
                        yaxis_title='Success Rate (%)',
                        yaxis_range=[0, 100],
                        height=350,
                        hovermode='x unified'
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Real-time activity heatmap (visits per second for last 5 minutes)
                if not second_data.empty:
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=second_data['timestamp'],
                        y=second_data['visits'],
                        marker_color='#667eea',
                        name='Visits/sec'
                    ))
                    
                    fig.update_layout(
                        title='⚡ Activity Heatmap (Last 5 Minutes)',
                        xaxis_title='Time',
                        yaxis_title='Visits per Second',
                        height=300,
                        hovermode='x unified',
                        xaxis=dict(showgrid=True),
                        yaxis=dict(showgrid=True)
                    )
                    st.plotly_chart(fig, use_container_width=True)
        else:
            # Show message when bot is not running or no data
            if not status['is_running']:
                st.info("⏸️ **Bot is not running.** Start the bot to see real-time analytics charts.")
            else:
                st.info("📊 No traffic data yet. The bot is running but no visits have been recorded yet.")
        
        st.divider()
        
        # ========================================================================
        # LIVE LOG VIEWER (Manual refresh for stability and user control)
        # ========================================================================
        st.markdown("### 📋 Live Log Viewer")
        
        # Controls row with manual refresh button
        log_col1, log_col2, log_col3 = st.columns([2, 1, 1])
        
        with log_col1:
            log_filter = st.selectbox(
                "Filter Logs",
                ["all", "error", "warning", "info", "success"],
                label_visibility="collapsed",
                key="log_filter"
            )
        
        with log_col2:
            # Get current selection from session state or default to 20
            line_options = [10, 20, 30, 40, 50, 100]
            current_selection = st.session_state.log_lines_selected
            # Find index of current selection, default to 1 (20) if not found
            try:
                default_index = line_options.index(current_selection)
            except ValueError:
                default_index = 1  # Default to 20
            
            log_lines = st.selectbox(
                "Lines",
                line_options,
                index=default_index,
                label_visibility="collapsed",
                key="log_lines"
            )
            
            # Save selection to session state to persist across reruns
            st.session_state.log_lines_selected = log_lines
        
        with log_col3:
            # Manual refresh button - gives user control
            if st.button("🔄 Refresh Logs", key="refresh_logs_btn", use_container_width=True):
                # Clear any cached log data to force reload
                if 'last_log_content' in st.session_state:
                    del st.session_state.last_log_content
                st.rerun()
        
        # Read and display logs (simple, no complex caching)
        logs = read_log_file_realtime('traffic_bot.log', lines=st.session_state.log_lines_selected)
        filtered_logs = filter_logs(logs, st.session_state.get('log_filter', 'all'))
        
        # Get log stats
        log_stats = get_log_stats(logs)
        
        # Display log stats
        st.caption(f"📊 Total: {log_stats['total_lines']} lines | "
                   f"❌ Errors: {log_stats['errors']} | "
                   f"⚠️ Warnings: {log_stats['warnings']} | "
                   f"ℹ️ Info: {log_stats['info']}")
        
        # Display logs in a clean code block
        if filtered_logs:
            log_text = '\n'.join(str(line) for line in filtered_logs)
        else:
            log_text = "No logs available. Start the bot to generate logs."
        
        # Simple display with st.code for better performance and no flicker
        st.code(log_text, language="log", line_numbers=False)
    
    # ========================================================================
    # TAB 2: HISTORIC - Key metrics, Historical analytics, Recent visits
    # ========================================================================
    with tab2:
        # Top metrics row
        st.markdown("### 📊 Key Metrics")
    
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            # Daily visits chart
            if stats and history:
                daily_df = get_daily_stats_dataframe(stats, days=30)
                if not daily_df.empty:
                    fig = px.line(
                        daily_df,
                        x='date',
                        y='visits',
                        title='Visits Over Time (Last 30 Days)',
                        labels={'date': 'Date', 'visits': 'Number of Visits'}
                    )
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)
            
                # Success vs Failure pie chart
                if metrics['total_successful'] > 0 or metrics['total_failed'] > 0:
                    fig = go.Figure(data=[go.Pie(
                        labels=['Successful', 'Failed'],
                        values=[metrics['total_successful'], metrics['total_failed']],
                        hole=0.4,
                        marker_colors=['#00cc00', '#cc0000']
                    )])
                    fig.update_layout(
                        title="Success vs Failure Rate",
                        height=300
                    )
                    st.plotly_chart(fig, use_container_width=True)
            else:
                if not stats and not history:
                    st.warning("⚠️ **No historic data available yet.**")
                    st.info("""
                    **To see historic data and analytics:**
                    1. Upload an Excel file with URLs
                    2. Click 'Save & Apply Excel File'
                    3. Start the bot
                    4. Wait for the bot to complete at least one visit
                    5. Data will appear here automatically
                    
                    **Note:** Data is stored in PostgreSQL database (if enabled) or JSON files as fallback.
                    In Docker containers, database data persists across restarts if using external PostgreSQL.
                    """)
                elif not stats:
                    st.info("No statistics available yet. The bot needs to complete at least one session.")
                elif not history:
                    st.info("No visit history available yet. Start the bot to begin tracking visits.")
        
        with chart_col2:
            # Recent activity timeline
            if history:
                recent_df = get_recent_visits_dataframe(history, limit=100)
                if not recent_df.empty:
                    recent_df['hour'] = recent_df['timestamp'].dt.hour
                    hourly_counts = recent_df.groupby('hour').size().reset_index(name='count')
                    
                    fig = px.bar(
                        hourly_counts,
                        x='hour',
                        y='count',
                        title='Recent Activity by Hour',
                        labels={'hour': 'Hour of Day', 'count': 'Visits'}
                    )
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Top URLs bar chart
                    url_stats = get_url_statistics(history)
                    if not url_stats.empty and len(url_stats) > 0:
                        top_urls = url_stats.head(10).copy()
                        top_urls['url_short'] = top_urls['url'].apply(
                            lambda x: x[:50] + '...' if len(x) > 50 else x
                        )
                        
                        fig = px.bar(
                            top_urls,
                            x='total_visits',
                            y='url_short',
                            orientation='h',
                            title='Top 10 URLs by Visits',
                            labels={'total_visits': 'Total Visits', 'url_short': 'URL'}
                        )
                        fig.update_layout(height=300, yaxis={'categoryorder': 'total ascending'})
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No history data available.")
        
        st.divider()
        
        # Recent visits table
        if history:
            st.markdown("### 🕒 Recent Visits")
            recent_df = get_recent_visits_dataframe(history, limit=50)
            if not recent_df.empty:
                # Format for display
                display_df = recent_df.copy()
                display_df['timestamp'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                display_df['success'] = display_df['success'].apply(lambda x: '✅' if x else '❌')
                display_df['duration'] = display_df['duration_seconds'].apply(format_duration)
                display_df['url'] = display_df['url'].apply(lambda x: x[:60] + '...' if len(x) > 60 else x)
                
                display_df = display_df[['timestamp', 'success', 'url', 'duration']]
                display_df.columns = ['Timestamp', 'Status', 'URL', 'Duration']
                
                st.dataframe(display_df, use_container_width=True, hide_index=True)
            else:
                st.info("No recent visits to display.")
        
        st.divider()
        
        # Bot progress section
        bot_status = bot_controller.get_status()
        if bot_status['is_running']:
            st.markdown("### 🎯 Bot Progress")
            progress = bot_controller.get_progress()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**Current URL:** {progress['current_url_index']} / {progress['total_urls']}")
            with col2:
                st.progress(progress['progress_percent'] / 100)
            with col3:
                st.write(f"**Progress:** {progress['progress_percent']:.1f}%")
    
    # ========================================================================
    # TAB 3: ADVANCED ANALYTICS - URL performance, Proxy stats, Deep dive
    # ========================================================================
    with tab3:
        # URL Performance Analytics
        st.markdown("#### 📍 URL Performance")
        
        if history:
            url_stats = get_url_statistics(history)
            if not url_stats.empty and len(url_stats) > 0:
                # URL Performance Metrics
                url_col1, url_col2, url_col3 = st.columns(3)
                
                with url_col1:
                    st.metric("Total URLs", format_number(len(url_stats)))
                
                with url_col2:
                    avg_success_rate = (url_stats['successful'] / url_stats['total_visits'] * 100).mean()
                    st.metric("Avg Success Rate", f"{avg_success_rate:.1f}%")
                
                with url_col3:
                    avg_response = url_stats['avg_duration'].mean()
                    st.metric("Avg Response Time", f"{avg_response:.2f}s")
                
                st.divider()
                
                # Top Performing URLs
                url_chart_col1, url_chart_col2 = st.columns(2)
                
                with url_chart_col1:
                    # Top 10 URLs by visits
                    top_urls = url_stats.head(10).copy()
                    top_urls['url_short'] = top_urls['url'].apply(
                        lambda x: x[:50] + '...' if len(x) > 50 else x
                    )
                    
                    fig = px.bar(
                        top_urls,
                        x='total_visits',
                        y='url_short',
                        orientation='h',
                        title='Top 10 URLs by Total Visits',
                        labels={'total_visits': 'Total Visits', 'url_short': 'URL'},
                        color='total_visits',
                        color_continuous_scale='Blues'
                    )
                    fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
                    st.plotly_chart(fig, use_container_width=True)
                
                with url_chart_col2:
                    # URLs by Success Rate
                    url_stats_sorted = url_stats.copy()
                    url_stats_sorted['success_rate'] = (url_stats_sorted['successful'] / url_stats_sorted['total_visits'] * 100)
                    url_stats_sorted = url_stats_sorted.sort_values('success_rate', ascending=False).head(10)
                    url_stats_sorted['url_short'] = url_stats_sorted['url'].apply(
                        lambda x: x[:50] + '...' if len(x) > 50 else x
                    )
                    
                    fig = px.bar(
                        url_stats_sorted,
                        x='success_rate',
                        y='url_short',
                        orientation='h',
                        title='Top 10 URLs by Success Rate',
                        labels={'success_rate': 'Success Rate (%)', 'url_short': 'URL'},
                        color='success_rate',
                        color_continuous_scale='Greens'
                    )
                    fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
                    st.plotly_chart(fig, use_container_width=True)
                
                st.divider()
                
                # URL Performance Table
                st.markdown("#### 📊 URL Performance Details")
                display_url_stats = url_stats.copy()
                display_url_stats['success_rate'] = (display_url_stats['successful'] / display_url_stats['total_visits'] * 100).round(2)
                display_url_stats['url_short'] = display_url_stats['url'].apply(
                    lambda x: x[:70] + '...' if len(x) > 70 else x
                )
                display_url_stats = display_url_stats[['url_short', 'total_visits', 'successful', 'failed', 'success_rate', 'avg_duration']]
                display_url_stats.columns = ['URL', 'Total Visits', 'Successful', 'Failed', 'Success Rate %', 'Avg Duration (s)']
                display_url_stats = display_url_stats.sort_values('Total Visits', ascending=False)
                
                st.dataframe(display_url_stats, use_container_width=True, hide_index=True)
            else:
                st.warning("⚠️ **No URL statistics available yet.**")
                st.info("""
                **To see URL performance analytics:**
                1. Upload an Excel file with URLs
                2. Start the bot and let it complete visits
                3. URL statistics will be calculated automatically
                4. Data appears here after the bot visits URLs
                """)
        else:
            st.warning("⚠️ **No history data available for analytics.**")
            st.info("""
            **To see advanced analytics:**
            1. Upload an Excel file with URLs
            2. Click 'Save & Apply Excel File'
            3. Start the bot
            4. Wait for visits to complete
            5. Analytics will appear here automatically
            
            **Note:** Analytics are generated from visit history. 
            Make sure the bot has completed at least one visit.
            """)
        
        st.divider()
        
        # Performance Analysis
        st.markdown("#### ⚡ Performance Analysis")
        
        if history:
            perf_col1, perf_col2 = st.columns(2)
            
            with perf_col1:
                # Response time distribution
                recent_df = get_recent_visits_dataframe(history, limit=1000)
                if not recent_df.empty and 'duration_seconds' in recent_df.columns:
                    durations = recent_df['duration_seconds'].dropna()
                    if len(durations) > 0:
                        fig = go.Figure()
                        fig.add_trace(go.Histogram(
                            x=durations,
                            nbinsx=30,
                            name='Response Time Distribution',
                            marker_color='#667eea'
                        ))
                        fig.update_layout(
                            title='Response Time Distribution',
                            xaxis_title='Response Time (seconds)',
                            yaxis_title='Frequency',
                            height=350
                        )
                        st.plotly_chart(fig, use_container_width=True)
            
            with perf_col2:
                # Success/Failure over time
                if not recent_df.empty:
                    recent_df['date'] = recent_df['timestamp'].dt.date
                    daily_perf = recent_df.groupby('date').agg({
                        'success': ['sum', 'count']
                    }).reset_index()
                    daily_perf.columns = ['date', 'successful', 'total']
                    daily_perf['failed'] = daily_perf['total'] - daily_perf['successful']
                    daily_perf['success_rate'] = (daily_perf['successful'] / daily_perf['total'] * 100).round(2)
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=daily_perf['date'],
                        y=daily_perf['success_rate'],
                        mode='lines+markers',
                        name='Success Rate %',
                        line=dict(color='#00cc00', width=2),
                        fill='tozeroy',
                        fillcolor='rgba(0, 200, 0, 0.1)'
                    ))
                    fig.add_hline(y=95, line_dash="dash", line_color="orange", 
                                 annotation_text="95% Target", annotation_position="right")
                    fig.update_layout(
                        title='Daily Success Rate Trend',
                        xaxis_title='Date',
                        yaxis_title='Success Rate (%)',
                        yaxis_range=[0, 100],
                        height=350
                    )
                    st.plotly_chart(fig, use_container_width=True)
    
    # ========================================================================
    # METRICS TRACKING FOR DELTA CALCULATIONS
    # ========================================================================
    
    # Update previous metrics for delta calculations on next manual refresh
    current_metrics = {
        'visits_per_minute': realtime_metrics['visits_per_minute'],
        'recent_success_rate': realtime_metrics['recent_success_rate'],
        'avg_response_time': realtime_metrics['avg_response_time']
    }
    
    # Store current metrics for next comparison
    st.session_state.previous_metrics = current_metrics.copy()
        


if __name__ == "__main__":
    main()

