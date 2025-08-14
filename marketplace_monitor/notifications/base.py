"""Base notification system."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from ..parsers.base import ParseResult


@dataclass
class NotificationMessage:
    """Notification message data."""
    
    title: str
    message: str
    url: str
    product_name: str
    available_sizes: List[str]
    price: Optional[str] = None
    site_name: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseNotifier(ABC):
    """Base class for all notification systems."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize notifier.
        
        Args:
            config: Notifier configuration
        """
        self.config = config
        self.enabled = config.get('enabled', True)
        self.logger = logging.getLogger(f"notifier.{self.__class__.__name__.lower()}")
    
    @abstractmethod
    async def send_notification(self, message: NotificationMessage) -> bool:
        """Send a notification message.
        
        Args:
            message: Notification message to send
            
        Returns:
            True if notification was sent successfully
        """
        pass
    
    def is_enabled(self) -> bool:
        """Check if this notifier is enabled."""
        return self.enabled
    
    def create_message_from_result(self, result: ParseResult, site_name: str) -> NotificationMessage:
        """Create notification message from parse result.
        
        Args:
            result: Parse result with size availability
            site_name: Name of the site
            
        Returns:
            NotificationMessage object
        """
        available_sizes = list(result.available_sizes)
        sizes_text = ", ".join(available_sizes) if available_sizes else "None"
        
        title = f"🔥 Size Available: {result.product_name or 'Product'}"
        
        message_parts = [
            f"📦 **Product**: {result.product_name or 'Unknown'}",
            f"👟 **Available Sizes**: {sizes_text}",
            f"🏪 **Site**: {site_name}",
        ]
        
        if result.price:
            message_parts.append(f"💰 **Price**: {result.price}")
        
        message_parts.extend([
            f"🔗 **URL**: {result.url}",
            "",
            "⚡ *Found by Marketplace Monitor*"
        ])
        
        return NotificationMessage(
            title=title,
            message="\n".join(message_parts),
            url=result.url,
            product_name=result.product_name or "Unknown",
            available_sizes=available_sizes,
            price=result.price,
            site_name=site_name,
            metadata=result.metadata
        )
