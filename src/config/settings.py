"""
Configuration settings for the IELTS Telegram Bot.
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""
    
    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    # OpenAI/OpenRouter Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "meta-llama/llama-3.1-8b-instruct:free")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    OPENROUTER_SITE_URL: str = os.getenv("OPENROUTER_SITE_URL", "https://ielts-telegram-bot.local")
    OPENROUTER_SITE_NAME: str = os.getenv("OPENROUTER_SITE_NAME", "IELTS Writing Bot")
    
    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/ielts_bot.db")
    
    # Application Configuration
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Rate Limiting Configuration
    DAILY_SUBMISSION_LIMIT: int = int(os.getenv("DAILY_SUBMISSION_LIMIT", "3"))
    PRO_DAILY_LIMIT: int = int(os.getenv("PRO_DAILY_LIMIT", "50"))
    
    # API Configuration
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    
    # MongoDB Configuration
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017/ielts_analytics")
    
    @classmethod
    def validate_required_settings(cls) -> None:
        """Validate that all required settings are present."""
        required_settings = [
            ("TELEGRAM_BOT_TOKEN", cls.TELEGRAM_BOT_TOKEN),
            ("OPENAI_API_KEY", cls.OPENAI_API_KEY),
        ]
        
        missing_settings = []
        for setting_name, setting_value in required_settings:
            if not setting_value:
                missing_settings.append(setting_name)
        
        if missing_settings:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_settings)}"
            )


# Global settings instance
settings = Settings()