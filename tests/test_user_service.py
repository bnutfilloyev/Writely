"""
Unit tests for UserService.
"""
import pytest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.user_service import UserService, UserProfile, UserStats
from src.models.user import User
from src.models.rate_limit import RateLimit


@pytest.fixture
def mock_session():
    """Mock async session."""
    return AsyncMock(spec=AsyncSession)


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


@pytest.fixture
def sample_pro_user():
    """Create a sample pro user."""
    return User(
        id=2,
        telegram_id=67890,
        username="prouser",
        first_name="Pro",
        created_at=datetime(2024, 1, 15, 10, 30, 0),
        is_pro=True,
        daily_submissions=5,
        last_submission_date=date.today()
    )


@pytest.fixture
def sample_rate_limits():
    """Create sample rate limit records."""
    return [
        RateLimit(id=1, user_id=1, submission_date=date.today(), submission_count=3),
        RateLimit(id=2, user_id=1, submission_date=date.today() - timedelta(days=1), submission_count=2),
        RateLimit(id=3, user_id=1, submission_date=date.today() - timedelta(days=2), submission_count=1),
    ]


class TestUserService:
    """Test cases for UserService."""
    
    @pytest.mark.asyncio
    async def test_get_or_create_user_existing(self, user_service, sample_user):
        """Test getting existing user."""
        # Arrange
        user_service.user_repo.get_or_create_user.return_value = sample_user
        user_service._get_user_total_submissions = AsyncMock(return_value=10)
        
        # Act
        profile = await user_service.get_or_create_user(12345, "testuser", "Test")
        
        # Assert
        user_service.user_repo.get_or_create_user.assert_called_once_with(12345, "testuser", "Test")
        assert isinstance(profile, UserProfile)
        assert profile.telegram_id == 12345
        assert profile.username == "testuser"
        assert profile.first_name == "Test"
        assert profile.is_pro == False
        assert profile.total_submissions == 10
    
    @pytest.mark.asyncio
    async def test_get_or_create_user_new(self, user_service):
        """Test creating new user."""
        # Arrange
        new_user = User(
            id=3,
            telegram_id=99999,
            username="newuser",
            first_name="New",
            created_at=datetime.now(),
            is_pro=False,
            daily_submissions=0,
            last_submission_date=None
        )
        user_service.user_repo.get_or_create_user.return_value = new_user
        user_service._get_user_total_submissions = AsyncMock(return_value=0)
        
        # Act
        profile = await user_service.get_or_create_user(99999, "newuser", "New")
        
        # Assert
        assert profile.telegram_id == 99999
        assert profile.total_submissions == 0
        assert profile.daily_submissions == 0
    
    @pytest.mark.asyncio
    async def test_get_user_profile_existing(self, user_service, sample_user):
        """Test getting user profile for existing user."""
        # Arrange
        user_service.user_repo.get_by_telegram_id.return_value = sample_user
        user_service._get_user_total_submissions = AsyncMock(return_value=15)
        
        # Act
        profile = await user_service.get_user_profile(12345)
        
        # Assert
        assert profile is not None
        assert profile.telegram_id == 12345
        assert profile.total_submissions == 15
    
    @pytest.mark.asyncio
    async def test_get_user_profile_not_found(self, user_service):
        """Test getting user profile for non-existent user."""
        # Arrange
        user_service.user_repo.get_by_telegram_id.return_value = None
        
        # Act
        profile = await user_service.get_user_profile(12345)
        
        # Assert
        assert profile is None
    
    @pytest.mark.asyncio
    async def test_update_user_info_success(self, user_service, sample_user):
        """Test successful user info update."""
        # Arrange
        updated_user = User(
            id=1,
            telegram_id=12345,
            username="updateduser",
            first_name="Updated",
            created_at=sample_user.created_at,
            is_pro=False,
            daily_submissions=2,
            last_submission_date=date.today()
        )
        user_service.user_repo.update_user_info.return_value = updated_user
        user_service._get_user_total_submissions = AsyncMock(return_value=20)
        
        # Act
        profile = await user_service.update_user_info(12345, "updateduser", "Updated")
        
        # Assert
        user_service.user_repo.update_user_info.assert_called_once_with(12345, "updateduser", "Updated")
        assert profile is not None
        assert profile.username == "updateduser"
        assert profile.first_name == "Updated"
    
    @pytest.mark.asyncio
    async def test_update_user_info_not_found(self, user_service):
        """Test user info update for non-existent user."""
        # Arrange
        user_service.user_repo.update_user_info.return_value = None
        
        # Act
        profile = await user_service.update_user_info(12345, "newname", "New")
        
        # Assert
        assert profile is None
    
    @pytest.mark.asyncio
    async def test_set_pro_status_success(self, user_service, sample_user):
        """Test successful pro status update."""
        # Arrange
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
        user_service.user_repo.set_pro_status.return_value = pro_user
        user_service._get_user_total_submissions = AsyncMock(return_value=25)
        
        # Act
        profile = await user_service.set_pro_status(12345, True)
        
        # Assert
        user_service.user_repo.set_pro_status.assert_called_once_with(12345, True)
        assert profile is not None
        assert profile.is_pro == True
    
    @pytest.mark.asyncio
    async def test_set_pro_status_not_found(self, user_service):
        """Test pro status update for non-existent user."""
        # Arrange
        user_service.user_repo.set_pro_status.return_value = None
        
        # Act
        profile = await user_service.set_pro_status(12345, True)
        
        # Assert
        assert profile is None
    
    @pytest.mark.asyncio
    async def test_is_pro_user_true(self, user_service, sample_pro_user):
        """Test checking pro status for pro user."""
        # Arrange
        user_service.user_repo.get_by_telegram_id.return_value = sample_pro_user
        
        # Act
        is_pro = await user_service.is_pro_user(67890)
        
        # Assert
        assert is_pro == True
    
    @pytest.mark.asyncio
    async def test_is_pro_user_false(self, user_service, sample_user):
        """Test checking pro status for free user."""
        # Arrange
        user_service.user_repo.get_by_telegram_id.return_value = sample_user
        
        # Act
        is_pro = await user_service.is_pro_user(12345)
        
        # Assert
        assert is_pro == False
    
    @pytest.mark.asyncio
    async def test_is_pro_user_not_found(self, user_service):
        """Test checking pro status for non-existent user."""
        # Arrange
        user_service.user_repo.get_by_telegram_id.return_value = None
        
        # Act
        is_pro = await user_service.is_pro_user(12345)
        
        # Assert
        assert is_pro == False
    
    @pytest.mark.asyncio
    async def test_get_user_stats_success(self, user_service, sample_user, sample_rate_limits):
        """Test getting user statistics."""
        # Arrange
        user_service.user_repo.get_by_telegram_id.return_value = sample_user
        user_service.rate_limit_repo.get_user_rate_limits.return_value = sample_rate_limits
        user_service._calculate_current_streak = AsyncMock(return_value=3)
        user_service._calculate_longest_streak = AsyncMock(return_value=5)
        
        # Act
        stats = await user_service.get_user_stats(12345, days=30)
        
        # Assert
        assert isinstance(stats, UserStats)
        assert stats.total_submissions == 6  # 3 + 2 + 1
        assert stats.active_days == 3
        assert stats.average_submissions_per_day == 6/30
        assert stats.current_streak == 3
        assert stats.longest_streak == 5
    
    @pytest.mark.asyncio
    async def test_get_user_stats_not_found(self, user_service):
        """Test getting stats for non-existent user."""
        # Arrange
        user_service.user_repo.get_by_telegram_id.return_value = None
        
        # Act
        stats = await user_service.get_user_stats(12345)
        
        # Assert
        assert stats is None
    
    @pytest.mark.asyncio
    async def test_get_all_pro_users(self, user_service, sample_pro_user):
        """Test getting all pro users."""
        # Arrange
        user_service.user_repo.get_pro_users.return_value = [sample_pro_user]
        user_service._get_user_total_submissions = AsyncMock(return_value=50)
        
        # Act
        pro_users = await user_service.get_all_pro_users()
        
        # Assert
        assert len(pro_users) == 1
        assert pro_users[0].is_pro == True
        assert pro_users[0].total_submissions == 50
    
    @pytest.mark.asyncio
    async def test_get_active_users(self, user_service, sample_user):
        """Test getting active users."""
        # Arrange
        user_service.user_repo.get_users_by_submission_date.return_value = [sample_user]
        user_service._get_user_total_submissions = AsyncMock(return_value=30)
        
        # Act
        active_users = await user_service.get_active_users(days=7)
        
        # Assert
        assert len(active_users) >= 1
        assert user_service.user_repo.get_users_by_submission_date.call_count <= 7
    
    @pytest.mark.asyncio
    async def test_reset_user_daily_submissions_success(self, user_service, sample_user):
        """Test successful daily submissions reset."""
        # Arrange
        user_service.user_repo.reset_daily_submissions.return_value = sample_user
        
        # Act
        result = await user_service.reset_user_daily_submissions(12345)
        
        # Assert
        user_service.user_repo.reset_daily_submissions.assert_called_once_with(12345)
        assert result == True
    
    @pytest.mark.asyncio
    async def test_reset_user_daily_submissions_not_found(self, user_service):
        """Test daily submissions reset for non-existent user."""
        # Arrange
        user_service.user_repo.reset_daily_submissions.return_value = None
        
        # Act
        result = await user_service.reset_user_daily_submissions(12345)
        
        # Assert
        assert result == False
    
    @pytest.mark.asyncio
    async def test_get_user_display_name_first_name(self, user_service, sample_user):
        """Test getting display name with first name."""
        # Arrange
        user_service.user_repo.get_by_telegram_id.return_value = sample_user
        
        # Act
        display_name = await user_service.get_user_display_name(12345)
        
        # Assert
        assert display_name == "Test"
    
    @pytest.mark.asyncio
    async def test_get_user_display_name_username_only(self, user_service):
        """Test getting display name with username only."""
        # Arrange
        user_no_first_name = User(
            id=1,
            telegram_id=12345,
            username="testuser",
            first_name=None,
            is_pro=False
        )
        user_service.user_repo.get_by_telegram_id.return_value = user_no_first_name
        
        # Act
        display_name = await user_service.get_user_display_name(12345)
        
        # Assert
        assert display_name == "@testuser"
    
    @pytest.mark.asyncio
    async def test_get_user_display_name_telegram_id_only(self, user_service):
        """Test getting display name with telegram ID only."""
        # Arrange
        user_minimal = User(
            id=1,
            telegram_id=12345,
            username=None,
            first_name=None,
            is_pro=False
        )
        user_service.user_repo.get_by_telegram_id.return_value = user_minimal
        
        # Act
        display_name = await user_service.get_user_display_name(12345)
        
        # Assert
        assert display_name == "User 12345"
    
    @pytest.mark.asyncio
    async def test_get_user_display_name_not_found(self, user_service):
        """Test getting display name for non-existent user."""
        # Arrange
        user_service.user_repo.get_by_telegram_id.return_value = None
        
        # Act
        display_name = await user_service.get_user_display_name(12345)
        
        # Assert
        assert display_name == "User 12345"
    
    @pytest.mark.asyncio
    async def test_delete_user_success(self, user_service, sample_user):
        """Test successful user deletion."""
        # Arrange
        user_service.user_repo.get_by_telegram_id.return_value = sample_user
        user_service.user_repo.delete.return_value = AsyncMock()
        
        # Act
        result = await user_service.delete_user(12345)
        
        # Assert
        user_service.user_repo.delete.assert_called_once_with(1)
        assert result == True
    
    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, user_service):
        """Test user deletion for non-existent user."""
        # Arrange
        user_service.user_repo.get_by_telegram_id.return_value = None
        
        # Act
        result = await user_service.delete_user(12345)
        
        # Assert
        user_service.user_repo.delete.assert_not_called()
        assert result == False
    
    @pytest.mark.asyncio
    async def test_get_user_summary_success(self, user_service, sample_user):
        """Test getting comprehensive user summary."""
        # Arrange
        user_service.get_user_profile = AsyncMock(return_value=UserProfile(
            telegram_id=12345,
            username="testuser",
            first_name="Test",
            created_at=datetime(2024, 1, 1, 12, 0, 0),
            is_pro=False,
            daily_submissions=2,
            last_submission_date=date.today(),
            total_submissions=25
        ))
        user_service.get_user_stats = AsyncMock(return_value=UserStats(
            total_submissions=25,
            active_days=10,
            average_submissions_per_day=2.5,
            current_streak=3,
            longest_streak=5
        ))
        user_service.user_repo.get_daily_submission_count.return_value = 2
        user_service.get_user_display_name = AsyncMock(return_value="Test")
        
        # Act
        summary = await user_service.get_user_summary(12345)
        
        # Assert
        assert summary is not None
        assert "profile" in summary
        assert "stats" in summary
        assert "current_daily_count" in summary
        assert "display_name" in summary
        assert "account_age_days" in summary
        assert "is_active_today" in summary
        assert summary["current_daily_count"] == 2
        assert summary["is_active_today"] == True
    
    @pytest.mark.asyncio
    async def test_get_user_summary_not_found(self, user_service):
        """Test getting summary for non-existent user."""
        # Arrange
        user_service.get_user_profile = AsyncMock(return_value=None)
        
        # Act
        summary = await user_service.get_user_summary(12345)
        
        # Assert
        assert summary is None


class TestUserServicePrivateMethods:
    """Test private helper methods of UserService."""
    
    @pytest.mark.asyncio
    async def test_get_user_total_submissions(self, user_service, sample_rate_limits):
        """Test getting total submissions for a user."""
        # Arrange
        user_service.rate_limit_repo.get_user_rate_limits.return_value = sample_rate_limits
        
        # Act
        total = await user_service._get_user_total_submissions(1)
        
        # Assert
        user_service.rate_limit_repo.get_user_rate_limits.assert_called_once_with(1, days=365)
        assert total == 6  # 3 + 2 + 1
    
    @pytest.mark.asyncio
    async def test_calculate_current_streak(self, user_service):
        """Test calculating current consecutive days streak."""
        # Arrange
        today = date.today()
        user_service.rate_limit_repo.get_daily_count.side_effect = [
            3,  # today
            2,  # yesterday
            1,  # day before yesterday
            0   # 3 days ago (breaks streak)
        ]
        
        # Act
        streak = await user_service._calculate_current_streak(1)
        
        # Assert
        assert streak == 3
        assert user_service.rate_limit_repo.get_daily_count.call_count == 4
    
    @pytest.mark.asyncio
    async def test_calculate_current_streak_no_activity(self, user_service):
        """Test calculating streak when no recent activity."""
        # Arrange
        user_service.rate_limit_repo.get_daily_count.return_value = 0
        
        # Act
        streak = await user_service._calculate_current_streak(1)
        
        # Assert
        assert streak == 0
    
    @pytest.mark.asyncio
    async def test_calculate_longest_streak(self, user_service):
        """Test calculating longest streak in a period."""
        # Arrange
        consecutive_rate_limits = [
            RateLimit(id=1, user_id=1, submission_date=date(2024, 1, 1), submission_count=1),
            RateLimit(id=2, user_id=1, submission_date=date(2024, 1, 2), submission_count=2),
            RateLimit(id=3, user_id=1, submission_date=date(2024, 1, 3), submission_count=1),
            RateLimit(id=4, user_id=1, submission_date=date(2024, 1, 4), submission_count=0),  # break
            RateLimit(id=5, user_id=1, submission_date=date(2024, 1, 5), submission_count=3),
            RateLimit(id=6, user_id=1, submission_date=date(2024, 1, 6), submission_count=2),
        ]
        user_service.rate_limit_repo.get_user_rate_limits.return_value = consecutive_rate_limits
        
        # Act
        longest_streak = await user_service._calculate_longest_streak(1, days=30)
        
        # Assert
        assert longest_streak == 3  # Jan 1-3 is longest consecutive streak
    
    @pytest.mark.asyncio
    async def test_calculate_longest_streak_no_data(self, user_service):
        """Test calculating longest streak with no data."""
        # Arrange
        user_service.rate_limit_repo.get_user_rate_limits.return_value = []
        
        # Act
        longest_streak = await user_service._calculate_longest_streak(1, days=30)
        
        # Assert
        assert longest_streak == 0


class TestUserServiceEdgeCases:
    """Test edge cases and error scenarios for UserService."""
    
    @pytest.mark.asyncio
    async def test_get_active_users_no_duplicates(self, user_service, sample_user):
        """Test that get_active_users doesn't return duplicates."""
        # Arrange - same user appears on multiple days
        user_service.user_repo.get_users_by_submission_date.return_value = [sample_user]
        user_service._get_user_total_submissions = AsyncMock(return_value=10)
        
        # Act
        active_users = await user_service.get_active_users(days=3)
        
        # Assert
        # Should only have one instance of the user despite appearing on multiple days
        telegram_ids = [user.telegram_id for user in active_users]
        assert len(set(telegram_ids)) == len(telegram_ids)  # No duplicates
    
    @pytest.mark.asyncio
    async def test_get_user_stats_no_rate_limits(self, user_service, sample_user):
        """Test getting stats when user has no rate limit records."""
        # Arrange
        user_service.user_repo.get_by_telegram_id.return_value = sample_user
        user_service.rate_limit_repo.get_user_rate_limits.return_value = []
        user_service._calculate_current_streak = AsyncMock(return_value=0)
        user_service._calculate_longest_streak = AsyncMock(return_value=0)
        
        # Act
        stats = await user_service.get_user_stats(12345)
        
        # Assert
        assert stats.total_submissions == 0
        assert stats.active_days == 0
        assert stats.average_submissions_per_day == 0
        assert stats.current_streak == 0
        assert stats.longest_streak == 0