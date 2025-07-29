"""
Database base configuration and connection utilities.
"""
import os
import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import MetaData, text
from typing import AsyncGenerator

# Set up logging
logger = logging.getLogger(__name__)

# Create declarative base for models
Base = declarative_base()

# Database configuration with PostgreSQL as default
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://ielts_user:password@localhost:5432/ielts_bot")

# Global variables for engine and session factory
engine = None
AsyncSessionLocal = None


def get_engine():
    """Get or create the PostgreSQL database engine with connection pooling."""
    global engine
    if engine is None:
        # PostgreSQL-specific configuration with connection pooling
        engine = create_async_engine(
            DATABASE_URL,
            echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
            future=True,
            pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
            pool_pre_ping=True,
            pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "3600")),
            pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
            connect_args={
                "server_settings": {
                    "application_name": "ielts_telegram_bot",
                }
            }
        )
    return engine


def get_session_factory():
    """Get or create the session factory."""
    global AsyncSessionLocal
    if AsyncSessionLocal is None:
        AsyncSessionLocal = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False
        )
    return AsyncSessionLocal


async def check_database_connection() -> bool:
    """
    Check if PostgreSQL database connection is healthy.
    
    Returns:
        bool: True if connection is healthy, False otherwise
    """
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        logger.error(f"PostgreSQL health check failed: {e}")
        return False


async def wait_for_database(max_retries: int = 30, initial_delay: float = 1.0) -> bool:
    """
    Wait for database to be ready with exponential backoff retry logic.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        
    Returns:
        bool: True if database is ready, False if max retries exceeded
    """
    delay = initial_delay
    
    for attempt in range(max_retries):
        try:
            if await check_database_connection():
                logger.info(f"Database connection established on attempt {attempt + 1}")
                return True
        except Exception as e:
            logger.warning(f"Database connection attempt {attempt + 1}/{max_retries} failed: {e}")
        
        if attempt < max_retries - 1:  # Don't sleep on the last attempt
            logger.info(f"Retrying database connection in {delay:.1f} seconds...")
            await asyncio.sleep(delay)
            # Exponential backoff with jitter
            delay = min(delay * 1.5, 30.0)  # Cap at 30 seconds
    
    logger.error(f"Database connection failed after {max_retries} attempts")
    return False


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function to get database session with retry logic.
    """
    session_factory = get_session_factory()
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            async with session_factory() as session:
                yield session
                return
        except Exception as e:
            logger.warning(f"Database session attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(1.0 * (attempt + 1))  # Progressive delay


async def init_database():
    """
    Initialize database by creating all tables with connection retry logic.
    """
    # Wait for database to be ready
    if not await wait_for_database():
        raise RuntimeError("Database connection failed during initialization")
    
    engine = get_engine()
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


async def close_database():
    """
    Close database connections gracefully.
    """
    global engine, AsyncSessionLocal
    
    try:
        if engine is not None:
            await engine.dispose()
            logger.info("Database connections closed successfully")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")
    finally:
        engine = None
        AsyncSessionLocal = None


async def get_database_info() -> dict:
    """
    Get PostgreSQL connection information for monitoring.
    
    Returns:
        dict: Database connection information
    """
    try:
        engine = get_engine()
        pool = engine.pool
        
        info = {
            "database_url": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL,  # Hide credentials
            "database_type": "postgresql",
            "pool_size": getattr(pool, 'size', lambda: 0)(),
            "checked_in": getattr(pool, 'checkedin', lambda: 0)(),
            "checked_out": getattr(pool, 'checkedout', lambda: 0)(),
            "overflow": getattr(pool, 'overflow', lambda: 0)(),
            "is_healthy": await check_database_connection()
        }
        
        return info
    except Exception as e:
        logger.error(f"Failed to get PostgreSQL database info: {e}")
        return {"error": str(e), "is_healthy": False}