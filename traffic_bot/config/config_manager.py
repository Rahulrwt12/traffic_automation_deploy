"""Configuration manager for Traffic Bot"""
import json
import os
import logging
from typing import Dict, Any
from pydantic import ValidationError

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

from .config_schema import TrafficBotConfig

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration loading and validation"""
    
    def __init__(self, config_file: str = 'config.json'):
        """
        Initialize configuration manager
        
        Args:
            config_file: Path to configuration JSON file
            
        Raises:
            ValidationError: If configuration schema validation fails
        """
        self.config_file = config_file
        # Load environment variables from .env file first
        self._load_env_file()
        self.config = self._load_config()
        self._validate_config()
    
    def _load_env_file(self):
        """Load environment variables from .env file if it exists"""
        if DOTENV_AVAILABLE:
            # Try to load .env file from current directory
            env_path = os.path.join(os.getcwd(), '.env')
            if os.path.exists(env_path):
                load_dotenv(env_path)
                logger.info("Environment variables loaded from .env file")
            else:
                # Also try in the same directory as config file
                config_dir = os.path.dirname(os.path.abspath(self.config_file))
                env_path = os.path.join(config_dir, '.env')
                if os.path.exists(env_path):
                    load_dotenv(env_path)
                    logger.info(f"Environment variables loaded from {env_path}")
        else:
            logger.warning("python-dotenv not installed. Install it with: pip install python-dotenv")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        if not os.path.exists(self.config_file):
            logger.warning(f"Config file {self.config_file} not found. Using defaults.")
            return self._get_default_config()
        
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            logger.info(f"Configuration loaded from {self.config_file}")
            
            # Override with environment variables if available
            config = self._apply_environment_overrides(config)
            
            return config
        except Exception as e:
            logger.error(f"Error loading config file: {e}. Using defaults.")
            return self._get_default_config()
    
    def _apply_environment_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides to configuration"""
        # Proxy API Key
        proxy_api_key = os.getenv('PROXY_API_KEY')
        if proxy_api_key:
            if 'proxy_api' not in config:
                config['proxy_api'] = {}
            config['proxy_api']['api_key'] = proxy_api_key
            logger.info("Proxy API key loaded from environment variable")
        elif config.get('proxy_api', {}).get('api_key') == '':
            logger.warning("Proxy API key not set in config.json or environment variable PROXY_API_KEY")
        
        # Browser Authentication Credentials
        browser_auth_username = os.getenv('BROWSER_AUTH_USERNAME')
        browser_auth_password = os.getenv('BROWSER_AUTH_PASSWORD')
        
        if browser_auth_username or browser_auth_password:
            if 'browser' not in config:
                config['browser'] = {}
            if 'authentication' not in config['browser']:
                config['browser']['authentication'] = {}
            
            if browser_auth_username:
                config['browser']['authentication']['username'] = browser_auth_username
                config['browser']['authentication']['enabled'] = True
            if browser_auth_password:
                config['browser']['authentication']['password'] = browser_auth_password
                config['browser']['authentication']['enabled'] = True
            
            logger.info("Browser authentication credentials loaded from environment variables")
        
        return config
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "excel_file": "advanced_energy_products_dynamic.xlsx",
            "product_url_column": "Product URL",
            "mode": "batch",
            "delay_minutes": 5,
            "target_domain": "www-qa.advancedenergy.com",
            "min_delay_seconds": 120,
            "max_retries": 3,
            "timeout_seconds": 30,
            "enable_proxy_rotation": True,
            "track_traffic": True,
            "traffic_log_file": "traffic_history.json",
            "traffic_stats_file": "traffic_stats.json",
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
            "proxy_api": {
                "enabled": True,
                "api_key": "",
                "api_type": "webshare",
                "api_endpoint": "https://proxy.webshare.io/api/v2/proxy/list/",
                "max_proxies": 10
            },
            "browser": {
                "headless": False,
                "browser_type": "chromium",
                "viewport_width": None,
                "viewport_height": None,
                "user_agent": None,
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
            "cookies": {
                "enabled": True,
                "persist_cookies": True,
                "cookie_file": "cookies.json",
                "returning_user_ratio": 0.3
            }
        }
    
    def _validate_config(self):
        """
        Validate configuration using Pydantic schema
        
        Raises:
            ValidationError: If configuration doesn't match schema
        """
        try:
            # Validate entire config with Pydantic - this will raise ValidationError if invalid
            validated_config = TrafficBotConfig(**self.config)
            # Convert back to dict for compatibility with existing code
            self.config = validated_config.model_dump(exclude_none=False)
            logger.info("Configuration validated successfully")
        except ValidationError as e:
            # Format validation errors into a readable message
            error_messages = []
            for error in e.errors():
                field_path = " -> ".join(str(loc) for loc in error["loc"])
                error_msg = f"{field_path}: {error['msg']}"
                if "input" in error:
                    error_msg += f" (got: {error['input']})"
                error_messages.append(error_msg)
            
            error_summary = "\n".join(error_messages)
            logger.error(f"Configuration validation failed:\n{error_summary}")
            # Re-raise the original ValidationError - it contains all the details
            raise
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value if value is not None else default
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get entire configuration section"""
        return self.config.get(section, {})
    
    def save(self):
        """Save current configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"Configuration saved to {self.config_file}")
        except Exception as e:
            logger.error(f"Error saving config: {e}")

