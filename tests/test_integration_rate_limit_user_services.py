"""
Integration tests for RateLimitService and UserService working together.
"""
import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.rate_limit_service import RateLimitService, RateLimitStatus
from src.services.user_service import UserService
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
def user_service(mock_session):
    """Create UserService instance with mocked dependencies."""
    service = UserService(mock_session)
    service.user_repo = AsyncMock()
    service.rate_limit_repo = AsyncMock()
    return service


@pytest.fixture
def sample_user():
    """Create a sample user."""
    return User(
        id=1,
        telegram_id=12345,
        username="testuser",
        first_name="Test",
        created_at=datetime(2024, 1, 1, 12, 0, 0),
        is_pro=False,
        daily_submissions=2,
        last_submission_date=date.today()
    )


class TestRateLimitUserServiceIntegration:
    """Integration tests for rate limiting and user management services."""
    
    @pytest.mark.asyncio
    async def test_user_creation_and_rate_limit_check(self, rate_limit_service, user_service, sample_user):
        """Test creating user and checking rate limits."""
        # Arrange
        user_service.user_repo.get_or_create_user.return_value = sample_user
        user_service._get_user_total_submissions = AsyncMock(return_value=0)
        
        rate_limit_service.user_repo.get_by_telegram_id.return_value = sample_user
        rate_limit_service.rate_limit_repo.get_daily_count.return_value = 0
        
        # Act - Create user
        user_profile = await user_service.get_or_create_user(12345, "testuser", "Test")
        
        # Act - Check rate limit for new user
        rate_limit_result = await rate_limit_service.check_rate_limit(12345)
        
        # Assert
        assert user_profile.telegram_id == 12345
        assert user_profile.is_pro == False
        assert rate_limit_result.status == RateLimitStatus.ALLOWED
        assert rate_limit_result.daily_limit == 3  # Free user limit
        assert rate_limit_result.can_submit == True
    
    @pytest.mark.asyncio
    async def test_pro_user_upgrade_affects_rate_limits(self, rate_limit_service, user_service, sample_user):
        """Test that upgrading to pro affects rate limits."""
        # Arrange - Start with free user
        user_service.user_repo.get_by_telegram_id.return_value = sample_user
        user_service.user_repo.set_pro_status.return_value = User(
            id=1,
            telegram_id=12345,
            username="testuser",
            first_name="Test",
            created_at=sample_user.created_at,
            is_pro=True,  # Now pro
            daily_submissions=2,
            last_submission_date=date.today()
        )
        user_service._get_user_total_submissions = AsyncMock(return_value=10)
        
        rate_limit_service.user_repo.get_by_telegram_id.return_value = sample_user
        rate_limit_service.rate_limit_repo.get_daily_count.return_value = 2
        
        # Act - Check rate limit as free user
        free_user_limit = await rate_limit_service.check_rate_limit(12345)
        
        # Act - Upgrade to pro
        pro_profile = await user_service.set_pro_status(12345, True)
        
        # Update rate limit service to return pro user
        pro_user = User(
            id=1,
            telegram_id=12345,
            username="testuser",
            first_name="Test",
            created_at=sample_user.created_at,
            is_pro=True,
            daily_submissions=2,
            last_submission_date=date.today()
        )
        rate_limit_service.user_repo.get_by_telegram_id.return_value = pro_user
        
        # Act - Check rate limit as pro user
        pro_user_limit = await rate_limit_service.check_rate_limit(12345)
        
        # Assert
        assert pro_profile.is_pro == True
        assert free_user_limit.daily_limit == 3
        assert pro_user_limit.daily_limit == 100  # Pro limit
        assert pro_user_limit.remaining == 98  # 100 - 2
    
    @pytest.mark.asyncio
    async def test_submission_recording_updates_both_services(self, rate_limit_service, user_service, sample_user):
        """Test that recording a submission updates both user and rate limit data."""
        # Arrange
        rate_limit_service.user_repo.get_by_telegram_id.return_value = sample_user
        rate_limit_service.rate_limit_repo.increment_daily_count.return_value = AsyncMock()
        rate_limit_service.user_repo.increment_daily_submissions.return_value = AsyncMock()
        rate_limit_service.rate_limit_repo.get_daily_count.return_value = 3  # After increment
        
        user_service.user_repo.get_by_telegram_id.return_value = sample_user
        user_service._get_user_total_submissions = AsyncMock(return_value=15)
        
        # Act - Record submission
        rate_limit_result = await rate_limit_service.record_submission(12345)
        
        # Act - Get updated user profile
        user_profile = await user_service.get_user_profile(12345)
        
        # Assert
        rate_limit_service.rate_limit_repo.increment_daily_count.assert_called_once_with(1)
        rate_limit_service.user_repo.increment_daily_submissions.assert_called_once_with(12345)
        assert rate_limit_result.current_count == 3
        assert user_profile.total_submissions == 15
    
    @pytest.mark.asyncio
    async def test_daily_reset_coordination(self, rate_limit_service, user_service):
        """Test that daily reset works for both services."""
        # Arrange
        users_with_submissions = [
            User(id=1, telegram_id=111, username="user1"),
            User(id=2, telegram_id=222, username="user2"),
        ]
        rate_limit_service.user_repo.get_users_by_submission_date.return_value = users_with_submissions
        rate_limit_service.user_repo.reset_daily_submissions.return_value = AsyncMock()
        
        user_service.user_repo.reset_daily_submissions.return_value = User(
            id=1, telegram_id=111, username="user1", daily_submissions=0
        )
        
        # Act - Reset daily counters via rate limit service
        users_reset = await rate_limit_service.reset_daily_counters()
        
        # Act - Reset individual user via user service
        reset_result = await user_service.reset_user_daily_submissions(111)
        
        # Assert
        assert users_reset == 2
        assert reset_result == True
        assert rate_limit_service.user_repo.reset_daily_submissions.call_count == 2
    
    @pytest.mark.asyncio
    async def test_user_stats_include_rate_limit_data(self, user_service, sample_user):
        """Test that user stats include rate limit information."""
        # Arrange
        user_service.user_repo.get_by_telegram_id.return_value = sample_user
        mock_rate_limits = [
            RateLimit(id=1, user_id=1, submission_date=date.today(), submission_count=3),
            RateLimit(id=2, user_id=1, submission_date=date.today(), submission_count=2),
        ]
        user_service.rate_limit_repo.get_user_rate_limits.return_value = mock_rate_limits
        user_service._calculate_current_streak = AsyncMock(return_value=2)
        user_service._calculate_longest_streak = AsyncMock(return_value=5)
        
        # Act
        user_stats = await user_service.get_user_stats(12345)
        
        # Assert
        assert user_stats is not None
        assert user_stats.total_submissions == 5  # 3 + 2
        assert user_stats.active_days == 2
        assert user_stats.current_streak == 2
        assert user_stats.longest_streak == 5
    
    @pytest.mark.asyncio
    async def test_comprehensive_user_summary_with_rate_limits(self, user_service, sample_user):
        """Test comprehensive user summary includes rate limit information."""
        # Arrange
        user_service.get_user_profile = AsyncMock(return_value=AsyncMock(
            telegram_id=12345,
            is_pro=False,
            created_at=datetime(2024, 1, 1, 12, 0, 0)
        ))
        user_service.get_user_stats = AsyncMock(return_value=AsyncMock(
            total_submissions=25,
            current_streak=3
        ))
        user_service.user_repo.get_daily_submission_count.return_value = 2
        user_service.get_user_display_name = AsyncMock(return_value="Test User")
        
        # Act
        summary = await user_service.get_user_summary(12345)
        
        # Assert
        assert summary is not None
        assert "profile" in summary
        assert "stats" in summary
        assert "current_daily_count" in summary
        assert "is_active_today" in summary
        assert summary["current_daily_count"] == 2
        assert summary["is_active_today"] == True


class TestRequirementsCompliance:
    """Test that the implementation meets all specified requirements."""
    
    @pytest.mark.asyncio
    async def test_requirement_5_1_track_daily_submissions(self, rate_limit_service, sample_user):
        """Test requirement 5.1: Track daily submission count per user."""
        # Arrange
        rate_limit_service.user_repo.get_by_telegram_id.return_value = sample_user
        rate_limit_service.rate_limit_repo.get_daily_count.return_value = 2
        
        # Act
        result = await rate_limit_service.check_rate_limit(12345)
        
        # Assert
        assert result.current_count == 2
        rate_limit_service.rate_limit_repo.get_daily_count.assert_called_once_with(1)
    
    @pytest.mark.asyncio
    async def test_requirement_5_2_inform_at_limit(self, rate_limit_service, sample_user):
        """Test requirement 5.2: Inform user when reaching 3 submissions per day."""
        # Arrange
        rate_limit_service.user_repo.get_by_telegram_id.return_value = sample_user
        rate_limit_service.rate_limit_repo.get_daily_count.return_value = 3
        
        # Act
        result = await rate_limit_service.check_rate_limit(12345)
        
        # Assert
        assert result.status == RateLimitStatus.LIMIT_REACHED
        assert "daily limit" in result.message.lower()
        assert not result.can_submit
    
    @pytest.mark.asyncio
    async def test_requirement_5_3_suggest_pro_upgrade(self, rate_limit_service, sample_user):
        """Test requirement 5.3: Suggest Pro upgrade when limit reached."""
        # Arrange
        rate_limit_service.user_repo.get_by_telegram_id.return_value = sample_user
        rate_limit_service.rate_limit_repo.get_daily_count.return_value = 3
        
        # Act
        result = await rate_limit_service.check_rate_limit(12345)
        
        # Assert
        assert result.status == RateLimitStatus.LIMIT_REACHED
        assert "upgrade to pro" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_requirement_5_4_daily_counter_reset(self, rate_limit_service):
        """Test requirement 5.4: Reset daily submission counter when new day begins."""
        # Arrange
        users_with_submissions = [
            User(id=1, telegram_id=111, username="user1"),
        ]
        rate_limit_service.user_repo.get_users_by_submission_date.return_value = users_with_submissions
        rate_limit_service.user_repo.reset_daily_submissions.return_value = AsyncMock()
        
        # Act
        users_reset = await rate_limit_service.reset_daily_counters()
        
        # Assert
        assert users_reset == 1
        rate_limit_service.user_repo.reset_daily_submissions.assert_called_once_with(111)