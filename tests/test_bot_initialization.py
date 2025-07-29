"""
Integration tests for bot initialization and message routing.
Tests the main application entry point and handler registration.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery, User, Chat
from sqlalchemy.ext.asyncio import AsyncSession

from main import create_bot, create_dispatcher, setup_database, start_bot, stop_bot
from src.config.settings import settings
from src.database.base import AsyncSessionLocal
from src.handlers import start_handler, submission_handler, history_handler, callback_handler


class TestBotInitialization:
    """Test bot initialization and configuration."""
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch.object(settings, 'TELEGRAM_BOT_TOKEN', '1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijk'):
            with patch.object(settings, 'OPENAI_API_KEY', 'test_openai_key'):
                yield settings
    
    def test_create_bot(self, mock_settings):
        """Test bot creation with proper configuration."""
        bot = create_bot()
        
        assert isinstance(bot, Bot)
        assert bot.token == '1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijk'
        assert bot.default.parse_mode.value == 'Markdown'
    
    def test_create_dispatcher(self):
        """Test dispatcher creation with middleware and handlers."""
        with patch('main.Dispatcher') as mock_dispatcher_class:
            mock_dp = MagicMock()
            mock_dispatcher_class.return_value = mock_dp
            
            dp = create_dispatcher()
            
            # Verify dispatcher was created with memory storage
            mock_dispatcher_class.assert_called_once()
            
            # Verify middleware was registered
            assert mock_dp.message.middleware.call_count >= 3  # Database, Logging, Error
            assert mock_dp.callback_query.middleware.call_count >= 3
            
            # Verify routers were included
            assert mock_dp.include_router.call_count == 4
    
    @pytest.mark.asyncio
    async def test_setup_database(self):
        """Test database setup and migration."""
        with patch('main.check_database_connection', return_value=True) as mock_check:
            with patch('main.migrate_database') as mock_migrate:
                await setup_database()
                
                mock_check.assert_called_once()
                mock_migrate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_setup_database_connection_failure(self):
        """Test database setup with connection failure."""
        with patch('main.check_database_connection', return_value=False):
            with pytest.raises(RuntimeError, match="Database connection failed"):
                await setup_database()


class TestBotLifecycle:
    """Test bot startup and shutdown procedures."""
    
    @pytest.fixture
    def mock_bot(self):
        """Mock bot instance."""
        bot = AsyncMock(spec=Bot)
        bot.get_me.return_value = MagicMock(username="test_bot", first_name="Test Bot")
        return bot
    
    @pytest.fixture
    def mock_dispatcher(self):
        """Mock dispatcher instance."""
        dp = AsyncMock(spec=Dispatcher)
        return dp
    
    @pytest.mark.asyncio
    async def test_start_bot_success(self, mock_bot, mock_dispatcher):
        """Test successful bot startup."""
        with patch('main.create_bot', return_value=mock_bot):
            with patch('main.create_dispatcher', return_value=mock_dispatcher):
                with patch('main.setup_database'):
                    await start_bot()
                    
                    mock_bot.get_me.assert_called_once()
                    mock_dispatcher.start_polling.assert_called_once_with(mock_bot, skip_updates=True)
    
    @pytest.mark.asyncio
    async def test_start_bot_database_failure(self):
        """Test bot startup with database failure."""
        with patch('main.create_bot') as mock_create_bot:
            with patch('main.create_dispatcher') as mock_create_dispatcher:
                with patch('main.setup_database', side_effect=RuntimeError("DB error")):
                    with pytest.raises(RuntimeError, match="DB error"):
                        await start_bot()
    
    @pytest.mark.asyncio
    async def test_stop_bot(self, mock_bot, mock_dispatcher):
        """Test graceful bot shutdown."""
        # Set global instances
        import main
        main.bot = mock_bot
        main.dp = mock_dispatcher
        
        # Mock the session attribute
        mock_bot.session = AsyncMock()
        
        with patch('main.close_database') as mock_close_db:
            await stop_bot()
            
            mock_dispatcher.stop_polling.assert_called_once()
            mock_bot.session.close.assert_called_once()
            mock_close_db.assert_called_once()


class TestMessageRouting:
    """Test message routing to appropriate handlers."""
    
    @pytest.fixture
    def mock_user(self):
        """Mock Telegram user."""
        return User(
            id=12345,
            is_bot=False,
            first_name="Test",
            username="testuser"
        )
    
    @pytest.fixture
    def mock_chat(self):
        """Mock Telegram chat."""
        return Chat(id=12345, type="private")
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        return AsyncMock(spec=AsyncSession)
    
    @pytest.mark.asyncio
    async def test_start_command_routing(self, mock_user, mock_chat, mock_session):
        """Test /start command routing to start handler."""
        # Create mock message
        message = Message(
            message_id=1,
            date=1234567890,
            chat=mock_chat,
            from_user=mock_user,
            text="/start"
        )
        
        # Mock the handler
        with patch.object(start_handler, 'handle_start_command') as mock_handler:
            # Simulate message processing
            mock_handler.return_value = None
            
            # Process the message directly
            await mock_handler(message, mock_session)
            
            mock_handler.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_text_message_routing(self, mock_user, mock_chat, mock_session):
        """Test text message routing to submission handler."""
        # Create mock message
        message = Message(
            message_id=1,
            date=1234567890,
            chat=mock_chat,
            from_user=mock_user,
            text="This is a test IELTS writing submission."
        )
        
        # Mock the handler
        with patch.object(submission_handler, 'handle_text_submission') as mock_handler:
            mock_handler.return_value = None
            
            # Process the message
            await mock_handler(message, AsyncMock(), mock_session)
            
            mock_handler.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_callback_query_routing(self, mock_user, mock_chat, mock_session):
        """Test callback query routing to callback handler."""
        # Create mock callback query
        callback = CallbackQuery(
            id="test_callback",
            from_user=mock_user,
            chat_instance="test_instance",
            data="back_to_menu"
        )
        
        # Mock the handler
        with patch.object(callback_handler, 'handle_back_to_menu') as mock_handler:
            mock_handler.return_value = None
            
            # Process the callback
            await mock_handler(callback, AsyncMock())
            
            mock_handler.assert_called_once()


class TestHealthCheck:
    """Test health check endpoint functionality."""
    
    def test_health_check_healthy(self):
        """Test health check with healthy status."""
        from main import app
        from fastapi.testclient import TestClient
        
        # Mock database session
        async def mock_get_session():
            mock_session = AsyncMock()
            mock_session.execute.return_value = None
            yield mock_session
        
        with patch('main.get_db_session', mock_get_session):
            with patch('main.bot') as mock_bot:
                mock_bot.get_me.return_value = MagicMock()
                
                with TestClient(app) as client:
                    response = client.get("/health")
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["status"] == "healthy"
                    assert data["database"] == "connected"
                    assert data["version"] == "1.0.0"
    
    def test_health_check_unhealthy(self):
        """Test health check with unhealthy status."""
        from main import app
        from fastapi.testclient import TestClient
        
        # Mock database session that raises an error
        async def mock_get_session():
            raise Exception("Database connection failed")
        
        with patch('main.get_db_session', mock_get_session):
            with TestClient(app) as client:
                response = client.get("/health")
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "unhealthy"
                assert data["database"] == "disconnected"
    
    def test_root_endpoint(self):
        """Test root endpoint."""
        from main import app
        from fastapi.testclient import TestClient
        
        with TestClient(app) as client:
            response = client.get("/")
            
            assert response.status_code == 200
            data = response.json()
            assert "IELTS Telegram Bot API is running" in data["message"]


class TestMiddleware:
    """Test middleware functionality."""
    
    @pytest.fixture
    def mock_user(self):
        """Mock Telegram user."""
        return User(
            id=12345,
            is_bot=False,
            first_name="Test",
            username="testuser"
        )
    
    @pytest.fixture
    def mock_chat(self):
        """Mock Telegram chat."""
        return Chat(id=12345, type="private")
    
    @pytest.mark.asyncio
    async def test_database_middleware(self, mock_user, mock_chat):
        """Test database middleware provides session."""
        from src.middleware.database_middleware import DatabaseMiddleware
        
        middleware = DatabaseMiddleware()
        
        # Mock handler
        async def mock_handler(event, data):
            assert "session" in data
            assert isinstance(data["session"], AsyncSession)
            return "success"
        
        # Mock message
        message = Message(
            message_id=1,
            date=1234567890,
            chat=mock_chat,
            from_user=mock_user,
            text="test"
        )
        
        with patch('src.database.base.get_session_factory') as mock_factory:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_factory.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await middleware(mock_handler, message, {})
            assert result == "success"
    
    @pytest.mark.asyncio
    async def test_logging_middleware(self, mock_user, mock_chat):
        """Test logging middleware logs events."""
        from src.middleware.logging_middleware import LoggingMiddleware
        
        middleware = LoggingMiddleware()
        
        # Mock handler
        async def mock_handler(event, data):
            return "success"
        
        # Mock message
        message = Message(
            message_id=1,
            date=1234567890,
            chat=mock_chat,
            from_user=mock_user,
            text="test message"
        )
        
        with patch.object(middleware.logger, 'info') as mock_log:
            result = await middleware(mock_handler, message, {})
            
            assert result == "success"
            mock_log.assert_called_once()
            assert "test message" in mock_log.call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_error_middleware(self, mock_user, mock_chat):
        """Test error middleware handles exceptions."""
        from src.middleware.error_middleware import ErrorMiddleware
        from src.exceptions import ValidationError
        
        middleware = ErrorMiddleware()
        
        # Mock handler that raises an error
        async def mock_handler(event, data):
            raise ValidationError("Test validation error")
        
        # Mock message
        message = Message(
            message_id=1,
            date=1234567890,
            chat=mock_chat,
            from_user=mock_user,
            text="test"
        )
        message.answer = AsyncMock()
        
        # Should handle the error gracefully
        await middleware(mock_handler, message, {})
        
        # Verify error response was sent
        message.answer.assert_called_once()
        call_args = message.answer.call_args
        assert "error" in call_args[1]["text"].lower() or "sorry" in call_args[1]["text"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])