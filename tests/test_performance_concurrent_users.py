"""
Performance tests for concurrent user handling.
Tests the system's ability to handle multiple simultaneous users and requests.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any
import statistics

from src.services.evaluation_service import EvaluationService, EvaluationRequest, EvaluationResult
from src.services.user_service import UserService, UserProfile
from src.services.rate_limit_service import RateLimitService, RateLimitResult, RateLimitStatus
from src.services.ai_assessment_engine import AIAssessmentEngine, StructuredAssessment
from src.models.submission import TaskType
from tests.test_data.ielts_samples import IELTSTestData, MOCK_OPENAI_RESPONSES


class TestConcurrentUserHandling:
    """Test concurrent user handling and performance."""
    
    @pytest.fixture
    def mock_repositories(self):
        """Mock all repository dependencies."""
        return {
            'user_repo': AsyncMock(),
            'submission_repo': AsyncMock(),
            'assessment_repo': AsyncMock(),
            'rate_limit_repo': AsyncMock()
        }
    
    @pytest.fixture
    def mock_ai_engine(self):
        """Mock AI assessment engine with realistic delays."""
        engine = AsyncMock(spec=AIAssessmentEngine)
        
        async def mock_assess_with_delay(*args, **kwargs):
            # Simulate realistic AI API response time
            await asyncio.sleep(0.1)  # 100ms delay
            from src.services.ai_assessment_engine import RawAssessment
            return RawAssessment(
                content='{"task_achievement_score": 7.0, "coherence_cohesion_score": 6.5, "lexical_resource_score": 7.5, "grammatical_accuracy_score": 6.0, "overall_band_score": 6.5, "detailed_feedback": "Good essay", "improvement_suggestions": ["Work on grammar", "Expand vocabulary"], "score_justifications": {"task_achievement": "Good response"}}',
                usage_tokens=500,
                model_used="gpt-4"
            )
        
        engine.assess_writing.side_effect = mock_assess_with_delay
        
        engine.parse_response.return_value = StructuredAssessment(
            task_achievement_score=7.0,
            coherence_cohesion_score=6.5,
            lexical_resource_score=7.5,
            grammatical_accuracy_score=6.0,
            overall_band_score=6.5,
            detailed_feedback="Good essay with clear structure.",
            improvement_suggestions=["Work on grammar accuracy", "Expand vocabulary range"],
            score_justifications={
                "task_achievement": "Good response to the task",
                "coherence_cohesion": "Well organized",
                "lexical_resource": "Good vocabulary",
                "grammatical_accuracy": "Some errors present"
            }
        )
        
        engine.validate_scores.return_value = True
        return engine
    
    def create_test_users(self, count: int) -> List[UserProfile]:
        """Create test user profiles."""
        users = []
        for i in range(count):
            user = UserProfile(
                telegram_id=10000 + i,
                username=f"testuser{i}",
                first_name=f"User{i}",
                created_at=datetime.now(),
                is_pro=i % 5 == 0,  # Every 5th user is pro
                daily_submissions=0,
                last_submission_date=date.today(),
                total_submissions=i
            )
            users.append(user)
        return users
    
    def create_evaluation_service(self, mock_ai_engine, mock_repositories):
        """Create evaluation service with mocked dependencies."""
        return EvaluationService(
            ai_engine=mock_ai_engine,
            user_repo=mock_repositories['user_repo'],
            submission_repo=mock_repositories['submission_repo'],
            assessment_repo=mock_repositories['assessment_repo'],
            rate_limit_repo=mock_repositories['rate_limit_repo']
        )
    
    @pytest.mark.asyncio
    async def test_concurrent_evaluations_performance(self, mock_ai_engine, mock_repositories):
        """Test performance with multiple concurrent evaluations."""
        
        # Setup
        evaluation_service = self.create_evaluation_service(mock_ai_engine, mock_repositories)
        test_users = self.create_test_users(10)
        task2_samples = IELTSTestData.get_task2_samples()
        
        # Mock repository responses
        mock_repositories['user_repo'].get_by_id.side_effect = lambda user_id: next(
            (user for user in test_users if user.telegram_id == user_id), None
        )
        mock_repositories['rate_limit_repo'].get_daily_submission_count.return_value = 0
        mock_repositories['submission_repo'].create.return_value = MagicMock(id=1)
        mock_repositories['assessment_repo'].create.return_value = MagicMock(id=1)
        mock_repositories['rate_limit_repo'].increment_daily_count.return_value = None
        mock_repositories['submission_repo'].update_status.return_value = None
        
        # Create evaluation requests
        requests = []
        for i, user in enumerate(test_users):
            sample = task2_samples[i % len(task2_samples)]
            request = EvaluationRequest(
                user_id=user.telegram_id,
                text=sample.text,
                task_type=TaskType.TASK_2,
                force_task_type=True
            )
            requests.append(request)
        
        # Measure concurrent execution time
        start_time = time.time()
        
        # Execute all evaluations concurrently
        tasks = [evaluation_service.evaluate_writing(request) for request in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify results
        successful_results = [r for r in results if isinstance(r, EvaluationResult) and r.success]
        failed_results = [r for r in results if isinstance(r, Exception) or (isinstance(r, EvaluationResult) and not r.success)]
        
        # Performance assertions
        assert len(successful_results) == len(test_users), f"Expected {len(test_users)} successful results, got {len(successful_results)}"
        assert len(failed_results) == 0, f"Unexpected failures: {failed_results}"
        assert total_time < 2.0, f"Concurrent execution took too long: {total_time:.2f}s"
        
        # Verify all AI engine calls were made
        assert mock_ai_engine.assess_writing.call_count == len(test_users)
        
        print(f"✅ Concurrent evaluation performance: {len(test_users)} users in {total_time:.2f}s")
    
    @pytest.mark.asyncio
    async def test_rate_limiting_under_load(self, mock_ai_engine, mock_repositories):
        """Test rate limiting behavior under concurrent load."""
        
        evaluation_service = self.create_evaluation_service(mock_ai_engine, mock_repositories)
        
        # Create a single user making multiple requests
        user = UserProfile(
            telegram_id=12345,
            username="testuser",
            first_name="Test",
            created_at=datetime.now(),
            is_pro=False,
            daily_submissions=0,
            last_submission_date=date.today(),
            total_submissions=0
        )
        
        # Mock repository responses
        mock_repositories['user_repo'].get_by_id.return_value = user
        
        # Mock rate limiting - first 3 requests allowed, rest blocked
        call_count = 0
        def mock_rate_limit_check(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                return 0  # Allowed
            else:
                return 3  # At limit
        
        mock_repositories['rate_limit_repo'].get_daily_submission_count.side_effect = mock_rate_limit_check
        mock_repositories['submission_repo'].create.return_value = MagicMock(id=1)
        mock_repositories['assessment_repo'].create.return_value = MagicMock(id=1)
        mock_repositories['rate_limit_repo'].increment_daily_count.return_value = None
        mock_repositories['submission_repo'].update_status.return_value = None
        
        # Create 5 concurrent requests from the same user
        task2_sample = IELTSTestData.get_task2_samples()[0]
        requests = []
        for i in range(5):
            request = EvaluationRequest(
                user_id=user.telegram_id,
                text=task2_sample.text,
                task_type=TaskType.TASK_2,
                force_task_type=True
            )
            requests.append(request)
        
        # Execute concurrently
        tasks = [evaluation_service.evaluate_writing(request) for request in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify rate limiting worked
        successful_results = [r for r in results if isinstance(r, EvaluationResult) and r.success]
        rate_limited_results = [r for r in results if isinstance(r, EvaluationResult) and not r.success and "limit" in r.error_message.lower()]
        
        assert len(successful_results) == 3, f"Expected 3 successful results, got {len(successful_results)}"
        assert len(rate_limited_results) == 2, f"Expected 2 rate-limited results, got {len(rate_limited_results)}"
        
        print(f"✅ Rate limiting under load: {len(successful_results)} allowed, {len(rate_limited_results)} blocked")
    
    @pytest.mark.asyncio
    async def test_database_connection_pool_stress(self, mock_ai_engine, mock_repositories):
        """Test database connection handling under stress."""
        
        evaluation_service = self.create_evaluation_service(mock_ai_engine, mock_repositories)
        test_users = self.create_test_users(20)  # More users for stress test
        
        # Add delays to simulate database operations
        async def mock_db_operation(*args, **kwargs):
            await asyncio.sleep(0.01)  # 10ms database delay
            return MagicMock(id=1)
        
        mock_repositories['user_repo'].get_by_id.side_effect = lambda user_id: next(
            (user for user in test_users if user.telegram_id == user_id), None
        )
        mock_repositories['rate_limit_repo'].get_daily_submission_count.return_value = 0
        mock_repositories['submission_repo'].create.side_effect = mock_db_operation
        mock_repositories['assessment_repo'].create.side_effect = mock_db_operation
        mock_repositories['rate_limit_repo'].increment_daily_count.side_effect = mock_db_operation
        mock_repositories['submission_repo'].update_status.side_effect = mock_db_operation
        
        # Create evaluation requests
        task1_sample = IELTSTestData.get_task1_samples()[0]
        requests = []
        for user in test_users:
            request = EvaluationRequest(
                user_id=user.telegram_id,
                text=task1_sample.text,
                task_type=TaskType.TASK_1,
                force_task_type=True
            )
            requests.append(request)
        
        # Execute with high concurrency
        start_time = time.time()
        tasks = [evaluation_service.evaluate_writing(request) for request in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Verify all operations completed successfully
        successful_results = [r for r in results if isinstance(r, EvaluationResult) and r.success]
        failed_results = [r for r in results if isinstance(r, Exception)]
        
        assert len(successful_results) == len(test_users), f"Expected {len(test_users)} successful results, got {len(successful_results)}"
        assert len(failed_results) == 0, f"Database stress test failures: {failed_results}"
        
        # Verify reasonable performance under stress
        total_time = end_time - start_time
        assert total_time < 5.0, f"Database stress test took too long: {total_time:.2f}s"
        
        print(f"✅ Database stress test: {len(test_users)} operations in {total_time:.2f}s")
    
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, mock_ai_engine, mock_repositories):
        """Test memory usage doesn't grow excessively under load."""
        
        evaluation_service = self.create_evaluation_service(mock_ai_engine, mock_repositories)
        
        # Create many users for memory test
        test_users = self.create_test_users(50)
        
        # Mock repository responses
        mock_repositories['user_repo'].get_by_id.side_effect = lambda user_id: next(
            (user for user in test_users if user.telegram_id == user_id), None
        )
        mock_repositories['rate_limit_repo'].get_daily_submission_count.return_value = 0
        mock_repositories['submission_repo'].create.return_value = MagicMock(id=1)
        mock_repositories['assessment_repo'].create.return_value = MagicMock(id=1)
        mock_repositories['rate_limit_repo'].increment_daily_count.return_value = None
        mock_repositories['submission_repo'].update_status.return_value = None
        
        # Run multiple batches to test memory cleanup
        batch_size = 10
        batches = [test_users[i:i + batch_size] for i in range(0, len(test_users), batch_size)]
        
        task2_sample = IELTSTestData.get_task2_samples()[0]
        
        for batch_num, batch_users in enumerate(batches):
            # Create requests for this batch
            requests = []
            for user in batch_users:
                request = EvaluationRequest(
                    user_id=user.telegram_id,
                    text=task2_sample.text,
                    task_type=TaskType.TASK_2,
                    force_task_type=True
                )
                requests.append(request)
            
            # Execute batch
            tasks = [evaluation_service.evaluate_writing(request) for request in requests]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Verify batch completed successfully
            successful_results = [r for r in results if isinstance(r, EvaluationResult) and r.success]
            assert len(successful_results) == len(batch_users), f"Batch {batch_num} failed"
            
            # Force garbage collection between batches
            import gc
            gc.collect()
        
        print(f"✅ Memory test: Processed {len(test_users)} users in {len(batches)} batches")
    
    @pytest.mark.asyncio
    async def test_response_time_distribution(self, mock_ai_engine, mock_repositories):
        """Test response time distribution under concurrent load."""
        
        evaluation_service = self.create_evaluation_service(mock_ai_engine, mock_repositories)
        test_users = self.create_test_users(15)
        
        # Add variable delays to AI engine to simulate real-world conditions
        async def mock_assess_with_variable_delay(*args, **kwargs):
            import random
            delay = random.uniform(0.05, 0.2)  # 50-200ms delay
            await asyncio.sleep(delay)
            from src.services.ai_assessment_engine import RawAssessment
            return RawAssessment(
                content='{"task_achievement_score": 7.0, "coherence_cohesion_score": 6.5, "lexical_resource_score": 7.5, "grammatical_accuracy_score": 6.0, "overall_band_score": 6.5, "detailed_feedback": "Good essay", "improvement_suggestions": ["Work on grammar"], "score_justifications": {"task_achievement": "Good"}}',
                usage_tokens=500,
                model_used="gpt-4"
            )
        
        mock_ai_engine.assess_writing.side_effect = mock_assess_with_variable_delay
        
        # Mock repository responses
        mock_repositories['user_repo'].get_by_id.side_effect = lambda user_id: next(
            (user for user in test_users if user.telegram_id == user_id), None
        )
        mock_repositories['rate_limit_repo'].get_daily_submission_count.return_value = 0
        mock_repositories['submission_repo'].create.return_value = MagicMock(id=1)
        mock_repositories['assessment_repo'].create.return_value = MagicMock(id=1)
        mock_repositories['rate_limit_repo'].increment_daily_count.return_value = None
        mock_repositories['submission_repo'].update_status.return_value = None
        
        # Create evaluation requests
        task1_sample = IELTSTestData.get_task1_samples()[0]
        requests = []
        for user in test_users:
            request = EvaluationRequest(
                user_id=user.telegram_id,
                text=task1_sample.text,
                task_type=TaskType.TASK_1,
                force_task_type=True
            )
            requests.append(request)
        
        # Measure individual response times
        response_times = []
        
        async def timed_evaluation(request):
            start_time = time.time()
            result = await evaluation_service.evaluate_writing(request)
            end_time = time.time()
            response_times.append(end_time - start_time)
            return result
        
        # Execute all evaluations concurrently
        tasks = [timed_evaluation(request) for request in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze response time distribution
        successful_results = [r for r in results if isinstance(r, EvaluationResult) and r.success]
        assert len(successful_results) == len(test_users)
        
        # Calculate statistics
        avg_response_time = statistics.mean(response_times)
        median_response_time = statistics.median(response_times)
        max_response_time = max(response_times)
        min_response_time = min(response_times)
        
        # Performance assertions
        assert avg_response_time < 1.0, f"Average response time too high: {avg_response_time:.2f}s"
        assert max_response_time < 2.0, f"Max response time too high: {max_response_time:.2f}s"
        assert min_response_time > 0.05, f"Min response time suspiciously low: {min_response_time:.2f}s"
        
        print(f"✅ Response time distribution:")
        print(f"   Average: {avg_response_time:.3f}s")
        print(f"   Median: {median_response_time:.3f}s")
        print(f"   Min: {min_response_time:.3f}s")
        print(f"   Max: {max_response_time:.3f}s")
    
    @pytest.mark.asyncio
    async def test_error_handling_under_concurrent_load(self, mock_ai_engine, mock_repositories):
        """Test error handling when some operations fail under concurrent load."""
        
        evaluation_service = self.create_evaluation_service(mock_ai_engine, mock_repositories)
        test_users = self.create_test_users(10)
        
        # Mock some operations to fail
        call_count = 0
        async def mock_assess_with_failures(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:  # Every 3rd call fails
                raise Exception("Simulated AI API failure")
            
            await asyncio.sleep(0.1)
            from src.services.ai_assessment_engine import RawAssessment
            return RawAssessment(
                content='{"task_achievement_score": 7.0, "coherence_cohesion_score": 6.5, "lexical_resource_score": 7.5, "grammatical_accuracy_score": 6.0, "overall_band_score": 6.5, "detailed_feedback": "Good essay", "improvement_suggestions": ["Work on grammar"], "score_justifications": {"task_achievement": "Good"}}',
                usage_tokens=500,
                model_used="gpt-4"
            )
        
        mock_ai_engine.assess_writing.side_effect = mock_assess_with_failures
        
        # Mock repository responses
        mock_repositories['user_repo'].get_by_id.side_effect = lambda user_id: next(
            (user for user in test_users if user.telegram_id == user_id), None
        )
        mock_repositories['rate_limit_repo'].get_daily_submission_count.return_value = 0
        mock_repositories['submission_repo'].create.return_value = MagicMock(id=1)
        mock_repositories['assessment_repo'].create.return_value = MagicMock(id=1)
        mock_repositories['rate_limit_repo'].increment_daily_count.return_value = None
        mock_repositories['submission_repo'].update_status.return_value = None
        
        # Create evaluation requests
        task2_sample = IELTSTestData.get_task2_samples()[0]
        requests = []
        for user in test_users:
            request = EvaluationRequest(
                user_id=user.telegram_id,
                text=task2_sample.text,
                task_type=TaskType.TASK_2,
                force_task_type=True
            )
            requests.append(request)
        
        # Execute all evaluations concurrently
        tasks = [evaluation_service.evaluate_writing(request) for request in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        successful_results = [r for r in results if isinstance(r, EvaluationResult) and r.success]
        failed_results = [r for r in results if isinstance(r, EvaluationResult) and not r.success]
        exception_results = [r for r in results if isinstance(r, Exception)]
        
        # Verify error handling
        expected_failures = len(test_users) // 3  # Every 3rd should fail
        expected_successes = len(test_users) - expected_failures
        
        assert len(successful_results) == expected_successes, f"Expected {expected_successes} successes, got {len(successful_results)}"
        assert len(failed_results) == expected_failures, f"Expected {expected_failures} failures, got {len(failed_results)}"
        assert len(exception_results) == 0, f"Unexpected exceptions: {exception_results}"
        
        # Verify failed results have proper error messages
        for failed_result in failed_results:
            assert "Assessment failed" in failed_result.error_message
        
        print(f"✅ Error handling under load: {len(successful_results)} successes, {len(failed_results)} handled failures")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])