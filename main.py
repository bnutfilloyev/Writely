"""
Main entry point for the IELTS Telegram Bot.
"""
import asyncio
import logging
import signal
import sys
import os
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import uvicorn

from src.config.settings import settings
from src.config.logging_config import setup_production_logging, get_access_logger
from src.database.base import get_db_session, init_database, close_database
from src.database.init import migrate_database, check_database_connection
from src.handlers import start_handler, submission_handler, history_handler, callback_handler
from src.middleware.logging_middleware import LoggingMiddleware
from src.middleware.error_middleware import ErrorMiddleware
from src.middleware.database_middleware import DatabaseMiddleware


def setup_logging():
    """Configure logging for the application."""
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
    dispatcher.message.middleware(DatabaseMiddleware())
    dispatcher.callback_query.middleware(DatabaseMiddleware())
    dispatcher.message.middleware(LoggingMiddleware())
    dispatcher.callback_query.middleware(LoggingMiddleware())
    dispatcher.message.middleware(ErrorMiddleware())
    dispatcher.callback_query.middleware(ErrorMiddleware())
    
    # Register handlers
    dispatcher.include_router(start_handler.router)
    dispatcher.include_router(callback_handler.router)
    dispatcher.include_router(submission_handler.router)
    dispatcher.include_router(history_handler.router)
    
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
    """Initialize and migrate database."""
    logger = logging.getLogger(__name__)
    
    logger.info("Checking database connection...")
    if not await check_database_connection():
        raise RuntimeError("Database connection failed")
    
    logger.info("Running database migrations...")
    await migrate_database()
    logger.info("Database setup completed")


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
                         "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                         f"🤖 *Bot:* @{bot_info.username}\n"
                         f"✅ *Status:* Online & Ready\n"
                         f"🕐 *Started:* `{time.strftime('%Y-%m-%d %H:%M:%S')}`\n"
                         f"👨‍💼 *Admin:* @bnutfilloyev\n"
                         "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
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
    
    logger.info("Closing database connections...")
    try:
        await close_database()
    except Exception as e:
        logger.error(f"Error closing database: {e}")
    
    logger.info("Bot stopped gracefully")


# FastAPI app for health checks and webhooks
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan context manager."""
    # Startup
    await setup_database()
    yield
    # Shutdown
    await close_database()


app = FastAPI(
    title="IELTS Telegram Bot API",
    description="Health check and webhook endpoints for IELTS Telegram Bot",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check(session: AsyncSession = Depends(get_db_session)):
    """Health check endpoint for deployment monitoring."""
    from sqlalchemy import text
    
    try:
        # Check database connection
        await session.execute(text("SELECT 1"))
        
        # Check bot connection if available
        bot_status = "unknown"
        if bot:
            try:
                await bot.get_me()
                bot_status = "connected"
            except Exception:
                bot_status = "disconnected"
        
        return {
            "status": "healthy",
            "database": "connected",
            "bot": bot_status,
            "version": "1.0.0"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "database": "disconnected",
            "bot": "unknown",
            "version": "1.0.0"
        }


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "IELTS Telegram Bot API is running"}


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


async def run_with_api():
    """Run bot with FastAPI server for health checks."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Validate configuration
        settings.validate_required_settings()
        logger.info("Configuration validated successfully")
        
        # Start bot in background
        bot_task = asyncio.create_task(run_bot_only())
        
        # Start FastAPI server
        config = uvicorn.Config(
            app,
            host=settings.API_HOST,
            port=settings.API_PORT,
            log_level=settings.LOG_LEVEL.lower()
        )
        server = uvicorn.Server(config)
        
        logger.info(f"Starting API server on {settings.API_HOST}:{settings.API_PORT}")
        await server.serve()
        
    except Exception as e:
        logger.error(f"Error running with API: {e}")
        raise


async def main():
    """Main application entry point."""
    # Run bot only by default, API server can be enabled via environment variable
    if settings.DEBUG or os.getenv("ENABLE_API", "false").lower() == "true":
        await run_with_api()
    else:
        await run_bot_only()


if __name__ == "__main__":
    import os
    asyncio.run(main())