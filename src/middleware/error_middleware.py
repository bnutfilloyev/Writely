"""
Error handling middleware for the IELTS Telegram Bot.
Provides global error handling and recovery for all bot interactions.
"""
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject, InlineKeyboardMarkup, InlineKeyboardButton

from src.exceptions import (
    ValidationError, RateLimitError, DatabaseError, 
    AIServiceError, ConfigurationError, ErrorHandler, ErrorContext
)


class ErrorMiddleware(BaseMiddleware):
    """Middleware for global error handling."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.error_handler = ErrorHandler()
    
    def _get_back_to_menu_keyboard(self) -> InlineKeyboardMarkup:
        """Create back to menu keyboard for error responses."""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_menu")]
        ])
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Handle errors from bot handlers."""
        
        try:
            return await handler(event, data)
        
        except (ValidationError, RateLimitError, DatabaseError, AIServiceError, ConfigurationError) as e:
            # Handle known application errors
            await self._handle_known_error(event, e)
        
        except Exception as e:
            # Handle unexpected errors
            await self._handle_unexpected_error(event, e)
    
    async def _handle_known_error(self, event: TelegramObject, error: Exception):
        """Handle known application errors with user-friendly messages."""
        try:
            # Create error context
            error_context = ErrorContext(
                user_id=event.from_user.id if hasattr(event, 'from_user') else None,
                username=event.from_user.username if hasattr(event, 'from_user') else None,
                message_text=getattr(event, 'text', '')[:100] if hasattr(event, 'text') else '',
                handler_name="error_middleware",
                timestamp=None
            )
            
            # Get error response
            error_response = self.error_handler.handle_error(error, error_context)
            
            # Send error message
            if isinstance(event, Message):
                await event.answer(
                    text=error_response.message,
                    reply_markup=error_response.keyboard or self._get_back_to_menu_keyboard(),
                    parse_mode=error_response.parse_mode
                )
            elif isinstance(event, CallbackQuery):
                await event.message.edit_text(
                    text=error_response.message,
                    reply_markup=error_response.keyboard or self._get_back_to_menu_keyboard(),
                    parse_mode=error_response.parse_mode
                )
                await event.answer()
        
        except Exception as e:
            self.logger.error(f"Error in error handler: {e}")
            await self._send_fallback_error(event)
    
    async def _handle_unexpected_error(self, event: TelegramObject, error: Exception):
        """Handle unexpected errors with generic fallback."""
        self.logger.error(f"Unexpected error in handler: {error}", exc_info=True)
        await self._send_fallback_error(event)
    
    async def _send_fallback_error(self, event: TelegramObject):
        """Send fallback error message when error handling fails."""
        fallback_message = (
            "❌ Sorry, something went wrong. Please try again later.\n\n"
            "If the problem persists, please restart the bot with /start"
        )
        
        try:
            if isinstance(event, Message):
                await event.answer(
                    text=fallback_message,
                    reply_markup=self._get_back_to_menu_keyboard()
                )
            elif isinstance(event, CallbackQuery):
                await event.message.edit_text(
                    text=fallback_message,
                    reply_markup=self._get_back_to_menu_keyboard()
                )
                await event.answer()
        except Exception as e:
            self.logger.error(f"Failed to send fallback error message: {e}")