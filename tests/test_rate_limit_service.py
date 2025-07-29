"""
Unit tests for RateLimitService.
"""
import pytest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.rate_limit_service import (
    RateLimitService, RateLimitStatus, RateLimitResult, UsageStatistics
)
from src.models.user import User
from src.models.rate_limit import RateLimit


@pytest.fixture
def mock_session():
    """Mock async session."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def rate_limit_service(mock_session):
    """Create RateLimitService instance with mocked dependencies."""
    service = RateLimitService(mock_session)
    service.rate_limit_repo = AsyncMock()
    service.user_repo = AsyncMock()
    return service


@pytest.fixture
def sample_user():
    """Create a sample user."""
    return User(
        id=1,
        telegram_id=12345,
        username="testuser",
        first_name="Test",
        is_pro=False,
        daily_submissions=0,
        last_submission_date=None
    )


@pytest.fixture
def sample_pro_user():
    """Create a sample pro user."""
    return User(
        id=2,
        telegram_id=67890,
        username="prouser",
        first_name="Pro",
        is_pro=True,
        daily_submissions=0,
        last_submission_date=None
    )


@pytest.fixture
def sample_rate_limit():
    """Create a sample rate limit record."""
    return RateLimit(
        id=1,
        user_id=1,
        submission_date=date.today(),
        submission_count=2
    )


class TestRateLimitService:
    """Test cases for RateLimitService."""
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_user_not_found(self, rate_limit_service):
        """Test rate limit check when user doesn't exist."""
        # Arrange
        rate_limit_service.user_repo.get_by_telegram_id.return_value = None
        
        # Act
        result = await rate_limit_service.check_rate_limit(12345)
        
        # Assert
        assert result.status == RateLimitStatus.USER_NOT_FOUND
        assert result.current_count == 0
        assert result.daily_limit == 3
        assert result.remaining == 0
        assert not result.can_submit
        assert "User not found" in result.message
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed_free_user(self, rate_limit_service, sample_user):
        """Test rate limit check for free user within limits."""
        # Arrange
        rate_limit_service.user_repo.get_by_telegram_id.return_value = sample_user
        rate_limit_service.rate_limit_repo.get_daily_count.return_value = 1
        
        # Act
        result = await rate_limit_service.check_rate_limit(12345)
        
        # Assert
        assert result.status == RateLimitStatus.ALLOWED
        assert result.current_count == 1
        assert result.daily_limit == 3
        assert result.remaining == 2
        assert result.can_submit
        assert result.message is None
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed_with_warning(self, rate_limit_service, sample_user):
        """Test rate limit check with warning message when close to limit."""
        # Arrange
        rate_limit_service.user_repo.get_by_telegram_id.return_value = sample_user
        rate_limit_service.rate_limit_repo.get_daily_count.return_value = 2
        
        # Act
        result = await rate_limit_service.check_rate_limit(12345)
        
        # Assert
        assert result.status == RateLimitStatus.ALLOWED
        assert result.current_count == 2
        assert result.daily_limit == 3
        assert result.remaining == 1
        assert result.can_submit
        assert "1 submission remaining" in result.message
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_reached_free_user(self, rate_limit_service, sample_user):
        """Test rate limit check when free user reaches limit."""
        # Arrange
        rate_limit_service.user_repo.get_by_telegram_id.return_value = sample_user
        rate_limit_service.rate_limit_repo.get_daily_count.return_value = 3
        
        # Act
        result = await rate_limit_service.check_rate_limit(12345)
        
        # Assert
        assert result.status == RateLimitStatus.LIMIT_REACHED
        assert result.current_count == 3
        assert result.daily_limit == 3
        assert result.remaining == 0
        assert not result.can_submit
        assert "Upgrade to Pro" in result.message
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_pro_user(self, rate_limit_service, sample_pro_user):
        """Test rate limit check for pro user."""
        # Arrange
        rate_limit_service.user_repo.get_by_telegram_id.return_value = sample_pro_user
        rate_limit_service.rate_limit_repo.get_daily_count.return_value = 50
        
        # Act
        result = await rate_limit_service.check_rate_limit(67890)
        
        # Assert
        assert result.status == RateLimitStatus.ALLOWED
        assert result.current_count == 50
        assert result.daily_limit == 100  # Pro limit
        assert result.remaining == 50
        assert result.can_submit
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_pro_parameter_override(self, rate_limit_service, sample_user):
        """Test rate limit check with pro parameter override."""
        # Arrange
        rate_limit_service.user_repo.get_by_telegram_id.return_value = sample_user
        rate_limit_service.rate_limit_repo.get_daily_count.return_value = 10
        
        # Act
        result = await rate_limit_service.check_rate_limit(12345, is_pro=True)
        
        # Assert
        assert result.status == RateLimitStatus.ALLOWED
        assert result.daily_limit == 100  # Pro limit despite user not being pro
        assert result.can_submit
    
    @pytest.mark.asyncio
    async def test_record_submission_success(self, rate_limit_service, sample_user):
        """Test successful submission recording."""
        # Arrange
        rate_limit_service.user_repo.get_by_telegram_id.return_value = sample_user
        rate_limit_service.rate_limit_repo.increment_daily_count.return_value = AsyncMock()
        rate_limit_service.user_repo.increment_daily_submissions.return_value = AsyncMock()
        rate_limit_service.rate_limit_repo.get_daily_count.return_value = 2
        
        # Act
        result = await rate_limit_service.record_submission(12345)
        
        # Assert
        rate_limit_service.rate_limit_repo.increment_daily_count.assert_called_once_with(1)
        rate_limit_service.user_repo.increment_daily_submissions.assert_called_once_with(12345)
        assert result.status == RateLimitStatus.ALLOWED
        assert result.current_count == 2
    
    @pytest.mark.asyncio
    async def test_record_submission_user_not_found(self, rate_limit_service):
        """Test submission recording when user doesn't exist."""
        # Arrange
        rate_limit_service.user_repo.get_by_telegram_id.return_value = None
        
        # Act
        result = await rate_limit_service.record_submission(12345)
        
        # Assert
        assert result.status == RateLimitStatus.USER_NOT_FOUND
        rate_limit_service.rate_limit_repo.increment_daily_count.assert_not_called()
        rate_limit_service.user_repo.increment_daily_submissions.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_reset_daily_counters(self, rate_limit_service):
        """Test daily counter reset functionality."""
        # Arrange
        yesterday = date.today() - timedelta(days=1)
        users_with_submissions = [
            User(id=1, telegram_id=111, username="user1"),
            User(id=2, telegram_id=222, username="user2"),
        ]
        rate_limit_service.user_repo.get_users_by_submission_date.return_value = users_with_submissions
        rate_limit_service.user_repo.reset_daily_submissions.return_value = AsyncMock()
        
        # Act
        users_reset = await rate_limit_service.reset_daily_counters()
        
        # Assert
        rate_limit_service.user_repo.get_users_by_submission_date.assert_called_once_with(yesterday)
        assert rate_limit_service.user_repo.reset_daily_submissions.call_count == 2
        assert users_reset == 2
    
    @pytest.mark.asyncio
    async def test_get_user_usage_stats(self, rate_limit_service, sample_user):
        """Test getting user usage statistics."""
        # Arrange
        rate_limit_service.user_repo.get_by_telegram_id.return_value = sample_user
        mock_rate_limits = [
            RateLimit(id=1, user_id=1, submission_date=date.today(), submission_count=3),
            RateLimit(id=2, user_id=1, submission_date=date.today() - timedelta(days=1), submission_count=2),
        ]
        rate_limit_service.rate_limit_repo.get_user_rate_limits.return_value = mock_rate_limits
        rate_limit_service.rate_limit_repo.get_weekly_usage_pattern.return_value = [
            {"date": date.today(), "day_name": "Monday", "submission_count": 3}
        ]
        rate_limit_service.rate_limit_repo.get_daily_count.return_value = 3
        
        # Act
        stats = await rate_limit_service.get_user_usage_stats(12345, days=7)
        
        # Assert
        assert stats["user_id"] == 12345
        assert stats["is_pro"] == False
        assert stats["total_submissions"] == 5
        assert stats["active_days"] == 2
        assert stats["average_per_day"] == 5/7
        assert stats["current_daily_count"] == 3
        assert len(stats["weekly_pattern"]) == 1
    
    @pytest.mark.asyncio
    async def test_get_user_usage_stats_user_not_found(self, rate_limit_service):
        """Test getting usage stats for non-existent user."""
        # Arrange
        rate_limit_service.user_repo.get_by_telegram_id.return_value = None
        
        # Act
        stats = await rate_limit_service.get_user_usage_stats(12345)
        
        # Assert
        assert "error" in stats
        assert stats["error"] == "User not found"
    
    @pytest.mark.asyncio
    async def test_get_daily_statistics(self, rate_limit_service):
        """Test getting daily statistics."""
        # Arrange
        mock_stats = {
            "date": date.today(),
            "total_users": 10,
            "total_submissions": 25,
            "users_at_limit": 3,
            "average_submissions_per_user": 2.5
        }
        rate_limit_service.rate_limit_repo.get_daily_statistics.return_value = mock_stats
        
        # Act
        stats = await rate_limit_service.get_daily_statistics()
        
        # Assert
        assert isinstance(stats, UsageStatistics)
        assert stats.total_users == 10
        assert stats.total_submissions == 25
        assert stats.users_at_limit == 3
        assert stats.average_submissions_per_user == 2.5
    
    @pytest.mark.asyncio
    async def test_cleanup_old_records(self, rate_limit_service):
        """Test cleanup of old rate limit records."""
        # Arrange
        rate_limit_service.rate_limit_repo.cleanup_old_records.return_value = 15
        
        # Act
        deleted_count = await rate_limit_service.cleanup_old_records(90)
        
        # Assert
        rate_limit_service.rate_limit_repo.cleanup_old_records.assert_called_once_with(90)
        assert deleted_count == 15
    
    @pytest.mark.asyncio
    async def test_get_users_at_limit(self, rate_limit_service):
        """Test getting users at daily limit."""
        # Arrange
        mock_rate_limits = [
            RateLimit(id=1, user_id=1, submission_date=date.today(), submission_count=3),
            RateLimit(id=2, user_id=2, submission_date=date.today(), submission_count=3),
        ]
        rate_limit_service.rate_limit_repo.get_users_by_usage_level.return_value = mock_rate_limits
        
        # Act
        users_at_limit = await rate_limit_service.get_users_at_limit()
        
        # Assert
        rate_limit_service.rate_limit_repo.get_users_by_usage_level.assert_called_once_with(
            None, min_submissions=3
        )
        assert len(users_at_limit) == 2
    
    @pytest.mark.asyncio
    async def test_is_user_active_today(self, rate_limit_service, sample_user):
        """Test checking if user is active today."""
        # Arrange
        rate_limit_service.user_repo.get_by_telegram_id.return_value = sample_user
        rate_limit_service.rate_limit_repo.is_user_active_today.return_value = True
        
        # Act
        is_active = await rate_limit_service.is_user_active_today(12345)
        
        # Assert
        rate_limit_service.rate_limit_repo.is_user_active_today.assert_called_once_with(1)
        assert is_active == True
    
    @pytest.mark.asyncio
    async def test_is_user_active_today_user_not_found(self, rate_limit_service):
        """Test checking activity for non-existent user."""
        # Arrange
        rate_limit_service.user_repo.get_by_telegram_id.return_value = None
        
        # Act
        is_active = await rate_limit_service.is_user_active_today(12345)
        
        # Assert
        assert is_active == False
        rate_limit_service.rate_limit_repo.is_user_active_today.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_time_until_reset(self, rate_limit_service):
        """Test getting time until daily reset."""
        # Act
        time_until_reset = await rate_limit_service.get_time_until_reset()
        
        # Assert
        assert isinstance(time_until_reset, timedelta)
        assert time_until_reset.total_seconds() > 0
        assert time_until_reset.total_seconds() <= 24 * 60 * 60  # Less than 24 hours


class TestRateLimitEdgeCases:
    """Test edge cases and error scenarios for RateLimitService."""
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_exactly_at_limit(self, rate_limit_service, sample_user):
        """Test rate limit check when exactly at the limit."""
        # Arrange
        rate_limit_service.user_repo.get_by_telegram_id.return_value = sample_user
        rate_limit_service.rate_limit_repo.get_daily_count.return_value = 3
        
        # Act
        result = await rate_limit_service.check_rate_limit(12345)
        
        # Assert
        assert result.status == RateLimitStatus.LIMIT_REACHED
        assert result.remaining == 0
        assert not result.can_submit
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_over_limit(self, rate_limit_service, sample_user):
        """Test rate limit check when over the limit (edge case)."""
        # Arrange
        rate_limit_service.user_repo.get_by_telegram_id.return_value = sample_user
        rate_limit_service.rate_limit_repo.get_daily_count.return_value = 5
        
        # Act
        result = await rate_limit_service.check_rate_limit(12345)
        
        # Assert
        assert result.status == RateLimitStatus.LIMIT_REACHED
        assert result.remaining == 0  # Should not be negative
        assert not result.can_submit
    
    @pytest.mark.asyncio
    async def test_pro_user_at_pro_limit(self, rate_limit_service, sample_pro_user):
        """Test pro user reaching pro limit."""
        # Arrange
        rate_limit_service.user_repo.get_by_telegram_id.return_value = sample_pro_user
        rate_limit_service.rate_limit_repo.get_daily_count.return_value = 100
        
        # Act
        result = await rate_limit_service.check_rate_limit(67890)
        
        # Assert
        assert result.status == RateLimitStatus.LIMIT_REACHED
        assert result.daily_limit == 100
        assert not result.can_submit
        assert "try again tomorrow" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_reset_daily_counters_no_users(self, rate_limit_service):
        """Test daily counter reset when no users have submissions."""
        # Arrange
        rate_limit_service.user_repo.get_users_by_submission_date.return_value = []
        
        # Act
        users_reset = await rate_limit_service.reset_daily_counters()
        
        # Assert
        assert users_reset == 0
        rate_limit_service.user_repo.reset_daily_submissions.assert_not_called()