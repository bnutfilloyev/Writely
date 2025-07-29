"""
Production logging configuration for the IELTS Telegram Bot.
"""
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Dict, Any

from .settings import settings


class ProductionLoggingConfig:
    """Production logging configuration with file rotation and structured logging."""
    
    def __init__(self):
        self.log_dir = Path(os.getenv("LOG_FILE_PATH", "/app/logs")).parent
        self.log_file = self.log_dir / "bot.log"
        self.error_log_file = self.log_dir / "error.log"
        self.access_log_file = self.log_dir / "access.log"
        
        # Create log directory if it doesn't exist
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Log rotation settings
        self.max_bytes = int(os.getenv("LOG_MAX_SIZE", "10485760"))  # 10MB
        self.backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))
    
    def get_formatter(self, include_extra: bool = False) -> logging.Formatter:
        """Get logging formatter with optional extra fields."""
        if include_extra:
            format_string = (
                "%(asctime)s - %(name)s - %(levelname)s - "
                "%(filename)s:%(lineno)d - %(funcName)s - %(message)s"
            )
        else:
            format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        
        return logging.Formatter(
            format_string,
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    def setup_file_handler(self, filename: Path, level: int = logging.INFO) -> logging.Handler:
        """Setup rotating file handler."""
        try:
            # Ensure directory exists and is writable
            filename.parent.mkdir(parents=True, exist_ok=True)
            
            handler = logging.handlers.RotatingFileHandler(
                filename=filename,
                maxBytes=self.max_bytes,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
            handler.setLevel(level)
            handler.setFormatter(self.get_formatter(include_extra=True))
            return handler
        except (PermissionError, OSError) as e:
            # If file logging fails, fall back to console only
            print(f"Warning: Could not set up file logging ({e}). Using console logging only.")
            return self.setup_console_handler(level)
    
    def setup_console_handler(self, level: int = logging.INFO) -> logging.Handler:
        """Setup console handler for stdout."""
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(self.get_formatter())
        return handler
    
    def setup_error_handler(self) -> logging.Handler:
        """Setup dedicated error handler for ERROR and CRITICAL logs."""
        handler = logging.handlers.RotatingFileHandler(
            filename=self.error_log_file,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        handler.setLevel(logging.ERROR)
        handler.setFormatter(self.get_formatter(include_extra=True))
        return handler
    
    def configure_root_logger(self) -> None:
        """Configure the root logger with all handlers."""
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Add console handler (always)
        console_handler = self.setup_console_handler()
        root_logger.addHandler(console_handler)
        
        # Add file handlers for production
        if not settings.DEBUG:
            # Main log file
            file_handler = self.setup_file_handler(self.log_file)
            root_logger.addHandler(file_handler)
            
            # Error log file
            error_handler = self.setup_error_handler()
            root_logger.addHandler(error_handler)
    
    def configure_specific_loggers(self) -> None:
        """Configure specific loggers for different components."""
        # Aiogram logger
        aiogram_logger = logging.getLogger("aiogram")
        aiogram_logger.setLevel(logging.WARNING)
        
        # OpenAI logger
        openai_logger = logging.getLogger("openai")
        openai_logger.setLevel(logging.WARNING)
        
        # SQLAlchemy logger
        sqlalchemy_logger = logging.getLogger("sqlalchemy.engine")
        if settings.DEBUG:
            sqlalchemy_logger.setLevel(logging.INFO)
        else:
            sqlalchemy_logger.setLevel(logging.WARNING)
        
        # HTTP clients
        httpx_logger = logging.getLogger("httpx")
        httpx_logger.setLevel(logging.WARNING)
        
        # Application loggers
        app_loggers = [
            "src.handlers",
            "src.services",
            "src.repositories",
            "src.middleware",
            "src.database"
        ]
        
        for logger_name in app_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    
    def setup_access_logging(self) -> logging.Logger:
        """Setup access logging for API requests."""
        access_logger = logging.getLogger("access")
        access_logger.setLevel(logging.INFO)
        
        # Don't propagate to root logger
        access_logger.propagate = False
        
        # Console handler for access logs
        console_handler = self.setup_console_handler()
        access_logger.addHandler(console_handler)
        
        # File handler for access logs (production only)
        if not settings.DEBUG:
            access_handler = self.setup_file_handler(self.access_log_file)
            access_logger.addHandler(access_handler)
        
        return access_logger
    
    def configure_all(self) -> Dict[str, Any]:
        """Configure all logging components and return configuration info."""
        self.configure_root_logger()
        self.configure_specific_loggers()
        access_logger = self.setup_access_logging()
        
        config_info = {
            "log_level": settings.LOG_LEVEL,
            "debug_mode": settings.DEBUG,
            "log_directory": str(self.log_dir),
            "log_files": {
                "main": str(self.log_file),
                "error": str(self.error_log_file),
                "access": str(self.access_log_file)
            },
            "rotation": {
                "max_bytes": self.max_bytes,
                "backup_count": self.backup_count
            }
        }
        
        # Log configuration info
        logger = logging.getLogger(__name__)
        logger.info("Logging configuration completed")
        logger.info(f"Log level: {settings.LOG_LEVEL}")
        logger.info(f"Debug mode: {settings.DEBUG}")
        logger.info(f"Log directory: {self.log_dir}")
        
        return config_info


def setup_production_logging() -> Dict[str, Any]:
    """Setup production logging configuration."""
    config = ProductionLoggingConfig()
    return config.configure_all()


def get_access_logger() -> logging.Logger:
    """Get the access logger for API request logging."""
    return logging.getLogger("access")


# Custom log filters
class HealthCheckFilter(logging.Filter):
    """Filter to exclude health check requests from access logs."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out health check requests."""
        if hasattr(record, 'pathname'):
            return '/health' not in record.pathname
        return True


class SensitiveDataFilter(logging.Filter):
    """Filter to remove sensitive data from logs."""
    
    SENSITIVE_PATTERNS = [
        'token',
        'password',
        'api_key',
        'secret',
        'authorization'
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Remove sensitive data from log messages."""
        if hasattr(record, 'msg'):
            msg = str(record.msg).lower()
            for pattern in self.SENSITIVE_PATTERNS:
                if pattern in msg:
                    record.msg = record.msg.replace(
                        record.msg[msg.find(pattern):msg.find(pattern) + 20],
                        f"{pattern}=***REDACTED***"
                    )
        return True


# Context manager for structured logging
class LogContext:
    """Context manager for adding structured context to logs."""
    
    def __init__(self, **context):
        self.context = context
        self.old_factory = logging.getLogRecordFactory()
    
    def __enter__(self):
        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            for key, value in self.context.items():
                setattr(record, key, value)
            return record
        
        logging.setLogRecordFactory(record_factory)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.setLogRecordFactory(self.old_factory)