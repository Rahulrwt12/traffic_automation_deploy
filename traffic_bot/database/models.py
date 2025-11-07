"""
Database Models for Traffic Bot
SQLAlchemy ORM models matching the PostgreSQL schema
"""
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Numeric, Text,
    ForeignKey, UniqueConstraint, Index, Date
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class Session(Base):
    """Bot execution session"""
    __tablename__ = 'sessions'
    
    session_id = Column(Integer, primary_key=True, autoincrement=True)
    start_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_time = Column(DateTime)
    total_requests = Column(Integer, default=0)
    successful_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)
    blocked_requests = Column(Integer, default=0)
    unique_urls_count = Column(Integer, default=0)
    status = Column(String(20), default='running')  # running, completed, failed, cancelled
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    visit_logs = relationship("VisitLog", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Session(id={self.session_id}, start={self.start_time}, status={self.status})>"


class VisitLog(Base):
    """Individual visit record"""
    __tablename__ = 'visit_logs'
    
    visit_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('sessions.session_id', ondelete='SET NULL'))
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    url = Column(Text, nullable=False, index=True)
    success = Column(Boolean, nullable=False, index=True)
    duration_seconds = Column(Numeric(10, 2))
    proxy = Column(String(255))
    proxy_ip = Column(String(45), index=True)  # IPv4 or IPv6
    status_code = Column(Integer)
    error_message = Column(Text)
    browser_type = Column(String(50))
    user_agent = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session = relationship("Session", back_populates="visit_logs")
    
    # Indexes
    __table_args__ = (
        Index('idx_visit_logs_timestamp_success', 'timestamp', 'success'),
        Index('idx_visit_logs_url_timestamp', 'url', 'timestamp'),
        Index('idx_visit_logs_proxy_timestamp', 'proxy_ip', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<VisitLog(id={self.visit_id}, url={self.url[:50]}, success={self.success})>"


class URLStats(Base):
    """Aggregated statistics per URL"""
    __tablename__ = 'url_stats'
    
    url_id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(Text, nullable=False, unique=True, index=True)
    total_visits = Column(Integer, default=0, index=True)
    successful_visits = Column(Integer, default=0)
    failed_visits = Column(Integer, default=0)
    avg_duration_seconds = Column(Numeric(10, 2))
    min_duration_seconds = Column(Numeric(10, 2))
    max_duration_seconds = Column(Numeric(10, 2))
    last_visited = Column(DateTime)
    first_visited = Column(DateTime)
    success_rate = Column(Numeric(5, 2), index=True)  # Percentage
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<URLStats(url={self.url[:50]}, visits={self.total_visits}, rate={self.success_rate}%)>"


class DailyStats(Base):
    """Daily aggregated statistics"""
    __tablename__ = 'daily_stats'
    
    stat_id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    total_visits = Column(Integer, default=0)
    successful_visits = Column(Integer, default=0)
    failed_visits = Column(Integer, default=0)
    unique_urls_count = Column(Integer, default=0)
    unique_proxies_count = Column(Integer, default=0)
    avg_duration_seconds = Column(Numeric(10, 2))
    success_rate = Column(Numeric(5, 2))  # Percentage
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<DailyStats(date={self.date}, visits={self.total_visits}, rate={self.success_rate}%)>"


class ProxyPerformance(Base):
    """Track performance of each proxy"""
    __tablename__ = 'proxy_performance'
    
    proxy_id = Column(Integer, primary_key=True, autoincrement=True)
    proxy_address = Column(String(255), nullable=False, unique=True, index=True)
    proxy_ip = Column(String(45))
    total_requests = Column(Integer, default=0)
    successful_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)
    consecutive_failures = Column(Integer, default=0)
    avg_response_time = Column(Numeric(10, 2))
    success_rate = Column(Numeric(5, 2), index=True)  # Percentage
    status = Column(String(20), default='active', index=True)  # active, dead, testing
    last_used = Column(DateTime)
    last_success = Column(DateTime)
    last_failure = Column(DateTime)
    failure_reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<ProxyPerformance(proxy={self.proxy_address}, rate={self.success_rate}%, status={self.status})>"

