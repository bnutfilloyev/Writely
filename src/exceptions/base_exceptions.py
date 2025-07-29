"""
Base exceptions for IELTS Telegram Bot error handling
"""

from typing import Optional, Dict, Any


class IELTSBotException(Exception):
    """Base exception for all IELTS bot errors"""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        user_message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        recoverable: bool = True
    ):
        super().__init__(message)
        self.error_code = error_code
        self.user_message = user_message or message
        self.context = context or {}
        self.recoverable = recoverable


class ValidationError(IELTSBotException):
    """Raised when user input validation fails"""
    
    def __init__(
        self, 
        message: str, 
        validation_type: str,
        user_message: Optional[str] = None,
        suggestions: Optional[list] = None
    ):
        super().__init__(
            message=message,
            error_code=f"VALIDATION_{validation_type.upper()}",
            user_message=user_message,
            recoverable=True
        )
        self.validation_type = validation_type
        self.suggestions = suggestions or []


class RateLimitError(IELTSBotException):
    """Raised when rate limits are exceeded"""
    
    def __init__(
        self, 
        message: str,
        limit_type: str,
        current_count: int,
        limit: int,
        reset_time: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code=f"RATE_LIMIT_{limit_type.upper()}",
            user_message=message,
            recoverable=True
        )
        self.limit_type = limit_type
        self.current_count = current_count
        self.limit = limit
        self.reset_time = reset_time


class DatabaseError(IELTSBotException):
    """Raised when database operations fail"""
    
    def __init__(
        self, 
        message: str,
        operation: str,
        table: Optional[str] = None,
        recoverable: bool = True
    ):
        super().__init__(
            message=message,
            error_code=f"DATABASE_{operation.upper()}",
            user_message="Database temporarily unavailable. Please try again.",
            recoverable=recoverable
        )
        self.operation = operation
        self.table = table


class AIServiceError(IELTSBotException):
    """Raised when AI service operations fail"""
    
    def __init__(
        self, 
        message: str,
        service_type: str = "openai",
        error_type: str = "unknown",
        retry_after: Optional[int] = None,
        recoverable: bool = True
    ):
        super().__init__(
            message=message,
            error_code=f"AI_{service_type.upper()}_{error_type.upper()}",
            user_message="Assessment service temporarily unavailable. Please try again in a few minutes.",
            recoverable=recoverable
        )
        self.service_type = service_type
        self.error_type = error_type
        self.retry_after = retry_after


class ConfigurationError(IELTSBotException):
    """Raised when configuration is invalid or missing"""
    
    def __init__(self, message: str, config_key: str):
        super().__init__(
            message=message,
            error_code=f"CONFIG_{config_key.upper()}",
            user_message="Service temporarily unavailable due to configuration issues.",
            recoverable=False
        )
        self.config_key = config_key