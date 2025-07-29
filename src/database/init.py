"""
Database initialization and migration utilities.
"""
import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.database.base import get_engine, init_database, Base

logger = logging.getLogger(__name__)


async def create_tables():
    """
    Create all database tables.
    """
    try:
        logger.info("Creating database tables...")
        await init_database()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise


async def drop_tables():
    """
    Drop all database tables. Use with caution!
    """
    try:
        logger.warning("Dropping all database tables...")
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("Database tables dropped successfully")
    except Exception as e:
        logger.error(f"Error dropping database tables: {e}")
        raise


async def reset_database():
    """
    Reset database by dropping and recreating all tables.
    """
    await drop_tables()
    await create_tables()


async def check_database_connection():
    """
    Check if database connection is working.
    """
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.fetchone()  # Don't await this, it's synchronous
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


async def get_table_info():
    """
    Get information about existing tables.
    """
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            # For SQLite, query sqlite_master table
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            )
            tables = result.fetchall()  # Don't await this, it's synchronous
            return [table[0] for table in tables]
    except Exception as e:
        logger.error(f"Error getting table info: {e}")
        return []


async def migrate_database():
    """
    Run database migrations. Currently just creates tables if they don't exist.
    In the future, this could be extended with proper migration logic.
    """
    try:
        logger.info("Running database migrations...")
        
        # Check if tables exist
        tables = await get_table_info()
        expected_tables = {"users", "submissions", "assessments", "rate_limits"}
        
        if not expected_tables.issubset(set(tables)):
            logger.info("Creating missing tables...")
            await create_tables()
        else:
            logger.info("All tables exist, no migration needed")
            
        logger.info("Database migration completed")
    except Exception as e:
        logger.error(f"Error during database migration: {e}")
        raise


if __name__ == "__main__":
    # Allow running this script directly for database setup
    async def main():
        logging.basicConfig(level=logging.INFO)
        
        print("Checking database connection...")
        if await check_database_connection():
            print("✓ Database connection successful")
        else:
            print("✗ Database connection failed")
            return
        
        print("\nRunning database migration...")
        await migrate_database()
        print("✓ Database migration completed")
        
        print("\nExisting tables:")
        tables = await get_table_info()
        for table in tables:
            print(f"  - {table}")
    
    asyncio.run(main())