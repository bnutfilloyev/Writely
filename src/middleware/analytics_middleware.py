"""
Analytics middleware for tracking user interactions.
"""
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from src.services.analytics_service import analytics_service

logger = logging.getLogger(__name__)


class AnalyticsMiddleware(BaseMiddleware):
    """Middleware to track user interactions for analytics."""
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        """Process the event and track analytics."""
        
        # Extract user info
        user = event.from_user
        if not user:
            return await handler(event, data)
        
        # Track different types of interactions
        try:
            if isinstance(event, Message):
                action_data = {
                    "message_type": "text" if event.text else "other",
                    "chat_type": event.chat.type,
                    "command": event.text.split()[0] if event.text and event.text.startswith('/') else None
                }
                
                await analytics_service.track_user_action(
                    user_id=user.id,
                    action="message",
                    data=action_data
                )
                
            elif isinstance(event, CallbackQuery):
                action_data = {
                    "callback_data": event.data,
                    "chat_type": event.message.chat.type if event.message else None
                }
                
                await analytics_service.track_user_action(
                    user_id=user.id,
                    action="callback",
                    data=action_data
                )
                
        except Exception as e:
            logger.error(f"Analytics tracking failed: {e}")
        
        # Continue with the handler
        return await handler(event, data)