"""
Database initialization and migration utilities.
"""
import asyncio
import logging
import time
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, TimeoutError as SQLTimeoutError
from src.database.base import get_engine, init_database, Base

# Import all models to ensure they're registered with Base.metadata
from src.models import User, Submission, Assessment, RateLimit

logger = logging.getLogger(__name__)


class DatabaseConnectionError(Exception):
    """Raised when database connection fails after retries."""
    pass


class DatabaseMigrationError(Exception):
    """Raised when database migration fails."""
    pass


async def create_tables():
    """
    Create all PostgreSQL database tables with connection retry logic.
    """
    try:
        logger.info("Creating PostgreSQL database tables...")
        
        # Ensure database is ready before creating tables
        if not await wait_for_database():
            raise DatabaseConnectionError("Database not ready for table creation")
        
        # Use a more careful approach for table creation to avoid enum conflicts
        engine = get_engine()
        
        # First check existing tables without a transaction
        existing_tables = await get_table_info()
        expected_tables = {"users", "submissions", "assessments", "rate_limits"}
        
        if expected_tables.issubset(set(existing_tables)):
            logger.info("All expected tables already exist, skipping table creation")
            return
        
        # Try to create tables in a transaction
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                logger.info("✓ Database tables created successfully")
        except Exception as table_error:
            # If creation fails due to database object conflicts, handle them in a new transaction
            if "duplicate key value violates unique constraint" in str(table_error):
                logger.warning(f"Database constraint conflict detected: {table_error}")
                
                # Determine conflict type and handle in a separate transaction
                if "typname" in str(table_error):
                    await _handle_database_conflicts_separate_tx(conflict_type="enum")
                elif "relname" in str(table_error):
                    await _handle_database_conflicts_separate_tx(conflict_type="objects")
                else:
                    await _handle_database_conflicts_separate_tx(conflict_type="all")
                
                # Retry table creation in a new transaction
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                    logger.info("✓ Database tables created successfully after resolving conflicts")
            else:
                raise table_error
                    
    except DatabaseConnectionError:
        raise
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise DatabaseMigrationError(f"Table creation failed: {e}")


async def _handle_database_conflicts_separate_tx(conflict_type="all"):
    """Handle PostgreSQL database object conflicts in a separate transaction."""
    try:
        logger.info(f"Resolving database conflicts in separate transaction (type: {conflict_type})...")
        engine = get_engine()
        
        if conflict_type in ["enum", "all"]:
            # Handle enum type conflicts
            enum_types = ['tasktype', 'processingstatus']
            
            async with engine.begin() as conn:
                for enum_type in enum_types:
                    try:
                        # Check if enum type exists
                        result = await conn.execute(text("""
                            SELECT EXISTS (
                                SELECT 1 FROM pg_type 
                                WHERE typname = :enum_name AND typtype = 'e'
                            )
                        """), {"enum_name": enum_type})
                        
                        if result.scalar():
                            logger.info(f"Dropping existing enum type: {enum_type}")
                            await conn.execute(text(f"DROP TYPE IF EXISTS {enum_type} CASCADE"))
                            
                    except Exception as e:
                        logger.warning(f"Could not handle enum type {enum_type}: {e}")
        
        if conflict_type in ["objects", "all"]:
            # Handle table and sequence conflicts
            table_names = ['users', 'submissions', 'assessments', 'rate_limits']
            
            async with engine.begin() as conn:
                for table_name in table_names:
                    try:
                        # Drop sequences that might conflict
                        sequence_name = f"{table_name}_id_seq"
                        await conn.execute(text(f"DROP SEQUENCE IF EXISTS {sequence_name} CASCADE"))
                        logger.info(f"Dropped sequence: {sequence_name}")
                        
                        # Drop table if it exists (this will also drop dependent objects)
                        await conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
                        logger.info(f"Dropped table: {table_name}")
                        
                    except Exception as e:
                        logger.warning(f"Could not handle table/sequence {table_name}: {e}")
                
                # Also handle any remaining indexes that might conflict
                try:
                    # Get and drop any remaining indexes that might conflict
                    result = await conn.execute(text("""
                        SELECT indexname FROM pg_indexes 
                        WHERE schemaname = 'public' 
                        AND tablename IN ('users', 'submissions', 'assessments', 'rate_limits')
                    """))
                    indexes = result.fetchall()
                    
                    for (index_name,) in indexes:
                        try:
                            await conn.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
                            logger.info(f"Dropped index: {index_name}")
                        except Exception as e:
                            logger.warning(f"Could not drop index {index_name}: {e}")
                            
                except Exception as e:
                    logger.warning(f"Could not query/drop indexes: {e}")
                
        logger.info("Database conflict resolution completed")
    except Exception as e:
        logger.error(f"Error handling database conflicts: {e}")
        raise


async def drop_tables():
    """
    Drop all PostgreSQL database tables including migration tracking. Use with caution!
    """
    try:
        logger.warning("Dropping all PostgreSQL database tables...")
        
        # Ensure database is ready
        if not await wait_for_database():
            raise DatabaseConnectionError("Database not ready for table dropping")
            
        engine = get_engine()
        async with engine.begin() as conn:
            # First, drop all tables in the correct order (reverse dependency)
            tables_to_drop = ["assessments", "submissions", "rate_limits", "users", "schema_migrations"]
            
            for table in tables_to_drop:
                try:
                    await conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                    logger.info(f"Dropped table: {table}")
                except Exception as e:
                    logger.warning(f"Could not drop table {table}: {e}")
            
            # Drop any remaining sequences
            sequences_to_drop = ["users_id_seq", "submissions_id_seq", "assessments_id_seq", "rate_limits_id_seq"]
            for sequence in sequences_to_drop:
                try:
                    await conn.execute(text(f"DROP SEQUENCE IF EXISTS {sequence} CASCADE"))
                    logger.info(f"Dropped sequence: {sequence}")
                except Exception as e:
                    logger.warning(f"Could not drop sequence {sequence}: {e}")
            
            # Drop any enum types
            enum_types = ['tasktype', 'processingstatus']
            for enum_type in enum_types:
                try:
                    await conn.execute(text(f"DROP TYPE IF EXISTS {enum_type} CASCADE"))
                    logger.info(f"Dropped enum type: {enum_type}")
                except Exception as e:
                    logger.warning(f"Could not drop enum type {enum_type}: {e}")
            
            # Use SQLAlchemy's metadata drop as a final cleanup
            try:
                await conn.run_sync(Base.metadata.drop_all)
            except Exception as e:
                logger.warning(f"SQLAlchemy metadata drop failed (may be expected): {e}")
            
        logger.info("✓ All database tables and objects dropped successfully")
    except DatabaseConnectionError:
        raise
    except Exception as e:
        logger.error(f"Error dropping database tables: {e}")
        raise DatabaseMigrationError(f"Table dropping failed: {e}")


async def clean_database_completely():
    """
    Completely clean the database by dropping all user-created objects.
    This is more thorough than just dropping tables.
    """
    try:
        logger.info("Performing complete database cleanup...")
        engine = get_engine()
        async with engine.begin() as conn:
            # Drop all tables in public schema
            result = await conn.execute(text("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public'
            """))
            tables = result.fetchall()
            
            for (table_name,) in tables:
                try:
                    await conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
                    logger.info(f"Dropped table: {table_name}")
                except Exception as e:
                    logger.warning(f"Could not drop table {table_name}: {e}")
            
            # Drop all sequences in public schema
            result = await conn.execute(text("""
                SELECT sequence_name FROM information_schema.sequences 
                WHERE sequence_schema = 'public'
            """))
            sequences = result.fetchall()
            
            for (sequence_name,) in sequences:
                try:
                    await conn.execute(text(f"DROP SEQUENCE IF EXISTS {sequence_name} CASCADE"))
                    logger.info(f"Dropped sequence: {sequence_name}")
                except Exception as e:
                    logger.warning(f"Could not drop sequence {sequence_name}: {e}")
            
            # Drop all custom types in public schema
            result = await conn.execute(text("""
                SELECT typname FROM pg_type 
                WHERE typnamespace = (
                    SELECT oid FROM pg_namespace WHERE nspname = 'public'
                ) AND typtype = 'e'
            """))
            types = result.fetchall()
            
            for (type_name,) in types:
                try:
                    await conn.execute(text(f"DROP TYPE IF EXISTS {type_name} CASCADE"))
                    logger.info(f"Dropped type: {type_name}")
                except Exception as e:
                    logger.warning(f"Could not drop type {type_name}: {e}")
            
            # Drop all functions in public schema (user-defined)
            result = await conn.execute(text("""
                SELECT proname, oidvectortypes(proargtypes) as argtypes
                FROM pg_proc 
                WHERE pronamespace = (
                    SELECT oid FROM pg_namespace WHERE nspname = 'public'
                )
            """))
            functions = result.fetchall()
            
            for (func_name, arg_types) in functions:
                try:
                    await conn.execute(text(f"DROP FUNCTION IF EXISTS {func_name}({arg_types}) CASCADE"))
                    logger.info(f"Dropped function: {func_name}")
                except Exception as e:
                    logger.warning(f"Could not drop function {func_name}: {e}")
                    
        logger.info("✓ Complete database cleanup finished")
    except Exception as e:
        logger.error(f"Error during complete database cleanup: {e}")
        raise


async def reset_database():
    """
    Reset PostgreSQL database by completely cleaning and recreating all tables.
    This will also reset migration tracking.
    """
    try:
        logger.warning("Resetting PostgreSQL database (complete cleanup)...")
        await clean_database_completely()
        await create_tables()
        logger.info("✓ Database reset completed")
    except Exception as e:
        logger.error(f"Database reset failed: {e}")
        raise DatabaseMigrationError(f"Database reset failed: {e}")


async def check_database_connection() -> bool:
    """
    Check if PostgreSQL database connection is working.
    
    Returns:
        bool: True if connection is successful, False otherwise
    """
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            # Use PostgreSQL-specific query to verify connection
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            if version and "PostgreSQL" in version:
                logger.debug("PostgreSQL connection verified")
                return True
            else:
                logger.warning("Connected but not to PostgreSQL database")
                return False
    except (OperationalError, SQLTimeoutError, ConnectionError) as e:
        logger.debug(f"Database connection check failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during database connection check: {e}")
        return False


async def wait_for_database(max_retries: int = 30, initial_delay: float = 2.0, max_delay: float = 30.0) -> bool:
    """
    Wait for PostgreSQL database to be ready with exponential backoff retry logic.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 30)
        initial_delay: Initial delay between retries in seconds (default: 2.0)
        max_delay: Maximum delay between retries in seconds (default: 30.0)
        
    Returns:
        bool: True if database is ready, False if max retries exceeded
        
    Raises:
        DatabaseConnectionError: If database is not ready after max retries
    """
    delay = initial_delay
    start_time = time.time()
    
    logger.info(f"Waiting for PostgreSQL database to be ready (max {max_retries} attempts)...")
    
    for attempt in range(max_retries):
        try:
            logger.debug(f"Database connection attempt {attempt + 1}/{max_retries}")
            
            if await check_database_connection():
                elapsed_time = time.time() - start_time
                logger.info(f"✓ PostgreSQL database ready after {attempt + 1} attempts ({elapsed_time:.1f}s)")
                return True
                
        except Exception as e:
            logger.warning(f"Database readiness check failed on attempt {attempt + 1}: {e}")
        
        if attempt < max_retries - 1:  # Don't sleep on the last attempt
            logger.info(f"Database not ready, retrying in {delay:.1f} seconds...")
            await asyncio.sleep(delay)
            
            # Exponential backoff with jitter to avoid thundering herd
            jitter = delay * 0.1 * (0.5 - asyncio.get_event_loop().time() % 1)
            delay = min(delay * 1.5 + jitter, max_delay)
    
    elapsed_time = time.time() - start_time
    error_msg = f"PostgreSQL database not ready after {max_retries} attempts ({elapsed_time:.1f}s)"
    logger.error(error_msg)
    raise DatabaseConnectionError(error_msg)


async def get_table_info():
    """
    Get information about existing PostgreSQL tables.
    
    Returns:
        list: List of table names in the current database
    """
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            # For PostgreSQL, query information_schema
            result = await conn.execute(
                text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
            )
            tables = result.fetchall()
            return [table[0] for table in tables]
    except Exception as e:
        logger.error(f"Error getting PostgreSQL table info: {e}")
        return []


async def create_migration_table():
    """Create the schema_migrations table for tracking migration versions."""
    try:
        engine = get_engine()
        
        # First, check if the table already exists without a transaction
        async with engine.begin() as conn:
            table_exists = await conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'schema_migrations'
                )
            """))
            exists = table_exists.scalar()
        
        if exists:
            logger.debug("Schema migrations table already exists")
            return
        
        # If table doesn't exist, try to create it
        try:
            async with engine.begin() as conn:
                await conn.execute(text("""
                    CREATE TABLE schema_migrations (
                        version VARCHAR(255) PRIMARY KEY,
                        applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        description TEXT NOT NULL,
                        success BOOLEAN DEFAULT TRUE
                    )
                """))
                logger.debug("Schema migrations table created")
        except Exception as create_error:
            # If creation fails due to type conflicts, clean up in a separate transaction and retry
            if "duplicate key value violates unique constraint" in str(create_error) and "typname" in str(create_error):
                logger.warning("Type conflict detected while creating schema_migrations table, cleaning up...")
                
                # Clean up any conflicting database objects in a separate transaction
                async with engine.begin() as conn:
                    try:
                        # Drop any sequences or types that might conflict
                        await conn.execute(text("DROP SEQUENCE IF EXISTS schema_migrations_id_seq CASCADE"))
                        await conn.execute(text("DROP TYPE IF EXISTS schema_migrations CASCADE"))
                        logger.debug("Cleaned up conflicting objects for schema_migrations table")
                    except Exception as cleanup_error:
                        logger.warning(f"Could not clean up conflicting objects: {cleanup_error}")
                
                # Try to create the table again in a new transaction
                async with engine.begin() as conn:
                    await conn.execute(text("""
                        CREATE TABLE schema_migrations (
                            version VARCHAR(255) PRIMARY KEY,
                            applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                            description TEXT NOT NULL,
                            success BOOLEAN DEFAULT TRUE
                        )
                    """))
                    logger.debug("Schema migrations table created after cleanup")
            else:
                raise create_error
                    
    except Exception as e:
        logger.error(f"Error creating migration table: {e}")
        raise


async def get_current_migration_version() -> Optional[str]:
    """
    Get the current migration version from the database.
    
    Returns:
        str: Current migration version or None if no migrations applied
    """
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT version FROM schema_migrations 
                WHERE success = TRUE
                ORDER BY applied_at DESC 
                LIMIT 1
            """))
            row = result.fetchone()
            return row[0] if row else None
    except Exception as e:
        logger.debug(f"Could not get migration version (table may not exist): {e}")
        return None


async def get_applied_migrations() -> list:
    """
    Get all successfully applied migrations.
    
    Returns:
        list: List of applied migration versions
    """
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT version FROM schema_migrations 
                WHERE success = TRUE
                ORDER BY applied_at ASC
            """))
            rows = result.fetchall()
            return [row[0] for row in rows]
    except Exception as e:
        logger.debug(f"Could not get applied migrations: {e}")
        return []


async def is_migration_applied(version: str) -> bool:
    """
    Check if a specific migration has been applied successfully.
    
    Args:
        version: Migration version to check
        
    Returns:
        bool: True if migration is applied, False otherwise
    """
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT COUNT(*) FROM schema_migrations 
                WHERE version = :version AND success = TRUE
            """), {"version": version})
            count = result.scalar()
            return count > 0
    except Exception as e:
        logger.debug(f"Could not check migration status for {version}: {e}")
        return False


async def record_migration(version: str, description: str, success: bool = True):
    """Record a migration attempt in the schema_migrations table."""
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("""
                INSERT INTO schema_migrations (version, description, success)
                VALUES (:version, :description, :success)
                ON CONFLICT (version) DO UPDATE SET
                    description = EXCLUDED.description,
                    success = EXCLUDED.success,
                    applied_at = CURRENT_TIMESTAMP
            """), {"version": version, "description": description, "success": success})
            
            status = "successfully" if success else "with failure"
            logger.info(f"Recorded migration {status}: {version} - {description}")
    except Exception as e:
        logger.error(f"Error recording migration {version}: {e}")
        raise


async def rollback_migration(version: str):
    """
    Mark a migration as rolled back (for rollback scenarios).
    
    Args:
        version: Migration version to rollback
    """
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            # Mark migration as unsuccessful instead of deleting
            result = await conn.execute(text("""
                UPDATE schema_migrations 
                SET success = FALSE, applied_at = CURRENT_TIMESTAMP
                WHERE version = :version
            """), {"version": version})
            
            if result.rowcount > 0:
                logger.info(f"Marked migration as rolled back: {version}")
            else:
                logger.warning(f"Migration {version} was not found for rollback")
    except Exception as e:
        logger.error(f"Error rolling back migration {version}: {e}")
        raise


async def execute_migration_with_rollback(version: str, description: str, migration_func, rollback_func=None):
    """Execute a migration with automatic rollback on failure."""
    try:
        logger.info(f"Executing migration {version}: {description}")
        
        # Check if migration is already applied
        if await is_migration_applied(version):
            logger.info(f"Migration {version} already applied, skipping")
            return True
        
        # Execute the migration
        await migration_func()
        
        # Record successful migration
        await record_migration(version, description, True)
        logger.info(f"✓ Migration {version} completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Migration {version} failed: {e}")
        
        try:
            # Record failed migration
            await record_migration(version, description, False)
            
            # Execute rollback if provided
            if rollback_func:
                logger.info(f"Executing rollback for migration {version}")
                await rollback_func()
                logger.info(f"Rollback completed for migration {version}")
            
        except Exception as rollback_error:
            logger.error(f"Rollback failed for migration {version}: {rollback_error}")
        
        return False


# Migration definitions
MIGRATIONS = [
    {
        "version": "001_initial_schema",
        "description": "Initial schema creation with users, submissions, assessments, and rate_limits tables",
        "migration_func": "migrate_001_initial_schema",
        "rollback_func": "rollback_001_initial_schema"
    }
]


async def migrate_001_initial_schema():
    """Migration 001: Create initial database schema."""
    logger.info("Creating initial database tables...")
    
    # Check existing tables
    existing_tables = await get_table_info()
    expected_tables = {"users", "submissions", "assessments", "rate_limits"}
    
    if expected_tables.issubset(set(existing_tables)):
        logger.info("Initial tables already exist, verifying schema consistency")
        # Tables exist, but let's verify they have the correct structure
        # by attempting a simple query on each table
        engine = get_engine()
        async with engine.begin() as conn:
            for table in expected_tables:
                try:
                    await conn.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
                except Exception as e:
                    logger.warning(f"Table {table} exists but may have schema issues: {e}")
        return
    
    logger.info("Creating missing database tables...")
    await create_tables()


async def rollback_001_initial_schema():
    """Rollback 001: Drop initial database schema."""
    logger.warning("Rolling back initial schema creation...")
    
    engine = get_engine()
    async with engine.begin() as conn:
        # Drop tables in reverse dependency order
        tables_to_drop = ["assessments", "submissions", "rate_limits", "users"]
        
        for table in tables_to_drop:
            try:
                await conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                logger.info(f"Dropped table: {table}")
            except Exception as e:
                logger.warning(f"Could not drop table {table}: {e}")
        
        # Drop sequences that might remain
        sequences_to_drop = ["users_id_seq", "submissions_id_seq", "assessments_id_seq", "rate_limits_id_seq"]
        for sequence in sequences_to_drop:
            try:
                await conn.execute(text(f"DROP SEQUENCE IF EXISTS {sequence} CASCADE"))
                logger.info(f"Dropped sequence: {sequence}")
            except Exception as e:
                logger.warning(f"Could not drop sequence {sequence}: {e}")
        
        # Drop enum types
        enum_types = ['tasktype', 'processingstatus']
        for enum_type in enum_types:
            try:
                await conn.execute(text(f"DROP TYPE IF EXISTS {enum_type} CASCADE"))
                logger.info(f"Dropped enum type: {enum_type}")
            except Exception as e:
                logger.warning(f"Could not drop enum type {enum_type}: {e}")


async def get_pending_migrations() -> list:
    """Get list of pending migrations that need to be applied."""
    applied_migrations = await get_applied_migrations()
    return [m for m in MIGRATIONS if m["version"] not in applied_migrations]


async def migrate_database():
    """
    Run PostgreSQL database migrations with version tracking and idempotent logic.
    
    Raises:
        DatabaseMigrationError: If migration fails
    """
    try:
        logger.info("Starting PostgreSQL database migration...")
        
        # Ensure database is ready
        if not await wait_for_database():
            raise DatabaseMigrationError("Database not ready for migration")
        
        # Create migration tracking table with robust error handling
        try:
            await create_migration_table()
        except Exception as migration_table_error:
            # If migration table creation fails due to conflicts, try complete cleanup
            if "duplicate key value violates unique constraint" in str(migration_table_error):
                logger.warning("Migration table creation failed due to conflicts, attempting complete database cleanup...")
                await clean_database_completely()
                # Retry migration table creation
                await create_migration_table()
            else:
                raise migration_table_error
        
        # Get current migration state
        current_version = await get_current_migration_version()
        logger.info(f"Current migration version: {current_version or 'none'}")
        
        # Get pending migrations
        pending_migrations = await get_pending_migrations()
        
        if not pending_migrations:
            logger.info("No pending migrations to apply")
        else:
            logger.info(f"Found {len(pending_migrations)} pending migrations")
            
            # Apply each pending migration
            for migration in pending_migrations:
                version = migration["version"]
                description = migration["description"]
                migration_func_name = migration["migration_func"]
                rollback_func_name = migration.get("rollback_func")
                
                # Get migration function
                migration_func = globals().get(migration_func_name)
                if not migration_func:
                    raise DatabaseMigrationError(f"Migration function {migration_func_name} not found")
                
                # Get rollback function if specified
                rollback_func = None
                if rollback_func_name:
                    rollback_func = globals().get(rollback_func_name)
                
                # Execute migration with rollback capability
                success = await execute_migration_with_rollback(
                    version, description, migration_func, rollback_func
                )
                
                if not success:
                    raise DatabaseMigrationError(f"Migration {version} failed")
        
        # Verify final state
        final_tables = await get_table_info()
        expected_tables = {"users", "submissions", "assessments", "rate_limits", "schema_migrations"}
        missing_tables = expected_tables - set(final_tables)
        
        if missing_tables:
            raise DatabaseMigrationError(f"Migration completed but missing tables: {missing_tables}")
        
        logger.info("✓ Database migration completed successfully")
        logger.info(f"Available tables: {sorted(final_tables)}")
        
    except DatabaseMigrationError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during database migration: {e}")
        raise DatabaseMigrationError(f"Migration failed: {e}")





if __name__ == "__main__":
    # Allow running this script directly for database setup
    async def main():
        import sys
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        

        
        # Default behavior: run migrations
        try:
            print("🔄 Waiting for PostgreSQL database to be ready...")
            await wait_for_database()
            print("✓ Database connection established")
            
            print("\n🔄 Running database migrations...")
            await migrate_database()
            print("✓ Database migrations completed")
            
            print("\n📋 Current database tables:")
            tables = await get_table_info()
            for table in sorted(tables):
                print(f"  - {table}")
            
            print("\n📊 Migration Status:")
            applied = await get_applied_migrations()
            current = await get_current_migration_version()
            print(f"Applied migrations: {len(applied)}")
            print(f"Current version: {current or 'none'}")
                
            print(f"\n✅ Database setup completed successfully!")
            
        except DatabaseConnectionError as e:
            print(f"❌ Database connection failed: {e}")
            return 1
        except DatabaseMigrationError as e:
            print(f"❌ Database migration failed: {e}")
            return 1
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            logger.exception("Unexpected error during database setup")
            return 1
        
        return 0
    
    import sys
    sys.exit(asyncio.run(main()))