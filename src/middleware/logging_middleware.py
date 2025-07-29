"""
Logging middleware for the IELTS Telegram Bot.
Logs all incoming messages and callback queries for monitoring and debugging.
"""
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject


class LoggingMiddleware(BaseMiddleware):
    """Middleware for logging bot interactions."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Log the event and call the handler."""
        
        # Log message events
        if isinstance(event, Message):
            user_info = f"@{event.from_user.username}" if event.from_user.username else f"ID:{event.from_user.id}"
            
            if event.text:
                # Truncate long messages for logging
                text_preview = event.text[:100] + "..." if len(event.text) > 100 else event.text
                self.logger.info(f"Message from {user_info}: {text_preview}")
            else:
                self.logger.info(f"Non-text message from {user_info}: {event.content_type}")
        
        # Log callback query events
        elif isinstance(event, CallbackQuery):
            user_info = f"@{event.from_user.username}" if event.from_user.username else f"ID:{event.from_user.id}"
            self.logger.info(f"Callback query from {user_info}: {event.data}")
        
        # Call the handler
        try:
            result = await handler(event, data)
            return result
        except Exception as e:
            # Log handler errors
            self.logger.error(f"Handler error for {type(event).__name__}: {e}")
            raise