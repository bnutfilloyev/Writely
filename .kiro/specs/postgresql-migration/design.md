# PostgreSQL Migration Design Document

## Overview

This design outlines the migration from SQLite to PostgreSQL for the IELTS Telegram Bot. The migration addresses persistent database connection issues, improves concurrent access handling, and provides a more robust production-ready database solution. The design ensures zero data loss and minimal downtime during the transition.

## Architecture

### Current Architecture
- **Database**: SQLite with aiosqlite async driver
- **Connection**: Single file-based database (`ielts_bot.db`)
- **Location**: `/app/data/ielts_bot.db` in Docker container
- **Issues**: File locking, concurrent access problems, permission issues

### Target Architecture
- **Database**: PostgreSQL 15+ with asyncpg driver
- **Connection**: Network-based database server
- **Deployment**: Docker Compose service with persistent volumes
- **Benefits**: Concurrent connections, ACID compliance, better performance

### Database Schema
The existing schema will be preserved with the following tables:
- `users` - Telegram user information and settings
- `submissions` - Writing submissions with metadata
- `assessments` - Evaluation results and feedback
- `rate_limits` - Daily submission tracking

## Components and Interfaces

### 1. Database Configuration Component

**Purpose**: Manage database connection settings and environment configuration

**Implementation**:
```python
# src/database/base.py updates
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://ielts_user:password@localhost:5432/ielts_bot")

def get_engine():
    """Get or create the database engine with PostgreSQL-specific settings."""
    global engine
    if engine is None:
        engine = create_async_engine(
            DATABASE_URL,
            echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
            future=True,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600
        )
    return engine
```

**Environment Variables**:
- `DATABASE_URL`: PostgreSQL connection string
- `POSTGRES_DB`: Database name
- `POSTGRES_USER`: Database user
- `POSTGRES_PASSWORD`: Database password
- `POSTGRES_HOST`: Database host (default: postgres)
- `POSTGRES_PORT`: Database port (default: 5432)

### 2. Docker Compose Service Component

**Purpose**: Provide PostgreSQL database service in Docker environment

**Implementation**:
```yaml
services:
  postgres:
    image: postgres:15-alpine
    container_name: ielts-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: ielts_bot
      POSTGRES_USER: ielts_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_INITDB_ARGS: "--encoding=UTF-8 --lc-collate=C --lc-ctype=C"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ielts_user -d ielts_bot"]
      interval: 10s
      timeout: 5s
      retries: 5

  ielts-bot:
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgresql+asyncpg://ielts_user:${POSTGRES_PASSWORD}@postgres:5432/ielts_bot

volumes:
  postgres_data:
```

### 3. Migration Script Component

**Purpose**: Migrate existing SQLite data to PostgreSQL

**Implementation**:
```python
# scripts/migrate_to_postgresql.py
import asyncio
import sqlite3
from sqlalchemy.ext.asyncio import create_async_engine
from src.models import User, Submission, Assessment, RateLimit

async def migrate_data():
    """Migrate data from SQLite to PostgreSQL."""
    # Connect to SQLite
    sqlite_conn = sqlite3.connect('data/ielts_bot.db')
    sqlite_conn.row_factory = sqlite3.Row
    
    # Connect to PostgreSQL
    pg_engine = create_async_engine(POSTGRES_URL)
    
    # Migrate each table
    await migrate_users(sqlite_conn, pg_engine)
    await migrate_submissions(sqlite_conn, pg_engine)
    await migrate_assessments(sqlite_conn, pg_engine)
    await migrate_rate_limits(sqlite_conn, pg_engine)
    
    # Verify data integrity
    await verify_migration(sqlite_conn, pg_engine)
```

### 4. Database Initialization Component

**Purpose**: Handle database startup, migrations, and health checks

**Implementation**:
```python
# src/database/init.py updates
async def wait_for_database(max_retries=30, delay=2):
    """Wait for database to be ready with exponential backoff."""
    for attempt in range(max_retries):
        try:
            if await check_database_connection():
                return True
        except Exception as e:
            logger.info(f"Database not ready (attempt {attempt + 1}/{max_retries}): {e}")
            await asyncio.sleep(delay * (1.5 ** attempt))
    return False

async def setup_database():
    """Initialize database with proper error handling."""
    if not await wait_for_database():
        raise RuntimeError("Database connection failed after retries")
    
    await migrate_database()
    logger.info("Database setup completed")
```

### 5. Connection Pool Management Component

**Purpose**: Optimize database connections for concurrent access

**Configuration**:
- **Pool Size**: 10 connections
- **Max Overflow**: 20 additional connections
- **Pool Recycle**: 1 hour (3600 seconds)
- **Pre-ping**: Validate connections before use
- **Timeout**: 30 seconds for connection acquisition

## Data Models

### Model Updates Required

**No schema changes needed** - existing SQLAlchemy models are compatible with PostgreSQL:

1. **User Model**: Compatible as-is
2. **Submission Model**: Enum types work with PostgreSQL
3. **Assessment Model**: JSON handling compatible
4. **RateLimit Model**: Date/DateTime types compatible

**Driver Changes**:
- Replace `sqlite+aiosqlite` with `postgresql+asyncpg`
- Update connection string format
- Add PostgreSQL-specific engine parameters

## Error Handling

### Connection Error Handling

```python
class DatabaseConnectionError(Exception):
    """Raised when database connection fails."""
    pass

class MigrationError(Exception):
    """Raised when data migration fails."""
    pass

async def robust_database_operation(operation):
    """Execute database operation with retry logic."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return await operation()
        except (ConnectionError, TimeoutError) as e:
            if attempt == max_retries - 1:
                raise DatabaseConnectionError(f"Database operation failed after {max_retries} attempts: {e}")
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

### Migration Error Handling

- **Pre-migration validation**: Check SQLite database integrity
- **Transaction safety**: Use database transactions for atomic operations
- **Rollback capability**: Ability to restore from backup if migration fails
- **Data verification**: Compare record counts and key data after migration

## Testing Strategy

### 1. Unit Tests

**Database Connection Tests**:
```python
async def test_postgresql_connection():
    """Test PostgreSQL connection establishment."""
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT version()"))
        version = result.scalar()
        assert "PostgreSQL" in version

async def test_model_operations():
    """Test CRUD operations with PostgreSQL."""
    # Test user creation, updates, queries
    # Test submission handling
    # Test assessment storage
    # Test rate limiting
```

**Migration Tests**:
```python
async def test_data_migration():
    """Test SQLite to PostgreSQL data migration."""
    # Create test SQLite database
    # Run migration
    # Verify data integrity
    # Check foreign key relationships
```

### 2. Integration Tests

**Docker Compose Tests**:
```python
async def test_docker_compose_startup():
    """Test full Docker Compose stack startup."""
    # Start PostgreSQL service
    # Wait for health check
    # Start application
    # Verify database connectivity
```

**End-to-End Tests**:
```python
async def test_bot_functionality():
    """Test bot functionality with PostgreSQL."""
    # Test user registration
    # Test submission processing
    # Test assessment storage
    # Test rate limiting
```

### 3. Performance Tests

**Concurrent Access Tests**:
```python
async def test_concurrent_users():
    """Test multiple simultaneous users."""
    # Simulate 50+ concurrent users
    # Verify no database locking issues
    # Check response times
    # Monitor connection pool usage
```

**Load Tests**:
```python
async def test_database_load():
    """Test database under load."""
    # High-frequency submissions
    # Bulk data operations
    # Connection pool stress testing
    # Memory usage monitoring
```

### 4. Migration Testing

**Data Integrity Tests**:
```python
async def test_migration_integrity():
    """Verify migration preserves all data correctly."""
    # Compare record counts
    # Verify foreign key relationships
    # Check data types and values
    # Validate enum conversions
```

**Rollback Tests**:
```python
async def test_migration_rollback():
    """Test ability to rollback failed migration."""
    # Simulate migration failure
    # Verify rollback procedure
    # Check data restoration
    # Validate system recovery
```

## Deployment Strategy

### Phase 1: Preparation
1. **Backup Creation**: Full SQLite database backup
2. **Environment Setup**: Add PostgreSQL environment variables
3. **Docker Compose Update**: Add PostgreSQL service
4. **Testing**: Validate new configuration in development

### Phase 2: Migration
1. **Service Shutdown**: Stop current application
2. **Data Migration**: Run migration script
3. **Verification**: Validate data integrity
4. **Configuration Update**: Switch to PostgreSQL connection

### Phase 3: Deployment
1. **Service Startup**: Start PostgreSQL and application
2. **Health Checks**: Verify all services are healthy
3. **Functional Testing**: Test core bot functionality
4. **Monitoring**: Monitor performance and errors

### Phase 4: Cleanup
1. **SQLite Archival**: Archive old SQLite database
2. **Documentation Update**: Update deployment guides
3. **Monitoring Setup**: Configure PostgreSQL monitoring
4. **Backup Configuration**: Set up automated PostgreSQL backups

## Security Considerations

### Database Security
- **Password Management**: Use strong, generated passwords
- **Network Security**: PostgreSQL accessible only within Docker network
- **User Permissions**: Minimal required permissions for application user
- **Connection Encryption**: SSL/TLS for production deployments

### Data Protection
- **Backup Encryption**: Encrypted database backups
- **Access Logging**: Log database access for auditing
- **Data Retention**: Implement data retention policies
- **Privacy Compliance**: Ensure GDPR/privacy compliance

## Monitoring and Maintenance

### Health Monitoring
- **Connection Pool Metrics**: Monitor pool usage and performance
- **Query Performance**: Track slow queries and optimization opportunities
- **Error Rates**: Monitor database errors and connection failures
- **Resource Usage**: CPU, memory, and disk usage monitoring

### Backup Strategy
- **Automated Backups**: Daily automated PostgreSQL dumps
- **Backup Retention**: 30-day backup retention policy
- **Backup Verification**: Regular backup restoration tests
- **Disaster Recovery**: Documented recovery procedures

### Maintenance Tasks
- **Index Optimization**: Regular index analysis and optimization
- **Statistics Updates**: Automated table statistics updates
- **Log Rotation**: PostgreSQL log management
- **Version Updates**: Planned PostgreSQL version updates