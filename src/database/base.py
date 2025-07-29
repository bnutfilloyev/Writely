"""
Database base configuration and connection utilities.
"""
import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import MetaData
from typing import AsyncGenerator

# Create declarative base for models
Base = declarative_base()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./ielts_bot.db")

# Global variables for engine and session factory
engine = None
AsyncSessionLocal = None


def get_engine():
    """Get or create the database engine."""
    global engine
    if engine is None:
        engine = create_async_engine(
            DATABASE_URL,
            echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
            future=True
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


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function to get database session.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_database():
    """
    Initialize database by creating all tables.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_database():
    """
    Close database connections.
    """
    engine = get_engine()
    await engine.dispose()