"""Pydantic models for configuration schema validation"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Literal
from enum import Enum


class BrowserType(str, Enum):
    """Valid browser types"""
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


class ProxyApiType(str, Enum):
    """Valid proxy API types"""
    WEBSHARE = "webshare"
    SMARTPROXY = "smartproxy"
    BRIGHTDATA = "brightdata"
    OXYLABS = "oxylabs"


class ScrollPattern(str, Enum):
    """Valid scroll patterns"""
    PROGRESSIVE = "progressive"
    RANDOM = "random"
    LINEAR = "linear"


class ProxyRotationStrategy(str, Enum):
    """Valid proxy rotation strategies"""
    SMART = "smart"
    ROUND_ROBIN = "round-robin"
    RANDOM = "random"
    LEAST_USED = "least-used"


class WaitUntil(str, Enum):
    """Valid wait until options"""
    LOAD = "load"
    DOMCONTENTLOADED = "domcontentloaded"
    NETWORKIDLE = "networkidle"
    COMMIT = "commit"


class SpeedMode(str, Enum):
    """Valid speed modes"""
    FAST = "fast"
    NORMAL = "normal"
    SLOW = "slow"


class BrowserAuthenticationConfig(BaseModel):
    """Browser authentication configuration"""
    enabled: bool = False
    username: str = ""
    password: str = ""
    domain: Optional[str] = None


class BrowserConfig(BaseModel):
    """Browser configuration"""
    headless: bool = False
    browser_type: BrowserType = BrowserType.CHROMIUM
    timeout: int = Field(default=30000, ge=1000, le=300000)  # 1s to 5min
    wait_until: WaitUntil = WaitUntil.NETWORKIDLE
    stealth_mode: bool = True
    fingerprint_randomization: bool = True
    viewport_width: Optional[int] = Field(default=None, ge=100, le=7680)
    viewport_height: Optional[int] = Field(default=None, ge=100, le=4320)
    user_agent: Optional[str] = None
    authentication: BrowserAuthenticationConfig = Field(default_factory=BrowserAuthenticationConfig)


class BatchModeConfig(BaseModel):
    """Batch mode configuration"""
    enabled: bool = True
    delay_between_urls_seconds: float = Field(default=7.0, ge=0.0, le=3600.0)
    delay_variation_seconds: float = Field(default=4.0, ge=0.0, le=3600.0)
    reading_time_min: float = Field(default=3.0, ge=0.0, le=3600.0)
    reading_time_max: float = Field(default=8.0, ge=0.0, le=3600.0)
    pre_request_delay_min: float = Field(default=1.0, ge=0.0, le=3600.0)
    pre_request_delay_max: float = Field(default=3.0, ge=0.0, le=3600.0)
    shuffle_urls: bool = True
    batch_size: Optional[int] = Field(default=None, ge=1)
    delay_between_batches_seconds: float = Field(default=0.0, ge=0.0, le=86400.0)
    
    @field_validator('reading_time_max')
    @classmethod
    def validate_reading_time_range(cls, v, info):
        """Ensure reading_time_max >= reading_time_min"""
        if 'reading_time_min' in info.data and v < info.data['reading_time_min']:
            raise ValueError("reading_time_max must be >= reading_time_min")
        return v
    
    @field_validator('pre_request_delay_max')
    @classmethod
    def validate_pre_request_delay_range(cls, v, info):
        """Ensure pre_request_delay_max >= pre_request_delay_min"""
        if 'pre_request_delay_min' in info.data and v < info.data['pre_request_delay_min']:
            raise ValueError("pre_request_delay_max must be >= pre_request_delay_min")
        return v


class AutomatedBatchesConfig(BaseModel):
    """Automated batches configuration"""
    enabled: bool = False
    proxies_per_batch: int = Field(default=25, ge=1, le=1000)
    delay_between_batches_minutes: float = Field(default=45.0, ge=0.0, le=1440.0)
    delay_variation_minutes: float = Field(default=15.0, ge=0.0, le=1440.0)
    
    @field_validator('delay_variation_minutes')
    @classmethod
    def validate_delay_variation(cls, v, info):
        """Ensure delay_variation doesn't exceed delay_between_batches"""
        if 'delay_between_batches_minutes' in info.data:
            max_variation = info.data['delay_between_batches_minutes'] * 0.5
            if v > max_variation:
                raise ValueError(f"delay_variation_minutes should not exceed 50% of delay_between_batches_minutes")
        return v


class ParallelModeConfig(BaseModel):
    """Parallel mode configuration"""
    enabled: bool = True
    max_concurrent_proxies: int = Field(default=10, ge=1, le=1000)
    distribution: str = "round-robin"
    show_ip_in_logs: bool = False
    automated_batches: AutomatedBatchesConfig = Field(default_factory=AutomatedBatchesConfig)


class ProxyApiAlternativesConfig(BaseModel):
    """Proxy API alternatives configuration"""
    smartproxy: Optional[str] = None
    brightdata: Optional[str] = None
    oxylabs: Optional[str] = None


class ProxyApiConfig(BaseModel):
    """Proxy API configuration"""
    enabled: bool = True
    api_key: str = ""
    api_type: ProxyApiType = ProxyApiType.WEBSHARE
    api_endpoint: str = "https://proxy.webshare.io/api/v2/proxy/list/"
    max_proxies: int = Field(default=100, ge=1, le=10000)
    proxy_format: str = "http://username:password@ip:port"
    alternatives: ProxyApiAlternativesConfig = Field(default_factory=ProxyApiAlternativesConfig)


class ProxyRotationConfig(BaseModel):
    """Proxy rotation configuration"""
    strategy: ProxyRotationStrategy = ProxyRotationStrategy.SMART
    health_check: bool = True
    health_check_timeout: float = Field(default=5.0, ge=1.0, le=60.0)
    max_failures_before_remove: int = Field(default=3, ge=1, le=100)
    consecutive_failures_before_remove: int = Field(default=3, ge=1, le=100)
    failure_rate_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    retry_with_different_proxy: bool = True
    fallback_to_direct: bool = True
    auto_remove_failing_proxies: bool = True
    validate_at_startup: bool = True
    validation_timeout: float = Field(default=10.0, ge=1.0, le=60.0)
    validation_test_url: str = "https://www.google.com"


class BehaviorConfig(BaseModel):
    """Behavior configuration"""
    mouse_movements: bool = True
    scrolling: bool = True
    click_interactions: bool = True
    scroll_pattern: ScrollPattern = ScrollPattern.PROGRESSIVE
    mouse_movement_chance: float = Field(default=0.7, ge=0.0, le=1.0)
    click_chance: float = Field(default=0.3, ge=0.0, le=1.0)
    scroll_delay_min: float = Field(default=0.5, ge=0.0, le=10.0)
    scroll_delay_max: float = Field(default=2.0, ge=0.0, le=10.0)
    
    @field_validator('scroll_delay_max')
    @classmethod
    def validate_scroll_delay_range(cls, v, info):
        """Ensure scroll_delay_max >= scroll_delay_min"""
        if 'scroll_delay_min' in info.data and v < info.data['scroll_delay_min']:
            raise ValueError("scroll_delay_max must be >= scroll_delay_min")
        return v


class CookiesConfig(BaseModel):
    """Cookies configuration"""
    enabled: bool = True
    persist_cookies: bool = True
    cookie_file: str = "cookies.json"
    returning_user_ratio: float = Field(default=0.3, ge=0.0, le=1.0)


class ResourceMonitoringConfig(BaseModel):
    """Resource monitoring configuration"""
    enabled: bool = True
    check_interval_seconds: int = Field(default=30, ge=1, le=3600)
    max_memory_percent: float = Field(default=85.0, ge=0.0, le=100.0)
    max_cpu_percent: float = Field(default=90.0, ge=0.0, le=100.0)
    alert_on_high_usage: bool = True


class AdvancedStealthConfig(BaseModel):
    """Advanced stealth configuration"""
    enabled: bool = True
    mask_canvas: bool = True
    mask_webgl: bool = True
    randomize_headers: bool = True
    humanize_timing: bool = True


class ThrottlingConfig(BaseModel):
    """Throttling configuration"""
    enabled: bool = True
    requests_per_minute: int = Field(default=30, ge=1, le=10000)
    requests_per_second: float = Field(default=2.0, ge=0.1, le=1000.0)
    burst_size: int = Field(default=5, ge=1, le=100)
    adaptive_delays: bool = True
    per_domain_limit: bool = True
    domain_requests_per_minute: int = Field(default=10, ge=1, le=10000)


class MemoryOptimizationConfig(BaseModel):
    """Memory optimization configuration"""
    enabled: bool = True
    browser_pool_size: int = Field(default=5, ge=1, le=100)
    max_browser_idle_time_seconds: int = Field(default=300, ge=10, le=3600)
    cleanup_interval_seconds: int = Field(default=60, ge=10, le=3600)
    force_gc_after_cleanup: bool = True


class TrafficBotConfig(BaseModel):
    """Complete Traffic Bot configuration schema"""
    excel_file: str = "advanced_energy_products_dynamic.xlsx"
    product_url_column: str = "Product URL"
    read_columns: List[str] = Field(default_factory=lambda: ["Product URL", "product_url", "URL", "url"])
    mode: str = "batch"
    delay_minutes: float = Field(default=5.0, ge=0.0, le=1440.0)
    target_domain: str = "www-qa.advancedenergy.com"
    min_delay_seconds: float = Field(default=120.0, ge=0.0, le=3600.0)
    max_retries: int = Field(default=3, ge=0, le=100)
    timeout_seconds: float = Field(default=30.0, ge=1.0, le=600.0)
    enable_proxy_rotation: bool = True
    proxy_file: str = "proxies.json"
    log_file: str = "traffic_bot.log"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    track_traffic: bool = True
    traffic_log_file: str = "traffic_history.json"
    traffic_stats_file: str = "traffic_stats.json"
    speed_mode: SpeedMode = SpeedMode.FAST
    
    # Nested configurations
    batch_mode: BatchModeConfig = Field(default_factory=BatchModeConfig)
    parallel_mode: ParallelModeConfig = Field(default_factory=ParallelModeConfig)
    proxy_api: ProxyApiConfig = Field(default_factory=ProxyApiConfig)
    proxy_rotation: ProxyRotationConfig = Field(default_factory=ProxyRotationConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    behavior: BehaviorConfig = Field(default_factory=BehaviorConfig)
    cookies: CookiesConfig = Field(default_factory=CookiesConfig)
    resource_monitoring: Optional[ResourceMonitoringConfig] = Field(default_factory=ResourceMonitoringConfig)
    advanced_stealth: Optional[AdvancedStealthConfig] = Field(default_factory=AdvancedStealthConfig)
    throttling: Optional[ThrottlingConfig] = Field(default_factory=ThrottlingConfig)
    memory_optimization: Optional[MemoryOptimizationConfig] = Field(default_factory=MemoryOptimizationConfig)
    
    class Config:
        """Pydantic configuration"""
        extra = "allow"  # Allow extra fields for backward compatibility
        validate_assignment = True  # Validate when assigning values

