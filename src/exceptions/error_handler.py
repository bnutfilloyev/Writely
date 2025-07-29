"""
Centralized error handling for IELTS Telegram Bot
"""

import logging
import traceback
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, Callable, Awaitable
from datetime import datetime, timedelta

from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from .base_exceptions import (
    IELTSBotException, ValidationError, RateLimitError, 
    DatabaseError, AIServiceError, ConfigurationError
)

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorContext:
    """Context information for error handling"""
    user_id: Optional[int] = None
    username: Optional[str] = None
    message_text: Optional[str] = None
    handler_name: Optional[str] = None
    timestamp: Optional[datetime] = None
    additional_data: Optional[Dict[str, Any]] = None


@dataclass
class ErrorResponse:
    """Response to send to user after error handling"""
    message: str
    keyboard: Optional[InlineKeyboardMarkup] = None
    parse_mode: str = "Markdown"
    show_retry_button: bool = False
    show_support_button: bool = False


class ErrorHandler:
    """Centralized error handler for the IELTS bot"""
    
    def __init__(self):
        self.error_counts: Dict[str, int] = {}
        self.last_error_time: Dict[str, datetime] = {}
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_window = timedelta(minutes=5)
        
    def handle_error(
        self, 
        error: Exception, 
        context: ErrorContext,
        fallback_message: str = "An unexpected error occurred. Please try again."
    ) -> ErrorResponse:
        """
        Handle any error and return appropriate user response
        
        Args:
            error: The exception that occurred
            context: Context information about the error
            fallback_message: Default message if no specific handling exists
            
        Returns:
            ErrorResponse with user-friendly message and options
        """
        try:
            # Log the error with context
            self._log_error(error, context)
            
            # Check if this is a known exception type
            if isinstance(error, IELTSBotException):
                return self._handle_known_error(error, context)
            
            # Handle specific exception types
            if isinstance(error, ConnectionError):
                return self._handle_connection_error(error, context)
            
            if isinstance(error, TimeoutError):
                return self._handle_timeout_error(error, context)
            
            # Handle unknown errors
            return self._handle_unknown_error(error, context, fallback_message)
            
        except Exception as handler_error:
            logger.critical(f"Error in error handler: {handler_error}")
            return ErrorResponse(
                message="❌ A critical error occurred. Please contact support.",
                keyboard=self._get_support_keyboard(),
                show_support_button=True
            )
    
    def _handle_known_error(self, error: IELTSBotException, context: ErrorContext) -> ErrorResponse:
        """Handle known IELTS bot exceptions"""
        
        if isinstance(error, ValidationError):
            return self._handle_validation_error(error, context)
        
        elif isinstance(error, RateLimitError):
            return self._handle_rate_limit_error(error, context)
        
        elif isinstance(error, DatabaseError):
            return self._handle_database_error(error, context)
        
        elif isinstance(error, AIServiceError):
            return self._handle_ai_service_error(error, context)
        
        elif isinstance(error, ConfigurationError):
            return self._handle_configuration_error(error, context)
        
        else:
            return ErrorResponse(
                message=f"❌ {error.user_message}",
                keyboard=self._get_back_to_menu_keyboard(),
                show_retry_button=error.recoverable
            )
    
    def _handle_validation_error(self, error: ValidationError, context: ErrorContext) -> ErrorResponse:
        """Handle validation errors with helpful suggestions"""
        message = f"❌ {error.user_message}"
        
        if error.suggestions:
            message += "\n\n💡 **Suggestions:**"
            for suggestion in error.suggestions:
                message += f"\n• {suggestion}"
        
        return ErrorResponse(
            message=message,
            keyboard=self._get_back_to_menu_keyboard(),
            show_retry_button=True
        )
    
    def _handle_rate_limit_error(self, error: RateLimitError, context: ErrorContext) -> ErrorResponse:
        """Handle rate limit errors with upgrade suggestions"""
        message = f"⏰ {error.user_message}"
        
        if error.reset_time:
            message += f"\n\n🔄 Resets: {error.reset_time}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Upgrade to Pro", callback_data="upgrade_pro")],
            [InlineKeyboardButton(text="📊 Check History", callback_data="show_history")],
            [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_menu")]
        ])
        
        return ErrorResponse(
            message=message,
            keyboard=keyboard
        )
    
    def _handle_database_error(self, error: DatabaseError, context: ErrorContext) -> ErrorResponse:
        """Handle database errors with graceful degradation"""
        severity = self._get_error_severity(error, context)
        
        if severity == ErrorSeverity.LOW:
            message = "⚠️ Some features may be temporarily limited, but evaluation will continue."
        else:
            message = "❌ Database temporarily unavailable. Please try again in a few minutes."
        
        keyboard = self._get_retry_keyboard() if error.recoverable else self._get_support_keyboard()
        
        return ErrorResponse(
            message=message,
            keyboard=keyboard,
            show_retry_button=error.recoverable,
            show_support_button=severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]
        )
    
    def _handle_ai_service_error(self, error: AIServiceError, context: ErrorContext) -> ErrorResponse:
        """Handle AI service errors with retry suggestions"""
        message = f"🤖 {error.user_message}"
        
        if error.retry_after:
            message += f"\n\n⏱️ Please wait {error.retry_after} seconds before retrying."
        
        # Check if we should enable circuit breaker
        if self._should_circuit_break(error, context):
            message += "\n\n🔧 Service is experiencing high load. Please try again later."
            keyboard = self._get_support_keyboard()
        else:
            keyboard = self._get_retry_keyboard()
        
        return ErrorResponse(
            message=message,
            keyboard=keyboard,
            show_retry_button=error.recoverable and not self._should_circuit_break(error, context)
        )
    
    def _handle_configuration_error(self, error: ConfigurationError, context: ErrorContext) -> ErrorResponse:
        """Handle configuration errors (usually critical)"""
        return ErrorResponse(
            message="🔧 Service temporarily unavailable due to maintenance. Please try again later.",
            keyboard=self._get_support_keyboard(),
            show_support_button=True
        )
    
    def _handle_connection_error(self, error: ConnectionError, context: ErrorContext) -> ErrorResponse:
        """Handle connection errors"""
        return ErrorResponse(
            message="🌐 Connection issue detected. Please check your internet and try again.",
            keyboard=self._get_retry_keyboard(),
            show_retry_button=True
        )
    
    def _handle_timeout_error(self, error: TimeoutError, context: ErrorContext) -> ErrorResponse:
        """Handle timeout errors"""
        return ErrorResponse(
            message="⏰ Request timed out. The service might be busy. Please try again.",
            keyboard=self._get_retry_keyboard(),
            show_retry_button=True
        )
    
    def _handle_unknown_error(self, error: Exception, context: ErrorContext, fallback_message: str) -> ErrorResponse:
        """Handle unknown errors with generic response"""
        severity = self._get_error_severity(error, context)
        
        if severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            message = "❌ A serious error occurred. Our team has been notified."
            keyboard = self._get_support_keyboard()
            show_support = True
        else:
            message = f"❌ {fallback_message}"
            keyboard = self._get_retry_keyboard()
            show_support = False
        
        return ErrorResponse(
            message=message,
            keyboard=keyboard,
            show_retry_button=True,
            show_support_button=show_support
        )
    
    def _log_error(self, error: Exception, context: ErrorContext):
        """Log error with context information"""
        log_data = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'user_id': context.user_id,
            'username': context.username,
            'handler': context.handler_name,
            'timestamp': context.timestamp or datetime.now(),
            'traceback': traceback.format_exc()
        }
        
        if context.additional_data:
            log_data.update(context.additional_data)
        
        # Log at appropriate level based on error type
        if isinstance(error, (ValidationError, RateLimitError)):
            logger.warning(f"User error: {log_data}")
        elif isinstance(error, (DatabaseError, AIServiceError)):
            logger.error(f"Service error: {log_data}")
        elif isinstance(error, ConfigurationError):
            logger.critical(f"Configuration error: {log_data}")
        else:
            logger.error(f"Unknown error: {log_data}")
    
    def _get_error_severity(self, error: Exception, context: ErrorContext) -> ErrorSeverity:
        """Determine error severity based on type and context"""
        if isinstance(error, ConfigurationError):
            return ErrorSeverity.CRITICAL
        
        if isinstance(error, DatabaseError) and not error.recoverable:
            return ErrorSeverity.HIGH
        
        if isinstance(error, AIServiceError) and error.error_type in ["auth", "quota"]:
            return ErrorSeverity.HIGH
        
        if isinstance(error, (ValidationError, RateLimitError)):
            return ErrorSeverity.LOW
        
        # Check error frequency for circuit breaking
        error_key = f"{type(error).__name__}_{context.user_id or 'global'}"
        if self._is_frequent_error(error_key):
            return ErrorSeverity.MEDIUM
        
        return ErrorSeverity.LOW
    
    def _should_circuit_break(self, error: Exception, context: ErrorContext) -> bool:
        """Check if circuit breaker should be activated"""
        error_key = f"{type(error).__name__}_global"
        current_time = datetime.now()
        
        # Reset counter if window has passed
        if (error_key in self.last_error_time and 
            current_time - self.last_error_time[error_key] > self.circuit_breaker_window):
            self.error_counts[error_key] = 0
        
        # Increment counter
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        self.last_error_time[error_key] = current_time
        
        return self.error_counts[error_key] >= self.circuit_breaker_threshold
    
    def _is_frequent_error(self, error_key: str) -> bool:
        """Check if this error is occurring frequently"""
        return self.error_counts.get(error_key, 0) >= 3
    
    def _get_back_to_menu_keyboard(self) -> InlineKeyboardMarkup:
        """Get back to menu keyboard"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_menu")]
        ])
    
    def _get_retry_keyboard(self) -> InlineKeyboardMarkup:
        """Get retry keyboard with back option"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Try Again", callback_data="retry_last_action")],
            [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_menu")]
        ])
    
    def _get_support_keyboard(self) -> InlineKeyboardMarkup:
        """Get support keyboard"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📞 Contact Support", callback_data="contact_support")],
            [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_menu")]
        ])

    async def send_processing_message(
        self, 
        message: Message, 
        processing_text: str = "🔄 Processing your request..."
    ) -> Message:
        """
        Send processing message for long-running operations
        
        Args:
            message: Original message to reply to
            processing_text: Text to show while processing
            
        Returns:
            Message object of the processing message
        """
        return await message.answer(processing_text)
    
    async def update_processing_message(
        self, 
        processing_msg: Message, 
        update_text: str
    ):
        """
        Update processing message with new status
        
        Args:
            processing_msg: The processing message to update
            update_text: New text to show
        """
        try:
            await processing_msg.edit_text(update_text)
        except Exception as e:
            logger.warning(f"Could not update processing message: {e}")
    
    async def cleanup_processing_message(self, processing_msg: Message):
        """
        Clean up processing message after completion
        
        Args:
            processing_msg: The processing message to delete
        """
        try:
            await processing_msg.delete()
        except Exception as e:
            logger.warning(f"Could not delete processing message: {e}")


# Global error handler instance
error_handler = ErrorHandler()