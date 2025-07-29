"""
Unit tests for database models.
"""
import pytest
import asyncio
from datetime import datetime, date
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.exc import IntegrityError
from src.database.base import Base
from src.models import User, Submission, Assessment, RateLimit, TaskType, ProcessingStatus


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
    async_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


class TestUserModel:
    """Test cases for User model."""
    
    async def test_user_creation(self, test_session):
        """Test creating a new user."""
        user = User(
            telegram_id=123456789,
            username="testuser",
            first_name="Test"
        )
        test_session.add(user)
        await test_session.commit()
        
        assert user.id is not None
        assert user.telegram_id == 123456789
        assert user.username == "testuser"
        assert user.first_name == "Test"
        assert user.is_pro is False
        assert user.daily_submissions == 0
        assert user.created_at is not None
    
    async def test_user_unique_telegram_id(self, test_session):
        """Test that telegram_id must be unique."""
        user1 = User(telegram_id=123456789, username="user1")
        user2 = User(telegram_id=123456789, username="user2")
        
        test_session.add(user1)
        await test_session.commit()
        
        test_session.add(user2)
        with pytest.raises(IntegrityError):
            await test_session.commit()
    
    async def test_user_daily_submission_methods(self, test_session):
        """Test daily submission tracking methods."""
        user = User(telegram_id=123456789)
        test_session.add(user)
        await test_session.commit()
        
        # Test increment
        user.increment_daily_submissions()
        assert user.daily_submissions == 1
        assert user.last_submission_date == date.today()
        
        # Test another increment same day
        user.increment_daily_submissions()
        assert user.daily_submissions == 2
        
        # Test reset
        user.reset_daily_submissions()
        assert user.daily_submissions == 0
        assert user.last_submission_date == date.today()


class TestSubmissionModel:
    """Test cases for Submission model."""
    
    async def test_submission_creation(self, test_session):
        """Test creating a new submission."""
        # Create user first
        user = User(telegram_id=123456789)
        test_session.add(user)
        await test_session.flush()
        
        submission = Submission(
            user_id=user.id,
            text="This is a test writing submission for IELTS Task 1.",
            task_type=TaskType.TASK_1,
            word_count=10
        )
        test_session.add(submission)
        await test_session.commit()
        
        assert submission.id is not None
        assert submission.user_id == user.id
        assert submission.task_type == TaskType.TASK_1
        assert submission.processing_status == ProcessingStatus.PENDING
        assert submission.submitted_at is not None
    
    async def test_submission_status_properties(self, test_session):
        """Test submission status property methods."""
        user = User(telegram_id=123456789)
        test_session.add(user)
        await test_session.flush()
        
        submission = Submission(
            user_id=user.id,
            text="Test text",
            task_type=TaskType.TASK_2,
            word_count=5
        )
        test_session.add(submission)
        await test_session.commit()
        
        # Test pending status
        assert submission.is_pending is True
        assert submission.is_completed is False
        assert submission.is_failed is False
        
        # Test completed status
        submission.processing_status = ProcessingStatus.COMPLETED
        assert submission.is_pending is False
        assert submission.is_completed is True
        assert submission.is_failed is False
        
        # Test failed status
        submission.processing_status = ProcessingStatus.FAILED
        assert submission.is_pending is False
        assert submission.is_completed is False
        assert submission.is_failed is True
    
    async def test_submission_user_relationship(self, test_session):
        """Test relationship between submission and user."""
        from sqlalchemy.orm import selectinload
        from sqlalchemy import select
        
        user = User(telegram_id=123456789)
        test_session.add(user)
        await test_session.flush()
        
        submission = Submission(
            user_id=user.id,
            text="Test text",
            task_type=TaskType.TASK_1,
            word_count=5
        )
        test_session.add(submission)
        await test_session.commit()
        
        # Reload user with submissions to test relationship
        result = await test_session.execute(
            select(User).options(selectinload(User.submissions)).where(User.id == user.id)
        )
        user_with_submissions = result.scalar_one()
        
        # Test relationship
        assert submission.user.telegram_id == 123456789
        assert len(user_with_submissions.submissions) == 1
        assert user_with_submissions.submissions[0].id == submission.id


class TestAssessmentModel:
    """Test cases for Assessment model."""
    
    async def test_assessment_creation(self, test_session):
        """Test creating a new assessment."""
        # Create user and submission first
        user = User(telegram_id=123456789)
        test_session.add(user)
        await test_session.flush()
        
        submission = Submission(
            user_id=user.id,
            text="Test text",
            task_type=TaskType.TASK_1,
            word_count=5
        )
        test_session.add(submission)
        await test_session.flush()
        
        assessment = Assessment(
            submission_id=submission.id,
            task_achievement_score=7.0,
            coherence_cohesion_score=6.5,
            lexical_resource_score=7.5,
            grammatical_accuracy_score=6.0,
            overall_band_score=6.75,
            detailed_feedback="Good writing with some areas for improvement.",
            improvement_suggestions='["Work on grammar", "Expand vocabulary"]'
        )
        test_session.add(assessment)
        await test_session.commit()
        
        assert assessment.id is not None
        assert assessment.submission_id == submission.id
        assert assessment.overall_band_score == 6.75
        assert assessment.assessed_at is not None
    
    async def test_assessment_improvement_suggestions_property(self, test_session):
        """Test improvement suggestions list property."""
        user = User(telegram_id=123456789)
        test_session.add(user)
        await test_session.flush()
        
        submission = Submission(
            user_id=user.id,
            text="Test text",
            task_type=TaskType.TASK_1,
            word_count=5
        )
        test_session.add(submission)
        await test_session.flush()
        
        assessment = Assessment(
            submission_id=submission.id,
            task_achievement_score=7.0,
            coherence_cohesion_score=6.5,
            lexical_resource_score=7.5,
            grammatical_accuracy_score=6.0,
            overall_band_score=6.75,
            detailed_feedback="Test feedback",
            improvement_suggestions='["Suggestion 1", "Suggestion 2"]'
        )
        test_session.add(assessment)
        await test_session.commit()
        
        # Test getter
        suggestions = assessment.improvement_suggestions_list
        assert suggestions == ["Suggestion 1", "Suggestion 2"]
        
        # Test setter
        assessment.improvement_suggestions_list = ["New suggestion 1", "New suggestion 2"]
        assert "New suggestion 1" in assessment.improvement_suggestions
        assert "New suggestion 2" in assessment.improvement_suggestions
    
    async def test_assessment_scores_dict_property(self, test_session):
        """Test scores dictionary property."""
        user = User(telegram_id=123456789)
        test_session.add(user)
        await test_session.flush()
        
        submission = Submission(
            user_id=user.id,
            text="Test text",
            task_type=TaskType.TASK_1,
            word_count=5
        )
        test_session.add(submission)
        await test_session.flush()
        
        assessment = Assessment(
            submission_id=submission.id,
            task_achievement_score=7.0,
            coherence_cohesion_score=6.5,
            lexical_resource_score=7.5,
            grammatical_accuracy_score=6.0,
            overall_band_score=6.75,
            detailed_feedback="Test feedback",
            improvement_suggestions='[]'
        )
        test_session.add(assessment)
        await test_session.commit()
        
        scores = assessment.scores_dict
        assert scores["task_achievement"] == 7.0
        assert scores["coherence_cohesion"] == 6.5
        assert scores["lexical_resource"] == 7.5
        assert scores["grammatical_accuracy"] == 6.0
        assert scores["overall_band_score"] == 6.75
    
    async def test_assessment_score_validation(self, test_session):
        """Test score validation method."""
        user = User(telegram_id=123456789)
        test_session.add(user)
        await test_session.flush()
        
        submission = Submission(
            user_id=user.id,
            text="Test text",
            task_type=TaskType.TASK_1,
            word_count=5
        )
        test_session.add(submission)
        await test_session.flush()
        
        # Valid scores
        assessment = Assessment(
            submission_id=submission.id,
            task_achievement_score=7.0,
            coherence_cohesion_score=6.5,
            lexical_resource_score=7.5,
            grammatical_accuracy_score=6.0,
            overall_band_score=6.75,
            detailed_feedback="Test feedback",
            improvement_suggestions='[]'
        )
        assert assessment.validate_scores() is True
        
        # Invalid score (too high)
        assessment.task_achievement_score = 10.0
        assert assessment.validate_scores() is False
        
        # Invalid score (negative)
        assessment.task_achievement_score = -1.0
        assert assessment.validate_scores() is False
    
    async def test_assessment_calculate_overall_score(self, test_session):
        """Test overall score calculation."""
        user = User(telegram_id=123456789)
        test_session.add(user)
        await test_session.flush()
        
        submission = Submission(
            user_id=user.id,
            text="Test text",
            task_type=TaskType.TASK_1,
            word_count=5
        )
        test_session.add(submission)
        await test_session.flush()
        
        assessment = Assessment(
            submission_id=submission.id,
            task_achievement_score=7.0,
            coherence_cohesion_score=6.0,
            lexical_resource_score=8.0,
            grammatical_accuracy_score=5.0,
            overall_band_score=0.0,  # Will be calculated
            detailed_feedback="Test feedback",
            improvement_suggestions='[]'
        )
        
        calculated_score = assessment.calculate_overall_score()
        expected_score = (7.0 + 6.0 + 8.0 + 5.0) / 4  # 6.5
        assert calculated_score == 6.5


class TestRateLimitModel:
    """Test cases for RateLimit model."""
    
    async def test_rate_limit_creation(self, test_session):
        """Test creating a new rate limit record."""
        user = User(telegram_id=123456789)
        test_session.add(user)
        await test_session.flush()
        
        rate_limit = RateLimit(
            user_id=user.id,
            submission_date=date.today(),
            submission_count=1
        )
        test_session.add(rate_limit)
        await test_session.commit()
        
        assert rate_limit.id is not None
        assert rate_limit.user_id == user.id
        assert rate_limit.submission_date == date.today()
        assert rate_limit.submission_count == 1
        assert rate_limit.created_at is not None
    
    async def test_rate_limit_is_today_property(self, test_session):
        """Test is_today property."""
        user = User(telegram_id=123456789)
        test_session.add(user)
        await test_session.flush()
        
        rate_limit = RateLimit(
            user_id=user.id,
            submission_date=date.today(),
            submission_count=0
        )
        assert rate_limit.is_today is True
        
        # Test with yesterday's date
        from datetime import timedelta
        yesterday = date.today() - timedelta(days=1)
        rate_limit.submission_date = yesterday
        assert rate_limit.is_today is False
    
    async def test_rate_limit_increment_count(self, test_session):
        """Test increment count method."""
        user = User(telegram_id=123456789)
        test_session.add(user)
        await test_session.flush()
        
        rate_limit = RateLimit(
            user_id=user.id,
            submission_date=date.today(),
            submission_count=0
        )
        
        rate_limit.increment_count()
        assert rate_limit.submission_count == 1
        
        rate_limit.increment_count()
        assert rate_limit.submission_count == 2
    
    async def test_rate_limit_create_for_today(self, test_session):
        """Test create_for_today class method."""
        user = User(telegram_id=123456789)
        test_session.add(user)
        await test_session.flush()
        
        rate_limit = RateLimit.create_for_today(user.id)
        assert rate_limit.user_id == user.id
        assert rate_limit.submission_date == date.today()
        assert rate_limit.submission_count == 0
        assert rate_limit.is_today is True
    
    async def test_rate_limit_user_relationship(self, test_session):
        """Test relationship between rate limit and user."""
        from sqlalchemy.orm import selectinload
        from sqlalchemy import select
        
        user = User(telegram_id=123456789)
        test_session.add(user)
        await test_session.flush()
        
        rate_limit = RateLimit(
            user_id=user.id,
            submission_date=date.today(),
            submission_count=1
        )
        test_session.add(rate_limit)
        await test_session.commit()
        
        # Reload user with rate_limits to test relationship
        result = await test_session.execute(
            select(User).options(selectinload(User.rate_limits)).where(User.id == user.id)
        )
        user_with_rate_limits = result.scalar_one()
        
        # Test relationship
        assert rate_limit.user.telegram_id == 123456789
        assert len(user_with_rate_limits.rate_limits) == 1
        assert user_with_rate_limits.rate_limits[0].id == rate_limit.id


# Run tests if this file is executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])