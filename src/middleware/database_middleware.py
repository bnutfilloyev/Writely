"""
Database middleware for the IELTS Telegram Bot.
Provides database session management for all handlers.
"""
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.base import get_session_factory


class DatabaseMiddleware(BaseMiddleware):
    """Middleware for database session management."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Provide database session to handlers."""
        
        session_factory = get_session_factory()
        async with session_factory() as session:
            try:
                # Add session to handler data
                data["session"] = session
                
                # Call handler
                result = await handler(event, data)
                
                # Commit transaction if successful
                await session.commit()
                return result
                
            except Exception as e:
                # Rollback transaction on error
                await session.rollback()
                self.logger.error(f"Database error in handler: {e}")
                raise
            finally:
                # Session is automatically closed by context manager
                pass