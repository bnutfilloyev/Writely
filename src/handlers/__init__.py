"""
Telegram bot handlers package.
Contains all message and callback handlers for the IELTS bot.
"""

from .start_handler import router as start_router
from .submission_handler import router as submission_router
from .history_handler import router as history_router
from .callback_handler import router as callback_router

__all__ = [
    'start_router',
    'submission_router', 
    'history_router',
    'callback_router'
]