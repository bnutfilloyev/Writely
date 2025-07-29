"""
Telegram bot handlers package.
Contains all simplified message and callback handlers for the IELTS bot.
"""

from .simple_start_handler import router as start_router
from .simple_submission_handler import router as submission_router
from .simple_callback_handler import router as callback_router

__all__ = [
    'start_router',
    'submission_router', 
    'callback_router'
]