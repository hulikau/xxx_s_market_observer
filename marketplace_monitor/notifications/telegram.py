"""Telegram notification system."""

import asyncio
import logging
from typing import Dict, Any
from telegram import Bot
from telegram.error import TelegramError
from .base import BaseNotifier, NotificationMessage


class TelegramNotifier(BaseNotifier):
    """Telegram notification system."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Telegram notifier.
        
        Args:
            config: Telegram configuration containing bot_token and chat_id
        """
        super().__init__(config)
        
        self.bot_token = config.get('bot_token')
        self.chat_id = config.get('chat_id')
        
        if not self.bot_token or not self.chat_id:
            self.logger.error("Telegram bot_token and chat_id are required")
            self.enabled = False
            return
        
        try:
            self.bot = Bot(token=self.bot_token)
        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram bot: {e}")
            self.enabled = False
    
    async def send_notification(self, message: NotificationMessage) -> bool:
        """Send notification via Telegram.
        
        Args:
            message: Notification message to send
            
        Returns:
            True if notification was sent successfully
        """
        if not self.is_enabled():
            self.logger.warning("Telegram notifier is disabled")
            return False
        
        try:
            # Format message for Telegram
            telegram_message = self._format_telegram_message(message)
            
            # Send message
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=telegram_message,
                parse_mode='Markdown',
                disable_web_page_preview=False
            )
            
            self.logger.info(f"Telegram notification sent for {message.product_name}")
            return True
            
        except TelegramError as e:
            self.logger.error(f"Failed to send Telegram message: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error sending Telegram message: {e}")
            return False
    
    def _format_telegram_message(self, message: NotificationMessage) -> str:
        """Format message for Telegram with markdown.
        
        Args:
            message: Notification message
            
        Returns:
            Formatted Telegram message
        """
        # Escape markdown special characters
        def escape_markdown(text: str) -> str:
            if not text:
                return ""
            # Escape markdown v2 special characters
            chars_to_escape = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
            for char in chars_to_escape:
                text = text.replace(char, f'\\{char}')
            return text
        
        product_name = escape_markdown(message.product_name)
        site_name = escape_markdown(message.site_name or "Unknown")
        price = escape_markdown(message.price or "N/A")
        sizes = escape_markdown(", ".join(message.available_sizes))
        
        # Create formatted message
        telegram_msg = f"""🔥 *Size Available\\!*

📦 *Product*: {product_name}
👟 *Available Sizes*: {sizes}
🏪 *Site*: {site_name}
💰 *Price*: {price}

🔗 [View Product]({message.url})

⚡ _Found by Marketplace Monitor_"""
        
        return telegram_msg
    
    async def test_connection(self) -> bool:
        """Test Telegram bot connection.
        
        Returns:
            True if connection is working
        """
        if not self.is_enabled():
            return False
        
        try:
            # Get bot info to test connection
            bot_info = await self.bot.get_me()
            self.logger.info(f"Telegram bot connected: @{bot_info.username}")
            
            # Send test message
            test_message = NotificationMessage(
                title="Test Message",
                message="This is a test message from Marketplace Monitor",
                url="https://example.com",
                product_name="Test Product",
                available_sizes=["Test Size"],
                site_name="Test Site"
            )
            
            return await self.send_notification(test_message)
            
        except Exception as e:
            self.logger.error(f"Telegram connection test failed: {e}")
            return False
    
    def get_bot_info(self) -> Dict[str, Any]:
        """Get Telegram bot information.
        
        Returns:
            Bot information dictionary
        """
        if not self.is_enabled():
            return {}
        
        try:
            # Run async function in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                bot_info = loop.run_until_complete(self.bot.get_me())
                return {
                    'id': bot_info.id,
                    'username': bot_info.username,
                    'first_name': bot_info.first_name,
                    'is_bot': bot_info.is_bot
                }
            finally:
                loop.close()
                
        except Exception as e:
            self.logger.error(f"Failed to get bot info: {e}")
            return {}


def create_telegram_notifier(config: Dict[str, Any]) -> TelegramNotifier:
    """Factory function to create Telegram notifier.
    
    Args:
        config: Telegram configuration
        
    Returns:
        TelegramNotifier instance
    """
    return TelegramNotifier(config)
