"""
Load tests for database operations under concurrent access.
Tests database performance and consistency under high load.
"""

import pytest
import asyncio
import time
import random
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, date, timedelta
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, OperationalError

from src.models.user import User
from src.models.submission import Submission, TaskType, ProcessingStatus
from src.models.assessment import Assessment
from src.models.rate_limit import RateLimit
from src.repositories.user_repository import UserRepository
from src.repositories.submission_repository import SubmissionRepository
from src.repositories.assessment_repository import AssessmentRepository
from src.repositories.rate_limit_repository import RateLimitRepository
from tests.test_data.ielts_samples import IELTSTestData


class TestDatabaseLoadTesting:
    """Test database operations under concurrent load."""
    
    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.close = AsyncMock()
        return session
    
    @pytest.fixture
    def mock_repositories(self, mock_session):
        """Create mock repositories."""
        return {
            'user_repo': UserRepository(mock_session),
            'submission_repo': SubmissionRepository(mock_session),
            'assessment_repo': AssessmentRepository(mock_session),
            'rate_limit_repo': RateLimitRepository(mock_session)
        }
    
    def create_test_users(self, count: int) -> List[User]:
        """Create test user objects."""
        users = []
        for i in range(count):
            user = User(
                id=i + 1,
                telegram_id=10000 + i,
                username=f"testuser{i}",
                first_name=f"User{i}",
                created_at=datetime.now(),
                is_pro=i % 10 == 0,  # Every 10th user is pro
                daily_submissions=0,
                last_submission_date=date.today()
            )
            users.append(user)
        return users
    
    def create_test_submissions(self, users: List[User], count_per_user: int = 3) -> List[Submission]:
        """Create test submission objects."""
        submissions = []
        samples = IELTSTestData.get_all_samples()
        
        submission_id = 1
        for user in users:
            for i in range(count_per_user):
                sample = samples[i % len(samples)]
                if sample.task_type in ['task_1', 'task_2']:
                    task_type = TaskType.TASK_1 if sample.task_type == 'task_1' else TaskType.TASK_2
                    
                    submission = Submission(
                        id=submission_id,
                        user_id=user.id,
                        text=sample.text,
                        task_type=task_type,
                        word_count=sample.word_count,
                        submitted_at=datetime.now() - timedelta(days=random.randint(0, 30)),
                        processing_status=ProcessingStatus.COMPLETED
                    )
                    submissions.append(submission)
                    submission_id += 1
        
        return submissions
    
    def create_test_assessments(self, submissions: List[Submission]) -> List[Assessment]:
        """Create test assessment objects."""
        assessments = []
        
        for i, submission in enumerate(submissions):
            assessment = Assessment(
                id=i + 1,
                submission_id=submission.id,
                task_achievement_score=random.uniform(4.0, 9.0),
                coherence_cohesion_score=random.uniform(4.0, 9.0),
                lexical_resource_score=random.uniform(4.0, 9.0),
                grammatical_accuracy_score=random.uniform(4.0, 9.0),
                overall_band_score=random.uniform(4.0, 9.0),
                detailed_feedback=f"Assessment feedback for submission {submission.id}",
                improvement_suggestions='["Suggestion 1", "Suggestion 2", "Suggestion 3"]',
                assessed_at=datetime.now()
            )
            assessments.append(assessment)
        
        return assessments
    
    @pytest.mark.asyncio
    async def test_concurrent_user_creation(self, mock_repositories):
        """Test concurrent user creation operations."""
        
        user_repo = mock_repositories['user_repo']
        test_users = self.create_test_users(50)
        
        # Mock successful user creation
        created_users = []
        async def mock_create_user(**kwargs):
            user = User(**kwargs)
            user.id = len(created_users) + 1
            created_users.append(user)
            return user
        
        user_repo.create = AsyncMock(side_effect=mock_create_user)
        
        # Create users concurrently
        tasks = []
        for user in test_users:
            task = user_repo.create(
                telegram_id=user.telegram_id,
                username=user.username,
                first_name=user.first_name,
                is_pro=user.is_pro
            )
            tasks.append(task)
        
        # Execute concurrently
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Verify results
        successful_results = [r for r in results if isinstance(r, User)]
        failed_results = [r for r in results if isinstance(r, Exception)]
        
        assert len(successful_results) == len(test_users), f"Expected {len(test_users)} successful creations"
        assert len(failed_results) == 0, f"Unexpected failures: {failed_results}"
        
        # Verify performance
        total_time = end_time - start_time
        assert total_time < 2.0, f"Concurrent user creation took too long: {total_time:.2f}s"
        
        # Verify all users were created
        assert len(created_users) == len(test_users)
        
        print(f"✅ Concurrent user creation: {len(test_users)} users in {total_time:.2f}s")
    
    @pytest.mark.asyncio
    async def test_concurrent_submission_creation(self, mock_repositories):
        """Test concurrent submission creation operations."""
        
        submission_repo = mock_repositories['submission_repo']
        test_users = self.create_test_users(20)
        test_submissions = self.create_test_submissions(test_users, 2)
        
        # Mock successful submission creation
        created_submissions = []
        async def mock_create_submission(**kwargs):
            submission = Submission(**kwargs)
            submission.id = len(created_submissions) + 1
            created_submissions.append(submission)
            return submission
        
        submission_repo.create = AsyncMock(side_effect=mock_create_submission)
        
        # Create submissions concurrently
        tasks = []
        for submission in test_submissions:
            task = submission_repo.create(
                user_id=submission.user_id,
                text=submission.text,
                task_type=submission.task_type,
                word_count=submission.word_count
            )
            tasks.append(task)
        
        # Execute concurrently
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Verify results
        successful_results = [r for r in results if isinstance(r, Submission)]
        failed_results = [r for r in results if isinstance(r, Exception)]
        
        assert len(successful_results) == len(test_submissions)
        assert len(failed_results) == 0, f"Unexpected failures: {failed_results}"
        
        # Verify performance
        total_time = end_time - start_time
        assert total_time < 3.0, f"Concurrent submission creation took too long: {total_time:.2f}s"
        
        print(f"✅ Concurrent submission creation: {len(test_submissions)} submissions in {total_time:.2f}s")
    
    @pytest.mark.asyncio
    async def test_concurrent_read_operations(self, mock_repositories):
        """Test concurrent read operations performance."""
        
        user_repo = mock_repositories['user_repo']
        submission_repo = mock_repositories['submission_repo']
        assessment_repo = mock_repositories['assessment_repo']
        
        test_users = self.create_test_users(30)
        test_submissions = self.create_test_submissions(test_users, 3)
        test_assessments = self.create_test_assessments(test_submissions)
        
        # Mock read operations
        user_repo.get_by_telegram_id = AsyncMock(side_effect=lambda tid: next(
            (u for u in test_users if u.telegram_id == tid), None
        ))
        
        submission_repo.get_by_user_id = AsyncMock(side_effect=lambda uid: [
            s for s in test_submissions if s.user_id == uid
        ])
        
        assessment_repo.get_by_submission_id = AsyncMock(side_effect=lambda sid: next(
            (a for a in test_assessments if a.submission_id == sid), None
        ))
        
        # Create concurrent read tasks
        read_tasks = []
        
        # User lookups
        for user in test_users[:15]:  # Test subset
            read_tasks.append(user_repo.get_by_telegram_id(user.telegram_id))
        
        # Submission lookups
        for user in test_users[:10]:
            read_tasks.append(submission_repo.get_by_user_id(user.id))
        
        # Assessment lookups
        for submission in test_submissions[:20]:
            read_tasks.append(assessment_repo.get_by_submission_id(submission.id))
        
        # Execute concurrent reads
        start_time = time.time()
        results = await asyncio.gather(*read_tasks, return_exceptions=True)
        end_time = time.time()
        
        # Verify results
        failed_results = [r for r in results if isinstance(r, Exception)]
        assert len(failed_results) == 0, f"Read operation failures: {failed_results}"
        
        # Verify performance
        total_time = end_time - start_time
        assert total_time < 1.0, f"Concurrent reads took too long: {total_time:.2f}s"
        
        print(f"✅ Concurrent read operations: {len(read_tasks)} reads in {total_time:.2f}s")
    
    @pytest.mark.asyncio
    async def test_concurrent_rate_limit_operations(self, mock_repositories):
        """Test concurrent rate limit operations."""
        
        rate_limit_repo = mock_repositories['rate_limit_repo']
        test_users = self.create_test_users(25)
        
        # Mock rate limit operations
        rate_limits = {}
        
        async def mock_get_daily_count(user_id: int, target_date: date = None):
            key = (user_id, target_date or date.today())
            return rate_limits.get(key, 0)
        
        async def mock_increment_count(user_id: int, target_date: date = None):
            key = (user_id, target_date or date.today())
            rate_limits[key] = rate_limits.get(key, 0) + 1
            return rate_limits[key]
        
        rate_limit_repo.get_daily_submission_count = AsyncMock(side_effect=mock_get_daily_count)
        rate_limit_repo.increment_daily_count = AsyncMock(side_effect=mock_increment_count)
        
        # Create concurrent rate limit operations
        tasks = []
        
        # Mix of get and increment operations
        for user in test_users:
            # Each user: check current count, then increment multiple times
            tasks.append(rate_limit_repo.get_daily_submission_count(user.id))
            
            for _ in range(3):  # 3 increments per user
                tasks.append(rate_limit_repo.increment_daily_count(user.id))
        
        # Execute concurrently
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Verify results
        failed_results = [r for r in results if isinstance(r, Exception)]
        assert len(failed_results) == 0, f"Rate limit operation failures: {failed_results}"
        
        # Verify final counts are correct
        for user in test_users:
            final_count = await rate_limit_repo.get_daily_submission_count(user.id)
            assert final_count == 3, f"Expected count 3 for user {user.id}, got {final_count}"
        
        # Verify performance
        total_time = end_time - start_time
        assert total_time < 2.0, f"Concurrent rate limit operations took too long: {total_time:.2f}s"
        
        print(f"✅ Concurrent rate limit operations: {len(tasks)} operations in {total_time:.2f}s")
    
    @pytest.mark.asyncio
    async def test_mixed_read_write_operations(self, mock_repositories):
        """Test mixed read and write operations under load."""
        
        user_repo = mock_repositories['user_repo']
        submission_repo = mock_repositories['submission_repo']
        assessment_repo = mock_repositories['assessment_repo']
        
        test_users = self.create_test_users(15)
        existing_submissions = self.create_test_submissions(test_users[:10], 2)
        
        # Mock repositories
        created_users = list(test_users[:10])  # Some users already exist
        created_submissions = list(existing_submissions)
        created_assessments = []
        
        async def mock_create_user(**kwargs):
            user = User(**kwargs)
            user.id = len(created_users) + 1
            created_users.append(user)
            await asyncio.sleep(0.01)  # Simulate DB delay
            return user
        
        async def mock_get_user(telegram_id):
            await asyncio.sleep(0.005)  # Simulate DB delay
            return next((u for u in created_users if u.telegram_id == telegram_id), None)
        
        async def mock_create_submission(**kwargs):
            submission = Submission(**kwargs)
            submission.id = len(created_submissions) + 1
            created_submissions.append(submission)
            await asyncio.sleep(0.01)  # Simulate DB delay
            return submission
        
        async def mock_get_submissions(user_id):
            await asyncio.sleep(0.005)  # Simulate DB delay
            return [s for s in created_submissions if s.user_id == user_id]
        
        async def mock_create_assessment(**kwargs):
            assessment = Assessment(**kwargs)
            assessment.id = len(created_assessments) + 1
            created_assessments.append(assessment)
            await asyncio.sleep(0.01)  # Simulate DB delay
            return assessment
        
        user_repo.create = AsyncMock(side_effect=mock_create_user)
        user_repo.get_by_telegram_id = AsyncMock(side_effect=mock_get_user)
        submission_repo.create = AsyncMock(side_effect=mock_create_submission)
        submission_repo.get_by_user_id = AsyncMock(side_effect=mock_get_submissions)
        assessment_repo.create = AsyncMock(side_effect=mock_create_assessment)
        
        # Create mixed operations
        tasks = []
        
        # Create new users
        for user in test_users[10:]:  # New users
            tasks.append(user_repo.create(
                telegram_id=user.telegram_id,
                username=user.username,
                first_name=user.first_name
            ))
        
        # Read existing users
        for user in test_users[:10]:
            tasks.append(user_repo.get_by_telegram_id(user.telegram_id))
        
        # Create new submissions
        for user in test_users[5:15]:  # Mix of existing and new users
            sample = IELTSTestData.get_task2_samples()[0]
            tasks.append(submission_repo.create(
                user_id=user.id,
                text=sample.text,
                task_type=TaskType.TASK_2,
                word_count=sample.word_count
            ))
        
        # Read existing submissions
        for user in test_users[:8]:
            tasks.append(submission_repo.get_by_user_id(user.id))
        
        # Create assessments
        for submission in existing_submissions[:10]:
            tasks.append(assessment_repo.create(
                submission_id=submission.id,
                task_achievement_score=7.0,
                coherence_cohesion_score=6.5,
                lexical_resource_score=7.5,
                grammatical_accuracy_score=6.0,
                overall_band_score=6.8,
                detailed_feedback="Good essay",
                improvement_suggestions='["Improve grammar", "Use more examples"]'
            ))
        
        # Execute all operations concurrently
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Verify results
        failed_results = [r for r in results if isinstance(r, Exception)]
        assert len(failed_results) == 0, f"Mixed operation failures: {failed_results}"
        
        # Verify performance
        total_time = end_time - start_time
        assert total_time < 5.0, f"Mixed operations took too long: {total_time:.2f}s"
        
        print(f"✅ Mixed read/write operations: {len(tasks)} operations in {total_time:.2f}s")
    
    @pytest.mark.asyncio
    async def test_database_connection_pool_exhaustion(self, mock_repositories):
        """Test behavior when database connection pool is exhausted."""
        
        user_repo = mock_repositories['user_repo']
        
        # Mock connection pool exhaustion
        connection_count = 0
        max_connections = 10
        
        async def mock_create_with_connection_limit(**kwargs):
            nonlocal connection_count
            connection_count += 1
            
            if connection_count > max_connections:
                raise OperationalError("Connection pool exhausted", None, None)
            
            try:
                await asyncio.sleep(0.1)  # Simulate long-running operation
                user = User(**kwargs)
                user.id = connection_count
                return user
            finally:
                connection_count -= 1
        
        user_repo.create = AsyncMock(side_effect=mock_create_with_connection_limit)
        
        # Create more tasks than connection pool can handle
        tasks = []
        for i in range(20):  # More than max_connections
            tasks.append(user_repo.create(
                telegram_id=20000 + i,
                username=f"pooltest{i}",
                first_name=f"PoolTest{i}"
            ))
        
        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify some operations succeeded and some failed appropriately
        successful_results = [r for r in results if isinstance(r, User)]
        failed_results = [r for r in results if isinstance(r, Exception)]
        
        assert len(successful_results) <= max_connections, f"Too many successful connections: {len(successful_results)}"
        assert len(failed_results) > 0, "Expected some connection pool failures"
        
        # Verify error types
        pool_errors = [r for r in failed_results if isinstance(r, OperationalError)]
        assert len(pool_errors) > 0, "Expected connection pool errors"
        
        print(f"✅ Connection pool test: {len(successful_results)} succeeded, {len(failed_results)} failed appropriately")
    
    @pytest.mark.asyncio
    async def test_transaction_rollback_under_load(self, mock_repositories):
        """Test transaction rollback behavior under concurrent load."""
        
        submission_repo = mock_repositories['submission_repo']
        
        # Mock transaction failures
        failure_count = 0
        
        async def mock_create_with_failures(**kwargs):
            nonlocal failure_count
            failure_count += 1
            
            # Every 4th operation fails
            if failure_count % 4 == 0:
                raise IntegrityError("Constraint violation", None, None)
            
            submission = Submission(**kwargs)
            submission.id = failure_count
            return submission
        
        submission_repo.create = AsyncMock(side_effect=mock_create_with_failures)
        
        # Create concurrent operations
        tasks = []
        sample = IELTSTestData.get_task1_samples()[0]
        
        for i in range(20):
            tasks.append(submission_repo.create(
                user_id=i + 1,
                text=sample.text,
                task_type=TaskType.TASK_1,
                word_count=sample.word_count
            ))
        
        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify results
        successful_results = [r for r in results if isinstance(r, Submission)]
        failed_results = [r for r in results if isinstance(r, Exception)]
        
        # Should have some successes and some failures
        assert len(successful_results) > 0, "Expected some successful operations"
        assert len(failed_results) > 0, "Expected some failed operations"
        
        # Verify failure types
        integrity_errors = [r for r in failed_results if isinstance(r, IntegrityError)]
        assert len(integrity_errors) > 0, "Expected integrity constraint violations"
        
        print(f"✅ Transaction rollback test: {len(successful_results)} succeeded, {len(failed_results)} failed")
    
    @pytest.mark.asyncio
    async def test_large_dataset_operations(self, mock_repositories):
        """Test operations with large datasets."""
        
        user_repo = mock_repositories['user_repo']
        submission_repo = mock_repositories['submission_repo']
        
        # Create large dataset
        large_user_count = 100
        test_users = self.create_test_users(large_user_count)
        
        # Mock bulk operations
        created_users = []
        user_submissions = {}
        
        async def mock_bulk_create_users(users_data):
            await asyncio.sleep(0.1)  # Simulate bulk operation delay
            for i, user_data in enumerate(users_data):
                user = User(**user_data)
                user.id = len(created_users) + 1
                created_users.append(user)
            return created_users[-len(users_data):]
        
        async def mock_get_user_submissions(user_id, limit=None):
            await asyncio.sleep(0.01)  # Simulate query delay
            submissions = user_submissions.get(user_id, [])
            return submissions[:limit] if limit else submissions
        
        # Mock repository methods
        user_repo.bulk_create = AsyncMock(side_effect=mock_bulk_create_users)
        submission_repo.get_by_user_id = AsyncMock(side_effect=mock_get_user_submissions)
        
        # Prepare user data for bulk creation
        users_data = []
        for user in test_users:
            users_data.append({
                'telegram_id': user.telegram_id,
                'username': user.username,
                'first_name': user.first_name,
                'is_pro': user.is_pro
            })
        
        # Create users in batches
        batch_size = 20
        batches = [users_data[i:i + batch_size] for i in range(0, len(users_data), batch_size)]
        
        start_time = time.time()
        
        # Execute batch operations concurrently
        batch_tasks = [user_repo.bulk_create(batch) for batch in batches]
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        
        end_time = time.time()
        
        # Verify batch results
        failed_batches = [r for r in batch_results if isinstance(r, Exception)]
        assert len(failed_batches) == 0, f"Batch operation failures: {failed_batches}"
        
        # Verify all users were created
        total_created = sum(len(batch_result) for batch_result in batch_results)
        assert total_created == large_user_count, f"Expected {large_user_count} users, got {total_created}"
        
        # Test concurrent reads on large dataset
        read_tasks = []
        for user in created_users[:50]:  # Test subset
            read_tasks.append(submission_repo.get_by_user_id(user.id, limit=10))
        
        read_start = time.time()
        read_results = await asyncio.gather(*read_tasks, return_exceptions=True)
        read_end = time.time()
        
        # Verify read results
        failed_reads = [r for r in read_results if isinstance(r, Exception)]
        assert len(failed_reads) == 0, f"Large dataset read failures: {failed_reads}"
        
        # Verify performance
        total_time = end_time - start_time
        read_time = read_end - read_start
        
        assert total_time < 3.0, f"Large dataset creation took too long: {total_time:.2f}s"
        assert read_time < 1.0, f"Large dataset reads took too long: {read_time:.2f}s"
        
        print(f"✅ Large dataset operations: {large_user_count} users created in {total_time:.2f}s, {len(read_tasks)} reads in {read_time:.2f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])