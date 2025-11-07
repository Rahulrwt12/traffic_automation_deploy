"""
Database Manager for Traffic Bot
Handles PostgreSQL connections, queries, and data persistence
"""
import logging
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from contextlib import contextmanager
from sqlalchemy import create_engine, text, func, Integer
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from .models import Base, Session, VisitLog, URLStats, DailyStats, ProxyPerformance

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages PostgreSQL database connections and operations"""
    
    # Class-level flag to track if initial connection has been logged
    _first_connection_logged = False
    
    def __init__(self, config: dict):
        """
        Initialize database manager
        
        Args:
            config: Configuration dictionary with database settings
        """
        self.config = config
        self.engine = None
        self.Session = None
        self._session = None
        
        # Database configuration (loaded from environment or config)
        db_config = config.get('database', {})
        self.enabled = db_config.get('enabled', False)
        
        if self.enabled:
            # Only log detailed info on first connection
            if not DatabaseManager._first_connection_logged:
                logger.info("📊 Database storage: ENABLED")
            self._init_connection()
        else:
            # Only log disabled message once
            if not DatabaseManager._first_connection_logged:
                logger.info("============================================================================")
                logger.info("📊 Database storage: DISABLED")
                logger.info("   Using JSON file storage for data persistence")
                logger.info("   To enable database: Set 'database.enabled' to true in config.json")
                logger.info("============================================================================")
                logger.info("")
                DatabaseManager._first_connection_logged = True
    
    def _init_connection(self):
        """Initialize database connection"""
        try:
            # Get database URL from environment or config
            database_url = os.getenv('DATABASE_URL') or self.config.get('database', {}).get('url')
            
            # Extract connection info for logging (without password)
            host = None
            port = None
            database = None
            user = None
            
            if not database_url:
                if not DatabaseManager._first_connection_logged:
                    logger.warning("Database enabled but DATABASE_URL not set. Using default configuration.")
                # Build URL from individual components
                host = os.getenv('DB_HOST', 'localhost')
                port = os.getenv('DB_PORT', '5432')
                user = os.getenv('DB_USER', 'traffic_bot')
                password = os.getenv('DB_PASSWORD', '')
                database = os.getenv('DB_NAME', 'traffic_automation')
                
                database_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
            else:
                # Parse database URL for logging (mask password)
                import re
                url_pattern = r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)'
                match = re.match(url_pattern, database_url)
                if match:
                    user, _, host, port, database = match.groups()
            
            # Only log detailed connection info on first connection
            if not DatabaseManager._first_connection_logged:
                logger.info("============================================================================")
                logger.info("🔌 Initializing Database Connection")
                logger.info("============================================================================")
                logger.info(f"   Database Type: PostgreSQL")
                logger.info(f"   Host: {host or 'from DATABASE_URL'}")
                logger.info(f"   Port: {port or 'from DATABASE_URL'}")
                logger.info(f"   Database: {database or 'from DATABASE_URL'}")
                logger.info(f"   User: {user or 'from DATABASE_URL'}")
                logger.info(f"   Pool Size: 10 connections")
                logger.info(f"   Max Overflow: 20 connections")
                logger.info("----------------------------------------------------------------------------")
            
            # Create engine with connection pooling
            self.engine = create_engine(
                database_url,
                poolclass=QueuePool,
                pool_size=10,  # Number of connections to maintain
                max_overflow=20,  # Additional connections when pool is full
                pool_pre_ping=True,  # Verify connections before using
                pool_recycle=3600,  # Recycle connections after 1 hour
                echo=False  # Set to True for SQL logging (debugging)
            )
            
            # Create session factory
            session_factory = sessionmaker(bind=self.engine)
            self.Session = scoped_session(session_factory)
            
            # Test connection (only log on first connection)
            if not DatabaseManager._first_connection_logged:
                logger.info("   Testing database connectivity...")
            try:
                with self.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
            except Exception as conn_error:
                logger.error(f"Database connection test failed: {conn_error}")
                raise
            
            # Only log success details on first connection
            if not DatabaseManager._first_connection_logged:
                logger.info("✅ Database connection established successfully!")
                logger.info("   Connection pool ready with 10 base connections")
                logger.info("============================================================================")
                logger.info("")
                DatabaseManager._first_connection_logged = True
            
        except Exception as e:
            logger.error("============================================================================")
            logger.error(f"❌ Failed to initialize database connection")
            logger.error(f"   Error: {e}")
            logger.error("   Falling back to JSON file storage")
            logger.error("============================================================================")
            logger.error("")
            self.enabled = False
            DatabaseManager._first_connection_logged = True  # Mark as logged even on failure
            raise
    
    def create_tables(self):
        """Create all database tables if they don't exist"""
        if not self.enabled:
            return False
        
        # Only log table creation once (first time only)
        try:
            # Check if this is the first time we're creating tables
            first_time = not hasattr(DatabaseManager, '_tables_created')
            
            if first_time:
                logger.info("🔧 Creating/verifying database tables...")
            
            Base.metadata.create_all(self.engine)
            
            if first_time:
                logger.info("✅ Database tables created/verified successfully")
                logger.info("   Tables: sessions, visit_logs, url_stats, daily_stats, proxy_performance")
                logger.info("")
                DatabaseManager._tables_created = True
            
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create database tables: {e}")
            logger.error("")
            return False
    
    @contextmanager
    def get_session(self):
        """Context manager for database sessions"""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================
    
    def create_session(self, start_time: Optional[datetime] = None) -> Optional[int]:
        """Create a new bot execution session"""
        if not self.enabled:
            return None
        
        try:
            with self.get_session() as session:
                new_session = Session(
                    start_time=start_time or datetime.utcnow(),
                    status='running'
                )
                session.add(new_session)
                session.flush()
                return new_session.session_id
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return None
    
    def update_session(self, session_id: int, **kwargs):
        """Update session with new data"""
        if not self.enabled or not session_id:
            return
        
        try:
            with self.get_session() as session:
                db_session = session.query(Session).filter_by(session_id=session_id).first()
                if db_session:
                    for key, value in kwargs.items():
                        if hasattr(db_session, key):
                            setattr(db_session, key, value)
        except Exception as e:
            logger.error(f"Failed to update session: {e}")
    
    def end_session(self, session_id: int, status: str = 'completed'):
        """Mark session as completed"""
        if not self.enabled or not session_id:
            return
        
        try:
            self.update_session(
                session_id,
                end_time=datetime.utcnow(),
                status=status
            )
        except Exception as e:
            logger.error(f"Failed to end session: {e}")
    
    def get_current_active_session(self) -> Optional[int]:
        """Get the current active/running session ID"""
        if not self.enabled:
            return None
        
        try:
            with self.get_session() as session:
                active_session = session.query(Session).filter_by(
                    status='running'
                ).order_by(Session.start_time.desc()).first()
                
                if active_session:
                    return active_session.session_id
                return None
        except Exception as e:
            logger.error(f"Failed to get current active session: {e}")
            return None
    
    # =========================================================================
    # VISIT LOGGING
    # =========================================================================
    
    def log_visit(self, url: str, success: bool, duration: float, 
                   proxy: Optional[str] = None, session_id: Optional[int] = None,
                   status_code: Optional[int] = None, error_message: Optional[str] = None) -> bool:
        """
        Log a visit to the database
        
        Args:
            url: URL visited
            success: Whether visit was successful
            duration: Duration in seconds
            proxy: Proxy used (full URL)
            session_id: Session ID
            status_code: HTTP status code
            error_message: Error message if failed
        
        Returns:
            True if logged successfully
        """
        if not self.enabled:
            return False
        
        try:
            # Extract proxy IP from full proxy URL
            proxy_ip = None
            if proxy:
                # Extract IP from proxy URL (e.g., http://user:pass@1.2.3.4:8080)
                import re
                ip_match = re.search(r'@?([\d\.]+):', proxy)
                if ip_match:
                    proxy_ip = ip_match.group(1)
            
            with self.get_session() as session:
                visit_log = VisitLog(
                    session_id=session_id,
                    timestamp=datetime.utcnow(),
                    url=url,
                    success=success,
                    duration_seconds=round(duration, 2) if duration else None,
                    proxy=proxy[:255] if proxy else None,  # Truncate if too long
                    proxy_ip=proxy_ip,
                    status_code=status_code,
                    error_message=error_message
                )
                session.add(visit_log)
            
            return True
        except Exception as e:
            logger.error(f"Failed to log visit: {e}")
            return False
    
    # =========================================================================
    # STATISTICS & ANALYTICS
    # =========================================================================
    
    def get_realtime_metrics(self, minutes: int = 60) -> Dict[str, Any]:
        """Get real-time metrics for last N minutes"""
        if not self.enabled:
            return {}
        
        try:
            with self.get_session() as session:
                cutoff = datetime.utcnow() - timedelta(minutes=minutes)
                
                result = session.query(
                    func.count(VisitLog.visit_id).label('total_visits'),
                    func.sum(func.cast(VisitLog.success, Integer)).label('successful'),
                    func.avg(VisitLog.duration_seconds).label('avg_duration'),
                    func.count(func.distinct(VisitLog.url)).label('unique_urls'),
                    func.count(func.distinct(VisitLog.proxy_ip)).label('unique_proxies')
                ).filter(
                    VisitLog.timestamp >= cutoff
                ).first()
                
                total = result.total_visits or 0
                successful = result.successful or 0
                
                return {
                    'total_visits': total,
                    'successful_visits': successful,
                    'failed_visits': total - successful,
                    'success_rate': round((successful / total * 100) if total > 0 else 0, 2),
                    'avg_duration': round(float(result.avg_duration or 0), 2),
                    'unique_urls': result.unique_urls or 0,
                    'unique_proxies': result.unique_proxies or 0
                }
        except Exception as e:
            logger.error(f"Failed to get realtime metrics: {e}")
            return {}
    
    def get_recent_visits(self, limit: int = 100, session_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get recent visits, optionally filtered by session_id"""
        if not self.enabled:
            return []
        
        try:
            with self.get_session() as session:
                query = session.query(VisitLog)
                
                # Filter by session_id if provided
                if session_id is not None:
                    query = query.filter(VisitLog.session_id == session_id)
                
                visits = query.order_by(
                    VisitLog.timestamp.desc()
                ).limit(limit).all()
                
                return [{
                    'timestamp': v.timestamp.isoformat(),
                    'url': v.url,
                    'success': v.success,
                    'duration_seconds': float(v.duration_seconds) if v.duration_seconds else 0,
                    'proxy': v.proxy,
                    'status_code': v.status_code
                } for v in visits]
        except Exception as e:
            logger.error(f"Failed to get recent visits: {e}")
            return []
    
    def get_url_statistics(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get URL performance statistics"""
        if not self.enabled:
            return []
        
        try:
            with self.get_session() as session:
                stats = session.query(URLStats).order_by(
                    URLStats.total_visits.desc()
                ).limit(limit).all()
                
                return [{
                    'url': s.url,
                    'total_visits': s.total_visits,
                    'successful_visits': s.successful_visits,
                    'failed_visits': s.failed_visits,
                    'success_rate': float(s.success_rate) if s.success_rate else 0,
                    'avg_duration': float(s.avg_duration_seconds) if s.avg_duration_seconds else 0,
                    'last_visited': s.last_visited.isoformat() if s.last_visited else None
                } for s in stats]
        except Exception as e:
            logger.error(f"Failed to get URL statistics: {e}")
            return []
    
    def get_daily_stats(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily statistics for last N days"""
        if not self.enabled:
            return []
        
        try:
            with self.get_session() as session:
                cutoff = date.today() - timedelta(days=days)
                
                stats = session.query(DailyStats).filter(
                    DailyStats.date >= cutoff
                ).order_by(DailyStats.date.desc()).all()
                
                return [{
                    'date': s.date.isoformat(),
                    'total_visits': s.total_visits,
                    'successful_visits': s.successful_visits,
                    'failed_visits': s.failed_visits,
                    'success_rate': float(s.success_rate) if s.success_rate else 0,
                    'avg_duration': float(s.avg_duration_seconds) if s.avg_duration_seconds else 0,
                    'unique_urls': s.unique_urls_count
                } for s in stats]
        except Exception as e:
            logger.error(f"Failed to get daily stats: {e}")
            return []
    
    # =========================================================================
    # PROXY MANAGEMENT
    # =========================================================================
    
    def update_proxy_stats(self, proxy_address: str, success: bool, 
                           response_time: Optional[float] = None):
        """Update proxy performance statistics"""
        if not self.enabled:
            return
        
        try:
            with self.get_session() as session:
                proxy = session.query(ProxyPerformance).filter_by(
                    proxy_address=proxy_address
                ).first()
                
                if not proxy:
                    # Create new proxy record
                    proxy = ProxyPerformance(proxy_address=proxy_address)
                    session.add(proxy)
                    session.flush()
                
                # Update stats
                proxy.total_requests += 1
                proxy.last_used = datetime.utcnow()
                
                if success:
                    proxy.successful_requests += 1
                    proxy.consecutive_failures = 0
                    proxy.last_success = datetime.utcnow()
                else:
                    proxy.failed_requests += 1
                    proxy.consecutive_failures += 1
                    proxy.last_failure = datetime.utcnow()
                
                # Update success rate
                if proxy.total_requests > 0:
                    proxy.success_rate = round(
                        (proxy.successful_requests / proxy.total_requests) * 100, 2
                    )
                
                # Update response time (rolling average)
                if response_time is not None and success:
                    if proxy.avg_response_time:
                        # Calculate rolling average
                        proxy.avg_response_time = round(
                            (proxy.avg_response_time * 0.9 + response_time * 0.1), 2
                        )
                    else:
                        proxy.avg_response_time = round(response_time, 2)
                
                # Mark as dead if too many consecutive failures
                if proxy.consecutive_failures >= 3:
                    proxy.status = 'dead'
        
        except Exception as e:
            logger.error(f"Failed to update proxy stats: {e}")
    
    def get_proxy_performance(self) -> List[Dict[str, Any]]:
        """Get proxy performance report"""
        if not self.enabled:
            return []
        
        try:
            with self.get_session() as session:
                proxies = session.query(ProxyPerformance).order_by(
                    ProxyPerformance.success_rate.desc()
                ).all()
                
                return [{
                    'proxy_address': p.proxy_address,
                    'total_requests': p.total_requests,
                    'successful_requests': p.successful_requests,
                    'failed_requests': p.failed_requests,
                    'success_rate': float(p.success_rate) if p.success_rate else 0,
                    'avg_response_time': float(p.avg_response_time) if p.avg_response_time else 0,
                    'status': p.status,
                    'last_used': p.last_used.isoformat() if p.last_used else None
                } for p in proxies]
        except Exception as e:
            logger.error(f"Failed to get proxy performance: {e}")
            return []
    
    # =========================================================================
    # CLEANUP & MAINTENANCE
    # =========================================================================
    
    def cleanup_old_data(self, days: int = 90) -> int:
        """Remove visit logs older than N days"""
        if not self.enabled:
            return 0
        
        try:
            with self.get_session() as session:
                cutoff = datetime.utcnow() - timedelta(days=days)
                
                deleted = session.query(VisitLog).filter(
                    VisitLog.timestamp < cutoff
                ).delete()
                
                logger.info(f"Cleaned up {deleted} old visit logs")
                return deleted
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return 0
    
    def close(self):
        """Close database connections"""
        if self.Session:
            self.Session.remove()
        if self.engine:
            self.engine.dispose()
        logger.info("Database connections closed")

