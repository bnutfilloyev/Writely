"""
Custom exceptions for IELTS Telegram Bot
"""

from .base_exceptions import (
    IELTSBotException,
    ValidationError,
    RateLimitError,
    DatabaseError,
    AIServiceError,
    ConfigurationError
)

from .error_handler import (
    ErrorHandler,
    ErrorContext,
    ErrorResponse,
    ErrorSeverity
)

__all__ = [
    'IELTSBotException',
    'ValidationError', 
    'RateLimitError',
    'DatabaseError',
    'AIServiceError',
    'ConfigurationError',
    'ErrorHandler',
    'ErrorContext',
    'ErrorResponse',
    'ErrorSeverity'
]