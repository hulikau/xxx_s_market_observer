"""Marketplace Monitor - A tool to monitor marketplace sites for product availability."""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .monitor import MarketplaceMonitor
from .config import Config

__all__ = ["MarketplaceMonitor", "Config"]
