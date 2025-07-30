"""
Main entry point for the IELTS Telegram Bot.
"""
import asyncio
import logging
import signal
import sys
import os
import time
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand


from src.config.settings import settings
from src.config.logging_config import setup_production_logging, get_access_logger
from src.handlers import start_router, submission_router, callback_router
from src.middleware.logging_middleware import LoggingMiddleware
from src.middleware.error_middleware import ErrorMiddleware
from src.middleware.analytics_middleware import AnalyticsMiddleware
from src.services.analytics_service import analytics_service


def setup_logging():
    """Configure logging for the application."""
    try:
        if settings.DEBUG:
            # Simple logging for development
            logging.basicConfig(
                level=getattr(logging, settings.LOG_LEVEL.upper()),
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[logging.StreamHandler(sys.stdout)]
            )
        else:
            # Production logging with file rotation
            setup_production_logging()
    except Exception as e:
        # Fallback to basic console logging if production logging fails
        print(f"Warning: Production logging setup failed ({e}). Using basic console logging.")
        logging.basicConfig(
            level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )


# Global bot and dispatcher instances
bot: Bot = None
dp: Dispatcher = None


def create_bot() -> Bot:
    """Create and configure the bot instance."""
    return Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )


def create_dispatcher() -> Dispatcher:
    """Create and configure the dispatcher with middleware and handlers."""
    # Create dispatcher with memory storage for FSM
    dispatcher = Dispatcher(storage=MemoryStorage())
    
    # Register middleware in order of execution
    dispatcher.message.middleware(LoggingMiddleware())
    dispatcher.callback_query.middleware(LoggingMiddleware())
    dispatcher.message.middleware(AnalyticsMiddleware())
    dispatcher.callback_query.middleware(AnalyticsMiddleware())
    dispatcher.message.middleware(ErrorMiddleware())
    dispatcher.callback_query.middleware(ErrorMiddleware())
    
    # Register handlers
    dispatcher.include_router(start_router)
    dispatcher.include_router(callback_router)
    dispatcher.include_router(submission_router)
    
    return dispatcher


async def setup_bot_commands(bot: Bot):
    """Set up bot commands for the menu."""
    commands = [
        BotCommand(command="start", description="🚀 Start using Writely robot"),
        BotCommand(command="help", description="❓ Get help and instructions"),
        BotCommand(command="task1", description="📊 Submit IELTS Writing Task 1"),
        BotCommand(command="task2", description="📝 Submit IELTS Writing Task 2"),
        BotCommand(command="history", description="📈 View your evaluation history"),
        BotCommand(command="about", description="ℹ️ About Writely robot"),
    ]
    
    await bot.set_my_commands(commands)
    logger = logging.getLogger(__name__)
    logger.info("Bot commands set up successfully")


async def setup_database():
    """Setup MongoDB connection for analytics."""
    logger = logging.getLogger(__name__)
    try:
        await analytics_service.connect()
        logger.info("MongoDB analytics service initialized")
    except Exception as e:
        logger.warning(f"MongoDB connection failed, analytics disabled: {e}")


async def start_bot():
    """Start the bot with proper initialization."""
    global bot, dp
    logger = logging.getLogger(__name__)
    
    try:
        # Create bot and dispatcher
        bot = create_bot()
        dp = create_dispatcher()
        
        # Setup database
        await setup_database()
        
        # Get bot info
        bot_info = await bot.get_me()
        logger.info(f"Bot started: @{bot_info.username} ({bot_info.first_name})")
        
        # Set up bot commands
        await setup_bot_commands(bot)
        
        # Send startup message to admin (if ADMIN_ID is set)
        admin_id = os.getenv("ADMIN_ID")
        if admin_id:
            try:
                await bot.send_message(
                    chat_id=int(admin_id),
                    text="🤖✨ *Writely Robot is Online!* ✨🤖\n\n"
                         f"🤖 *Bot:* @{bot_info.username}\n"
                         f"✅ *Status:* Online & Ready\n"
                         f"🕐 *Started:* `{time.strftime('%Y-%m-%d %H:%M:%S')}`\n"
                         f"👨‍💼 *Admin:* @bnutfilloyev\n\n"
                         "🎯 *Ready to help users improve their IELTS writing!*\n"
                         "📝 *Features:* Task 1 & 2 Evaluation\n"
                         "🧠 *AI Model:* Llama 3.1 8B (Free)\n"
                         "🌟 *Status:* All systems operational!",
                    parse_mode="Markdown"
                )
                logger.info(f"Startup notification sent to admin: {admin_id}")
            except Exception as e:
                logger.warning(f"Failed to send startup notification to admin: {e}")
        
        # Start polling
        logger.info("Starting bot polling...")
        await dp.start_polling(bot, skip_updates=True)
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise


async def stop_bot():
    """Stop the bot gracefully."""
    global bot, dp
    logger = logging.getLogger(__name__)
    
    if dp:
        logger.info("Stopping dispatcher...")
        try:
            await dp.stop_polling()
        except RuntimeError as e:
            if "Polling is not started" in str(e):
                logger.info("Polling was already stopped")
            else:
                logger.error(f"Error stopping polling: {e}")
    
    if bot:
        logger.info("Closing bot session...")
        try:
            await bot.session.close()
        except Exception as e:
            logger.error(f"Error closing bot session: {e}")
    
    # Cleanup MongoDB connection
    try:
        await analytics_service.disconnect()
        logger.info("MongoDB analytics service disconnected")
    except Exception as e:
        logger.error(f"Error disconnecting MongoDB: {e}")
    
    logger.info("Bot stopped gracefully")







async def run_bot_only():
    """Run only the bot without FastAPI server."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Validate configuration
        settings.validate_required_settings()
        logger.info("Configuration validated successfully")
        
        logger.info("IELTS Telegram Bot starting...")
        logger.info(f"Debug mode: {settings.DEBUG}")
        logger.info(f"Daily submission limit: {settings.DAILY_SUBMISSION_LIMIT}")
        
        # Start bot
        await start_bot()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Unexpected error during startup: {e}")
        raise
    finally:
        await stop_bot()


async def main():
    """Main application entry point."""
    await run_bot_only()


if __name__ == "__main__":
    import os
    asyncio.run(main())