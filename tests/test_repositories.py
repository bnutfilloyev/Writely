"""
Unit tests for repository operations.
"""
import pytest
import asyncio
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text
from src.database.base import Base
from src.models.user import User
from src.models.submission import Submission, TaskType, ProcessingStatus
from src.models.assessment import Assessment
from src.models.rate_limit import RateLimit
from src.repositories.user_repository import UserRepository
from src.repositories.submission_repository import SubmissionRepository
from src.repositories.assessment_repository import AssessmentRepository
from src.repositories.rate_limit_repository import RateLimitRepository


# Test database setup
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest.fixture
async def test_session(test_engine):
    """Create test database session."""
    AsyncSessionLocal = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    async with AsyncSessionLocal() as session:
        yield session

@pytest.fixture
async def user_repo(test_session):
    """Create UserRepository instance."""
    return UserRepository(test_session)

@pytest.fixture
async def submission_repo(test_session):
    """Create SubmissionRepository instance."""
    return SubmissionRepository(test_session)

@pytest.fixture
async def assessment_repo(test_session):
    """Create AssessmentRepository instance."""
    return AssessmentRepository(test_session)

@pytest.fixture
async def rate_limit_repo(test_session):
    """Create RateLimitRepository instance."""
    return RateLimitRepository(test_session)

@pytest.fixture
async def sample_user(user_repo):
    """Create a sample user for testing."""
    return await user_repo.create_user(
        telegram_id=12345,
        username="testuser",
        first_name="Test"
    )

@pytest.fixture
async def sample_submission(submission_repo, sample_user):
    """Create a sample submission for testing."""
    return await submission_repo.create_submission(
        user_id=sample_user.id,
        text="This is a test writing submission for IELTS Task 1.",
        task_type=TaskType.TASK_1,
        word_count=50
    )


class TestUserRepository:
    """Test cases for UserRepository."""

    async def test_create_user(self, user_repo):
        """Test creating a new user."""
        user = await user_repo.create_user(
            telegram_id=123456,
            username="newuser",
            first_name="New"
        )
        
        assert user.id is not None
        assert user.telegram_id == 123456
        assert user.username == "newuser"
        assert user.first_name == "New"
        assert user.is_pro is False
        assert user.daily_submissions == 0

    async def test_get_by_telegram_id(self, user_repo, sample_user):
        """Test getting user by Telegram ID."""
        user = await user_repo.get_by_telegram_id(sample_user.telegram_id)
        
        assert user is not None
        assert user.id == sample_user.id
        assert user.telegram_id == sample_user.telegram_id

    async def test_get_by_telegram_id_not_found(self, user_repo):
        """Test getting non-existent user by Telegram ID."""
        user = await user_repo.get_by_telegram_id(999999)
        assert user is None

    async def test_get_or_create_user_existing(self, user_repo, sample_user):
        """Test get_or_create with existing user."""
        user = await user_repo.get_or_create_user(
            telegram_id=sample_user.telegram_id,
            username="updated_username"
        )
        
        assert user.id == sample_user.id
        assert user.username == "updated_username"

    async def test_get_or_create_user_new(self, user_repo):
        """Test get_or_create with new user."""
        user = await user_repo.get_or_create_user(
            telegram_id=789012,
            username="brandnew",
            first_name="Brand"
        )
        
        assert user.id is not None
        assert user.telegram_id == 789012
        assert user.username == "brandnew"
        assert user.first_name == "Brand"

    async def test_set_pro_status(self, user_repo, sample_user):
        """Test setting user pro status."""
        user = await user_repo.set_pro_status(sample_user.telegram_id, True)
        
        assert user is not None
        assert user.is_pro is True

    async def test_increment_daily_submissions(self, user_repo, sample_user):
        """Test incrementing daily submissions."""
        user = await user_repo.increment_daily_submissions(sample_user.telegram_id)
        
        assert user is not None
        assert user.daily_submissions == 1
        assert user.last_submission_date == date.today()

    async def test_reset_daily_submissions(self, user_repo, sample_user):
        """Test resetting daily submissions."""
        # First increment
        await user_repo.increment_daily_submissions(sample_user.telegram_id)
        
        # Then reset
        user = await user_repo.reset_daily_submissions(sample_user.telegram_id)
        
        assert user is not None
        assert user.daily_submissions == 0
        assert user.last_submission_date == date.today()

    async def test_get_daily_submission_count(self, user_repo, sample_user):
        """Test getting daily submission count."""
        # Initially should be 0
        count = await user_repo.get_daily_submission_count(sample_user.telegram_id)
        assert count == 0
        
        # After increment should be 1
        await user_repo.increment_daily_submissions(sample_user.telegram_id)
        count = await user_repo.get_daily_submission_count(sample_user.telegram_id)
        assert count == 1


class TestSubmissionRepository:
    """Test cases for SubmissionRepository."""

    async def test_create_submission(self, submission_repo, sample_user):
        """Test creating a new submission."""
        submission = await submission_repo.create_submission(
            user_id=sample_user.id,
            text="Test submission text for Task 2.",
            task_type=TaskType.TASK_2,
            word_count=75
        )
        
        assert submission.id is not None
        assert submission.user_id == sample_user.id
        assert submission.text == "Test submission text for Task 2."
        assert submission.task_type == TaskType.TASK_2
        assert submission.word_count == 75
        assert submission.processing_status == ProcessingStatus.PENDING

    async def test_get_by_user_id(self, submission_repo, sample_user, sample_submission):
        """Test getting submissions by user ID."""
        submissions = await submission_repo.get_by_user_id(sample_user.id)
        
        assert len(submissions) == 1
        assert submissions[0].id == sample_submission.id

    async def test_get_pending_submissions(self, submission_repo, sample_submission):
        """Test getting pending submissions."""
        pending = await submission_repo.get_pending_submissions()
        
        assert len(pending) == 1
        assert pending[0].id == sample_submission.id
        assert pending[0].processing_status == ProcessingStatus.PENDING

    async def test_update_processing_status(self, submission_repo, sample_submission):
        """Test updating submission processing status."""
        updated = await submission_repo.update_processing_status(
            sample_submission.id, 
            ProcessingStatus.COMPLETED
        )
        
        assert updated is not None
        assert updated.processing_status == ProcessingStatus.COMPLETED

    async def test_get_by_task_type(self, submission_repo, sample_user):
        """Test getting submissions by task type."""
        # Create submissions of different types
        await submission_repo.create_submission(
            user_id=sample_user.id,
            text="Task 1 submission",
            task_type=TaskType.TASK_1,
            word_count=60
        )
        await submission_repo.create_submission(
            user_id=sample_user.id,
            text="Task 2 submission",
            task_type=TaskType.TASK_2,
            word_count=80
        )
        
        task1_submissions = await submission_repo.get_by_task_type(TaskType.TASK_1)
        task2_submissions = await submission_repo.get_by_task_type(TaskType.TASK_2)
        
        assert len(task1_submissions) >= 1
        assert len(task2_submissions) >= 1
        assert all(s.task_type == TaskType.TASK_1 for s in task1_submissions)
        assert all(s.task_type == TaskType.TASK_2 for s in task2_submissions)

    async def test_get_daily_submission_count(self, submission_repo, sample_user):
        """Test getting daily submission count."""
        today = date.today()
        
        # Initially should be 0
        count = await submission_repo.get_daily_submission_count(sample_user.id, today)
        initial_count = count
        
        # Create a submission
        await submission_repo.create_submission(
            user_id=sample_user.id,
            text="Daily count test",
            task_type=TaskType.TASK_1,
            word_count=50
        )
        
        # Count should increase by 1
        count = await submission_repo.get_daily_submission_count(sample_user.id, today)
        assert count == initial_count + 1

    async def test_get_user_statistics(self, submission_repo, sample_user):
        """Test getting user statistics."""
        # Create multiple submissions
        await submission_repo.create_submission(
            user_id=sample_user.id,
            text="Task 1 submission",
            task_type=TaskType.TASK_1,
            word_count=60
        )
        await submission_repo.create_submission(
            user_id=sample_user.id,
            text="Task 2 submission",
            task_type=TaskType.TASK_2,
            word_count=80
        )
        
        stats = await submission_repo.get_user_statistics(sample_user.id)
        
        assert stats["total_submissions"] >= 2
        assert stats["task1_submissions"] >= 1
        assert stats["task2_submissions"] >= 1
        assert stats["average_word_count"] > 0


class TestAssessmentRepository:
    """Test cases for AssessmentRepository."""

    async def test_create_assessment(self, assessment_repo, sample_submission):
        """Test creating a new assessment."""
        assessment = await assessment_repo.create_assessment(
            submission_id=sample_submission.id,
            task_achievement_score=7.0,
            coherence_cohesion_score=6.5,
            lexical_resource_score=7.5,
            grammatical_accuracy_score=6.0,
            overall_band_score=6.8,
            detailed_feedback="Good overall performance with room for improvement.",
            improvement_suggestions=["Work on grammar", "Expand vocabulary"]
        )
        
        assert assessment.id is not None
        assert assessment.submission_id == sample_submission.id
        assert assessment.task_achievement_score == 7.0
        assert assessment.overall_band_score == 6.8
        assert assessment.improvement_suggestions_list == ["Work on grammar", "Expand vocabulary"]

    async def test_get_by_submission_id(self, assessment_repo, sample_submission):
        """Test getting assessment by submission ID."""
        # Create assessment
        created = await assessment_repo.create_assessment(
            submission_id=sample_submission.id,
            task_achievement_score=7.0,
            coherence_cohesion_score=6.5,
            lexical_resource_score=7.5,
            grammatical_accuracy_score=6.0,
            overall_band_score=6.8,
            detailed_feedback="Test feedback",
            improvement_suggestions=["Test suggestion"]
        )
        
        # Retrieve by submission ID
        assessment = await assessment_repo.get_by_submission_id(sample_submission.id)
        
        assert assessment is not None
        assert assessment.id == created.id
        assert assessment.submission_id == sample_submission.id

    async def test_get_user_assessments(self, assessment_repo, sample_user, sample_submission):
        """Test getting assessments for a user."""
        # Create assessment
        await assessment_repo.create_assessment(
            submission_id=sample_submission.id,
            task_achievement_score=7.0,
            coherence_cohesion_score=6.5,
            lexical_resource_score=7.5,
            grammatical_accuracy_score=6.0,
            overall_band_score=6.8,
            detailed_feedback="Test feedback",
            improvement_suggestions=["Test suggestion"]
        )
        
        assessments = await assessment_repo.get_user_assessments(sample_user.id)
        
        assert len(assessments) == 1
        assert assessments[0].submission_id == sample_submission.id

    async def test_get_average_scores_by_user(self, assessment_repo, sample_user, sample_submission):
        """Test getting average scores for a user."""
        # Create assessment
        await assessment_repo.create_assessment(
            submission_id=sample_submission.id,
            task_achievement_score=7.0,
            coherence_cohesion_score=6.5,
            lexical_resource_score=7.5,
            grammatical_accuracy_score=6.0,
            overall_band_score=6.8,
            detailed_feedback="Test feedback",
            improvement_suggestions=["Test suggestion"]
        )
        
        averages = await assessment_repo.get_average_scores_by_user(sample_user.id)
        
        assert averages["avg_task_achievement"] == 7.0
        assert averages["avg_coherence_cohesion"] == 6.5
        assert averages["avg_lexical_resource"] == 7.5
        assert averages["avg_grammatical_accuracy"] == 6.0
        assert averages["avg_overall_band"] == 6.8

    async def test_get_user_progress_data(self, assessment_repo, sample_user, sample_submission):
        """Test getting user progress data."""
        # Create assessment
        await assessment_repo.create_assessment(
            submission_id=sample_submission.id,
            task_achievement_score=7.0,
            coherence_cohesion_score=6.5,
            lexical_resource_score=7.5,
            grammatical_accuracy_score=6.0,
            overall_band_score=6.8,
            detailed_feedback="Test feedback",
            improvement_suggestions=["Test suggestion"]
        )
        
        progress_data = await assessment_repo.get_user_progress_data(sample_user.id)
        
        assert len(progress_data) == 1
        assert progress_data[0]["overall_band_score"] == 6.8
        assert progress_data[0]["task_type"] == TaskType.TASK_1.value
        assert "scores" in progress_data[0]


class TestRateLimitRepository:
    """Test cases for RateLimitRepository."""

    async def test_get_or_create_today_limit(self, rate_limit_repo, sample_user):
        """Test getting or creating today's rate limit."""
        rate_limit = await rate_limit_repo.get_or_create_today_limit(sample_user.id)
        
        assert rate_limit.id is not None
        assert rate_limit.user_id == sample_user.id
        assert rate_limit.submission_date == date.today()
        assert rate_limit.submission_count == 0

    async def test_get_daily_count(self, rate_limit_repo, sample_user):
        """Test getting daily submission count."""
        # Initially should be 0
        count = await rate_limit_repo.get_daily_count(sample_user.id)
        assert count == 0
        
        # Create rate limit record
        await rate_limit_repo.get_or_create_today_limit(sample_user.id)
        count = await rate_limit_repo.get_daily_count(sample_user.id)
        assert count == 0

    async def test_increment_daily_count(self, rate_limit_repo, sample_user):
        """Test incrementing daily submission count."""
        rate_limit = await rate_limit_repo.increment_daily_count(sample_user.id)
        
        assert rate_limit.submission_count == 1
        assert rate_limit.submission_date == date.today()

    async def test_check_daily_limit(self, rate_limit_repo, sample_user):
        """Test checking daily limit status."""
        # Initially under limit
        status = await rate_limit_repo.check_daily_limit(sample_user.id, daily_limit=3)
        
        assert status["current_count"] == 0
        assert status["daily_limit"] == 3
        assert status["remaining"] == 3
        assert status["limit_reached"] is False
        assert status["can_submit"] is True
        
        # Increment to limit
        for _ in range(3):
            await rate_limit_repo.increment_daily_count(sample_user.id)
        
        status = await rate_limit_repo.check_daily_limit(sample_user.id, daily_limit=3)
        
        assert status["current_count"] == 3
        assert status["remaining"] == 0
        assert status["limit_reached"] is True
        assert status["can_submit"] is False

    async def test_reset_daily_count(self, rate_limit_repo, sample_user):
        """Test resetting daily submission count."""
        # First increment
        await rate_limit_repo.increment_daily_count(sample_user.id)
        
        # Then reset
        rate_limit = await rate_limit_repo.reset_daily_count(sample_user.id)
        
        assert rate_limit is not None
        assert rate_limit.submission_count == 0

    async def test_get_weekly_usage_pattern(self, rate_limit_repo, sample_user):
        """Test getting weekly usage pattern."""
        # Create some usage
        await rate_limit_repo.increment_daily_count(sample_user.id)
        
        pattern = await rate_limit_repo.get_weekly_usage_pattern(sample_user.id)
        
        assert len(pattern) == 7
        assert all("date" in day and "submission_count" in day for day in pattern)
        
        # Today should have count of 1
        today_data = next(day for day in pattern if day["date"] == date.today())
        assert today_data["submission_count"] == 1

    async def test_is_user_active_today(self, rate_limit_repo, sample_user):
        """Test checking if user is active today."""
        # Initially not active
        is_active = await rate_limit_repo.is_user_active_today(sample_user.id)
        assert is_active is False
        
        # After submission, should be active
        await rate_limit_repo.increment_daily_count(sample_user.id)
        is_active = await rate_limit_repo.is_user_active_today(sample_user.id)
        assert is_active is True

    async def test_get_daily_statistics(self, rate_limit_repo, sample_user):
        """Test getting daily statistics."""
        # Create some usage
        await rate_limit_repo.increment_daily_count(sample_user.id)
        await rate_limit_repo.increment_daily_count(sample_user.id)
        
        stats = await rate_limit_repo.get_daily_statistics()
        
        assert stats["date"] == date.today()
        assert stats["total_users"] >= 1
        assert stats["total_submissions"] >= 2
        assert stats["average_submissions_per_user"] > 0


if __name__ == "__main__":
    pytest.main([__file__])