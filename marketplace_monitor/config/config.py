"""Configuration management for marketplace monitor."""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv


class SiteConfig(BaseModel):
    """Configuration for a single site to monitor."""
    
    name: str = Field(..., description="Name of the site")
    parser: str = Field(..., description="Parser type to use for this site")
    urls: List[str] = Field(..., description="URLs to monitor on this site")
    sizes: List[str] = Field(..., description="Sizes to monitor for")
    check_interval: int = Field(default=300, description="Check interval in seconds")
    enabled: bool = Field(default=True, description="Whether monitoring is enabled")
    headers: Optional[Dict[str, str]] = Field(default=None, description="Custom headers for requests")
    cookies: Optional[Dict[str, str]] = Field(default=None, description="Custom cookies for requests")
    
    @validator('check_interval')
    def validate_check_interval(cls, v):
        if v < 60:
            raise ValueError('Check interval must be at least 60 seconds')
        return v


class NotificationConfig(BaseModel):
    """Configuration for notifications."""
    
    telegram: Optional[Dict[str, Any]] = Field(default=None, description="Telegram notification config")
    email: Optional[Dict[str, Any]] = Field(default=None, description="Email notification config")
    webhook: Optional[Dict[str, Any]] = Field(default=None, description="Webhook notification config")


class MonitorConfig(BaseModel):
    """Main monitoring configuration."""
    
    sites: List[SiteConfig] = Field(..., description="Sites to monitor")
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)
    global_check_interval: int = Field(default=300, description="Global check interval in seconds")
    max_concurrent_checks: int = Field(default=5, description="Maximum concurrent site checks")
    user_agent: str = Field(
        default="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        description="User agent string for requests"
    )
    timeout: int = Field(default=30, description="Request timeout in seconds")
    retry_attempts: int = Field(default=3, description="Number of retry attempts for failed requests")
    log_level: str = Field(default="INFO", description="Logging level")


class Config:
    """Configuration manager for marketplace monitor."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration manager.
        
        Args:
            config_path: Path to configuration file. If None, looks for default locations.
        """
        load_dotenv()
        self.config_path = self._find_config_path(config_path)
        self._config: Optional[MonitorConfig] = None
    
    def _find_config_path(self, config_path: Optional[str]) -> Path:
        """Find configuration file path."""
        if config_path:
            return Path(config_path)
        
        # Look for config in standard locations
        possible_paths = [
            Path.cwd() / "config.yaml",
            Path.cwd() / "config.yml",
            Path.home() / ".marketplace-monitor" / "config.yaml",
            Path.home() / ".config" / "marketplace-monitor" / "config.yaml",
        ]
        
        for path in possible_paths:
            if path.exists():
                return path
        
        # Return default path if none found
        return Path.cwd() / "config.yaml"
    
    def load(self) -> MonitorConfig:
        """Load configuration from file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        self._config = MonitorConfig(**config_data)
        return self._config
    
    def save(self, config: MonitorConfig) -> None:
        """Save configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config.dict(), f, default_flow_style=False, indent=2)
        
        self._config = config
    
    def get(self) -> MonitorConfig:
        """Get current configuration."""
        if self._config is None:
            self._config = self.load()
        return self._config
    
    def create_example_config(self) -> MonitorConfig:
        """Create an example configuration."""
        example_config = MonitorConfig(
            sites=[
                SiteConfig(
                    name="Example Store",
                    parser="generic",
                    urls=[
                        "https://example-store.com/product/sneakers-123",
                        "https://example-store.com/product/sneakers-456"
                    ],
                    sizes=["US 9", "US 10", "US 11"],
                    check_interval=300,
                    enabled=True
                ),
                SiteConfig(
                    name="Another Store",
                    parser="another_store",
                    urls=[
                        "https://another-store.com/shoes/running-shoes"
                    ],
                    sizes=["42", "43", "44"],
                    check_interval=600,
                    enabled=False
                )
            ],
            notifications=NotificationConfig(
                telegram={
                    "bot_token": "YOUR_BOT_TOKEN",
                    "chat_id": "YOUR_CHAT_ID",
                    "enabled": True
                }
            ),
            global_check_interval=300,
            max_concurrent_checks=5,
            log_level="INFO"
        )
        return example_config
    
    @staticmethod
    def get_env_var(key: str, default: Optional[str] = None) -> Optional[str]:
        """Get environment variable value."""
        return os.getenv(key, default)
