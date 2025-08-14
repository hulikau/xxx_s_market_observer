"""Tests for configuration system."""

import pytest
import tempfile
from pathlib import Path

from marketplace_monitor.config import Config, SiteConfig, MonitorConfig


def test_site_config_validation():
    """Test SiteConfig validation."""
    # Valid config
    config = SiteConfig(
        name="Test Site",
        parser="generic",
        urls=["https://example.com"],
        sizes=["US 9", "US 10"]
    )
    assert config.name == "Test Site"
    assert config.check_interval == 300  # default
    
    # Invalid check interval
    with pytest.raises(ValueError):
        SiteConfig(
            name="Test Site",
            parser="generic",
            urls=["https://example.com"],
            sizes=["US 9"],
            check_interval=30  # too low
        )


def test_config_creation():
    """Test configuration file creation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_config.yaml"
        config_manager = Config(str(config_path))
        
        # Create example config
        example_config = config_manager.create_example_config()
        assert len(example_config.sites) > 0
        assert example_config.global_check_interval == 300
        
        # Save and load
        config_manager.save(example_config)
        assert config_path.exists()
        
        loaded_config = config_manager.load()
        assert len(loaded_config.sites) == len(example_config.sites)
        assert loaded_config.global_check_interval == example_config.global_check_interval


def test_config_file_not_found():
    """Test behavior when config file doesn't exist."""
    config_manager = Config("/nonexistent/config.yaml")
    
    with pytest.raises(FileNotFoundError):
        config_manager.load()
