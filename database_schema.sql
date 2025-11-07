-- ============================================================================
-- Traffic Automation - PostgreSQL Database Schema
-- ============================================================================
-- This schema stores all traffic data, replacing JSON file storage
-- Version: 1.0
-- Created: 2024

-- ============================================================================
-- Drop existing tables (for fresh install)
-- ============================================================================
DROP TABLE IF EXISTS visit_logs CASCADE;
DROP TABLE IF EXISTS daily_stats CASCADE;
DROP TABLE IF EXISTS sessions CASCADE;
DROP TABLE IF EXISTS url_stats CASCADE;
DROP TABLE IF EXISTS proxy_performance CASCADE;

-- ============================================================================
-- 1. SESSIONS TABLE
-- ============================================================================
-- Stores information about each bot execution session
CREATE TABLE sessions (
    session_id SERIAL PRIMARY KEY,
    start_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    total_requests INTEGER DEFAULT 0,
    successful_requests INTEGER DEFAULT 0,
    failed_requests INTEGER DEFAULT 0,
    blocked_requests INTEGER DEFAULT 0,
    unique_urls_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'running', -- running, completed, failed, cancelled
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for faster queries
CREATE INDEX idx_sessions_start_time ON sessions(start_time DESC);
CREATE INDEX idx_sessions_status ON sessions(status);

-- ============================================================================
-- 2. VISIT LOGS TABLE
-- ============================================================================
-- Stores individual visit records (replaces traffic_history.json)
CREATE TABLE visit_logs (
    visit_id BIGSERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES sessions(session_id) ON DELETE SET NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    url TEXT NOT NULL,
    success BOOLEAN NOT NULL,
    duration_seconds NUMERIC(10, 2),
    proxy VARCHAR(255),
    proxy_ip VARCHAR(45), -- IPv4 or IPv6
    status_code INTEGER,
    error_message TEXT,
    browser_type VARCHAR(50),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_visit_logs_timestamp ON visit_logs(timestamp DESC);
CREATE INDEX idx_visit_logs_url ON visit_logs(url);
CREATE INDEX idx_visit_logs_success ON visit_logs(success);
CREATE INDEX idx_visit_logs_session_id ON visit_logs(session_id);
CREATE INDEX idx_visit_logs_proxy_ip ON visit_logs(proxy_ip);

-- ============================================================================
-- 3. URL STATISTICS TABLE
-- ============================================================================
-- Aggregated statistics per URL
CREATE TABLE url_stats (
    url_id SERIAL PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    total_visits INTEGER DEFAULT 0,
    successful_visits INTEGER DEFAULT 0,
    failed_visits INTEGER DEFAULT 0,
    avg_duration_seconds NUMERIC(10, 2),
    min_duration_seconds NUMERIC(10, 2),
    max_duration_seconds NUMERIC(10, 2),
    last_visited TIMESTAMP,
    first_visited TIMESTAMP,
    success_rate NUMERIC(5, 2), -- Percentage
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for faster lookups
CREATE INDEX idx_url_stats_url ON url_stats(url);
CREATE INDEX idx_url_stats_total_visits ON url_stats(total_visits DESC);
CREATE INDEX idx_url_stats_success_rate ON url_stats(success_rate DESC);

-- ============================================================================
-- 4. DAILY STATISTICS TABLE
-- ============================================================================
-- Daily aggregated statistics (replaces daily_stats in traffic_stats.json)
CREATE TABLE daily_stats (
    stat_id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    total_visits INTEGER DEFAULT 0,
    successful_visits INTEGER DEFAULT 0,
    failed_visits INTEGER DEFAULT 0,
    unique_urls_count INTEGER DEFAULT 0,
    unique_proxies_count INTEGER DEFAULT 0,
    avg_duration_seconds NUMERIC(10, 2),
    success_rate NUMERIC(5, 2), -- Percentage
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for date-based queries
CREATE INDEX idx_daily_stats_date ON daily_stats(date DESC);

-- ============================================================================
-- 5. PROXY PERFORMANCE TABLE
-- ============================================================================
-- Track performance of each proxy over time
CREATE TABLE proxy_performance (
    proxy_id SERIAL PRIMARY KEY,
    proxy_address VARCHAR(255) NOT NULL,
    proxy_ip VARCHAR(45),
    total_requests INTEGER DEFAULT 0,
    successful_requests INTEGER DEFAULT 0,
    failed_requests INTEGER DEFAULT 0,
    consecutive_failures INTEGER DEFAULT 0,
    avg_response_time NUMERIC(10, 2),
    success_rate NUMERIC(5, 2), -- Percentage
    status VARCHAR(20) DEFAULT 'active', -- active, dead, testing
    last_used TIMESTAMP,
    last_success TIMESTAMP,
    last_failure TIMESTAMP,
    failure_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(proxy_address)
);

-- Indexes for proxy queries
CREATE INDEX idx_proxy_performance_proxy_address ON proxy_performance(proxy_address);
CREATE INDEX idx_proxy_performance_status ON proxy_performance(status);
CREATE INDEX idx_proxy_performance_success_rate ON proxy_performance(success_rate DESC);

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Real-time metrics (last 60 minutes)
CREATE OR REPLACE VIEW realtime_metrics AS
SELECT 
    COUNT(*) as total_visits,
    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful_visits,
    SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failed_visits,
    ROUND(AVG(duration_seconds), 2) as avg_duration,
    ROUND(
        (SUM(CASE WHEN success THEN 1 ELSE 0 END)::NUMERIC / NULLIF(COUNT(*), 0)) * 100, 
        2
    ) as success_rate,
    COUNT(DISTINCT url) as unique_urls,
    COUNT(DISTINCT proxy_ip) as unique_proxies
FROM visit_logs
WHERE timestamp >= NOW() - INTERVAL '60 minutes';

-- Recent visits (last 100)
CREATE OR REPLACE VIEW recent_visits AS
SELECT 
    visit_id,
    timestamp,
    url,
    success,
    duration_seconds,
    proxy_ip,
    status_code,
    error_message
FROM visit_logs
ORDER BY timestamp DESC
LIMIT 100;

-- Top performing URLs
CREATE OR REPLACE VIEW top_urls AS
SELECT 
    url,
    total_visits,
    successful_visits,
    failed_visits,
    success_rate,
    avg_duration_seconds,
    last_visited
FROM url_stats
WHERE total_visits > 0
ORDER BY total_visits DESC
LIMIT 50;

-- Active proxies performance
CREATE OR REPLACE VIEW active_proxies AS
SELECT 
    proxy_address,
    proxy_ip,
    total_requests,
    successful_requests,
    failed_requests,
    success_rate,
    avg_response_time,
    last_used,
    status
FROM proxy_performance
WHERE status = 'active'
ORDER BY success_rate DESC, total_requests DESC;

-- ============================================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
CREATE TRIGGER update_sessions_updated_at 
    BEFORE UPDATE ON sessions 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_url_stats_updated_at 
    BEFORE UPDATE ON url_stats 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_daily_stats_updated_at 
    BEFORE UPDATE ON daily_stats 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_proxy_performance_updated_at 
    BEFORE UPDATE ON proxy_performance 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Function to calculate success rate
CREATE OR REPLACE FUNCTION calculate_success_rate(successful INTEGER, total INTEGER)
RETURNS NUMERIC AS $$
BEGIN
    IF total = 0 THEN
        RETURN 0;
    END IF;
    RETURN ROUND((successful::NUMERIC / total::NUMERIC) * 100, 2);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to update URL statistics (called after each visit)
CREATE OR REPLACE FUNCTION update_url_stats()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO url_stats (
        url, 
        total_visits, 
        successful_visits, 
        failed_visits,
        avg_duration_seconds,
        min_duration_seconds,
        max_duration_seconds,
        last_visited,
        first_visited,
        success_rate
    )
    VALUES (
        NEW.url,
        1,
        CASE WHEN NEW.success THEN 1 ELSE 0 END,
        CASE WHEN NOT NEW.success THEN 1 ELSE 0 END,
        NEW.duration_seconds,
        NEW.duration_seconds,
        NEW.duration_seconds,
        NEW.timestamp,
        NEW.timestamp,
        CASE WHEN NEW.success THEN 100 ELSE 0 END
    )
    ON CONFLICT (url) DO UPDATE SET
        total_visits = url_stats.total_visits + 1,
        successful_visits = url_stats.successful_visits + CASE WHEN NEW.success THEN 1 ELSE 0 END,
        failed_visits = url_stats.failed_visits + CASE WHEN NOT NEW.success THEN 1 ELSE 0 END,
        avg_duration_seconds = (
            (url_stats.avg_duration_seconds * url_stats.total_visits + COALESCE(NEW.duration_seconds, 0)) / 
            (url_stats.total_visits + 1)
        ),
        min_duration_seconds = LEAST(url_stats.min_duration_seconds, NEW.duration_seconds),
        max_duration_seconds = GREATEST(url_stats.max_duration_seconds, NEW.duration_seconds),
        last_visited = NEW.timestamp,
        success_rate = calculate_success_rate(
            url_stats.successful_visits + CASE WHEN NEW.success THEN 1 ELSE 0 END,
            url_stats.total_visits + 1
        );
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update URL stats
CREATE TRIGGER trigger_update_url_stats
    AFTER INSERT ON visit_logs
    FOR EACH ROW
    EXECUTE FUNCTION update_url_stats();

-- ============================================================================
-- INDEXES FOR ANALYTICS QUERIES
-- ============================================================================

-- Composite indexes for common query patterns
CREATE INDEX idx_visit_logs_timestamp_success ON visit_logs(timestamp DESC, success);
CREATE INDEX idx_visit_logs_url_timestamp ON visit_logs(url, timestamp DESC);
CREATE INDEX idx_visit_logs_proxy_timestamp ON visit_logs(proxy_ip, timestamp DESC);

-- ============================================================================
-- DATA RETENTION POLICY
-- ============================================================================

-- Function to clean old visit logs (keep last 90 days)
CREATE OR REPLACE FUNCTION cleanup_old_visit_logs()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM visit_logs
    WHERE timestamp < NOW() - INTERVAL '90 days';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- You can schedule this with pg_cron or external cron job:
-- SELECT cleanup_old_visit_logs();

-- ============================================================================
-- SAMPLE QUERIES (FOR REFERENCE)
-- ============================================================================

-- Get real-time metrics (last 60 minutes)
-- SELECT * FROM realtime_metrics;

-- Get recent visits
-- SELECT * FROM recent_visits;

-- Get daily statistics for last 30 days
-- SELECT * FROM daily_stats WHERE date >= CURRENT_DATE - INTERVAL '30 days' ORDER BY date DESC;

-- Get top performing URLs
-- SELECT * FROM top_urls;

-- Get proxy performance
-- SELECT * FROM active_proxies;

-- Get visits by hour (last 24 hours)
-- SELECT 
--     DATE_TRUNC('hour', timestamp) as hour,
--     COUNT(*) as visits,
--     SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful
-- FROM visit_logs
-- WHERE timestamp >= NOW() - INTERVAL '24 hours'
-- GROUP BY hour
-- ORDER BY hour DESC;

-- ============================================================================
-- GRANT PERMISSIONS (adjust username as needed)
-- ============================================================================

-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_username;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_username;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO your_username;

-- ============================================================================
-- COMPLETION MESSAGE
-- ============================================================================

DO $$ 
BEGIN 
    RAISE NOTICE 'Database schema created successfully!';
    RAISE NOTICE 'Tables: sessions, visit_logs, url_stats, daily_stats, proxy_performance';
    RAISE NOTICE 'Views: realtime_metrics, recent_visits, top_urls, active_proxies';
    RAISE NOTICE 'Functions: Auto-update triggers, cleanup functions';
END $$;

