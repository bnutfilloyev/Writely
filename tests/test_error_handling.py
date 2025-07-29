"""
Tests for comprehensive error handling and user experience features
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from src.exceptions import (
    ErrorHandler, ErrorContext, ErrorSeverity,
    ValidationError, RateLimitError, DatabaseError, 
    AIServiceError, ConfigurationError
)
from src.services.ai_assessment_engine import AIAssessmentEngine, TaskType
from src.services.evaluation_service import EvaluationService, EvaluationRequest
from src.services.service_monitor import ServiceMonitor, ServiceStatus


class TestErrorHandler:
    """Test the centralized error handler"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.error_handler = ErrorHandler()
        self.context = ErrorContext(
            user_id=12345,
            username="testuser",
            message_text="test message",
            handler_name="test_handler",
            timestamp=datetime.now()
        )
    
    def test_handle_validation_error(self):
        """Test handling of validation errors"""
        error = ValidationError(
            message="Text too short",
            validation_type="length",
            user_message="Please provide at least 50 words",
            suggestions=["Write more content", "Check word count"]
        )
        
        response = self.error_handler.handle_error(error, self.context)
        
        assert "Please provide at least 50 words" in response.message
        assert "Suggestions:" in response.message
        assert "Write more content" in response.message
        assert response.show_retry_button is True
        assert response.keyboard is not None
    
    def test_handle_rate_limit_error(self):
        """Test handling of rate limit errors"""
        error = RateLimitError(
            message="Daily limit reached",
            limit_type="daily_submissions",
            current_count=3,
            limit=3,
            reset_time="tomorrow at midnight"
        )
        
        response = self.error_handler.handle_error(error, self.context)
        
        assert "Daily limit reached" in response.message
        assert "tomorrow at midnight" in response.message
        assert response.keyboard is not None
        # Should have upgrade option
        keyboard_text = str(response.keyboard)
        assert "Upgrade to Pro" in keyboard_text
    
    def test_handle_database_error_recoverable(self):
        """Test handling of recoverable database errors"""
        error = DatabaseError(
            message="Connection timeout",
            operation="get_user",
            table="users",
            recoverable=True
        )
        
        response = self.error_handler.handle_error(error, self.context)
        
        # Should either suggest trying again or indicate graceful degradation
        assert ("try again" in response.message.lower() or 
                "limited" in response.message.lower())
        assert response.show_retry_button is True
    
    def test_handle_database_error_non_recoverable(self):
        """Test handling of non-recoverable database errors"""
        error = DatabaseError(
            message="Database corrupted",
            operation="create_table",
            table="users",
            recoverable=False
        )
        
        response = self.error_handler.handle_error(error, self.context)
        
        assert response.show_support_button is True
        assert response.show_retry_button is False
    
    def test_handle_ai_service_error(self):
        """Test handling of AI service errors"""
        error = AIServiceError(
            message="OpenAI API timeout",
            service_type="openai",
            error_type="timeout",
            retry_after=60,
            recoverable=True
        )
        
        response = self.error_handler.handle_error(error, self.context)
        
        assert "Assessment service temporarily unavailable" in response.message
        assert "60 seconds" in response.message
        assert response.show_retry_button is True
    
    def test_handle_configuration_error(self):
        """Test handling of configuration errors"""
        error = ConfigurationError(
            message="API key missing",
            config_key="OPENAI_API_KEY"
        )
        
        response = self.error_handler.handle_error(error, self.context)
        
        assert "maintenance" in response.message.lower()
        assert response.show_support_button is True
        assert response.show_retry_button is False
    
    def test_circuit_breaker_activation(self):
        """Test circuit breaker activation after repeated errors"""
        error = AIServiceError(
            message="API error",
            service_type="openai",
            error_type="api_error"
        )
        
        # Trigger multiple errors to activate circuit breaker
        for _ in range(6):
            response = self.error_handler.handle_error(error, self.context)
        
        # Last response should indicate circuit breaker activation
        assert "high load" in response.message.lower()
        assert response.show_retry_button is False
    
    def test_unknown_error_handling(self):
        """Test handling of unknown errors"""
        error = ValueError("Unknown error occurred")
        
        response = self.error_handler.handle_error(
            error, self.context, 
            fallback_message="Custom fallback message"
        )
        
        assert "Custom fallback message" in response.message
        assert response.show_retry_button is True
    
    @pytest.mark.asyncio
    async def test_processing_message_handling(self):
        """Test processing message creation and cleanup"""
        mock_message = Mock()
        mock_message.answer = AsyncMock(return_value=Mock())
        
        # Test sending processing message
        processing_msg = await self.error_handler.send_processing_message(
            mock_message, "Processing..."
        )
        
        mock_message.answer.assert_called_once_with("Processing...")
        
        # Test updating processing message
        processing_msg.edit_text = AsyncMock()
        await self.error_handler.update_processing_message(
            processing_msg, "Updated status"
        )
        
        processing_msg.edit_text.assert_called_once_with("Updated status")
        
        # Test cleanup
        processing_msg.delete = AsyncMock()
        await self.error_handler.cleanup_processing_message(processing_msg)
        
        processing_msg.delete.assert_called_once()


class TestAIAssessmentEngineErrorHandling:
    """Test error handling in AI assessment engine"""
    
    def setup_method(self):
        """Set up test fixtures"""
        with patch('src.services.ai_assessment_engine.AsyncOpenAI'):
            self.engine = AIAssessmentEngine(api_key="test_key")
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_prevents_calls(self):
        """Test that circuit breaker prevents API calls when open"""
        # Manually set circuit breaker to open state
        self.engine.circuit_breaker_failures = 10
        
        with pytest.raises(AIServiceError) as exc_info:
            await self.engine.assess_writing("test text", TaskType.TASK_1)
        
        assert exc_info.value.error_type == "circuit_breaker"
        assert exc_info.value.retry_after == 300
    
    @pytest.mark.asyncio
    async def test_rate_limit_error_handling(self):
        """Test handling of OpenAI rate limit errors"""
        import openai
        
        # Create a mock response object
        mock_response = Mock()
        mock_response.request = Mock()
        
        # Mock the client directly
        with patch.object(self.engine, 'client') as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=openai.RateLimitError("Rate limit exceeded", response=mock_response, body=None)
            )
            
            with pytest.raises(AIServiceError) as exc_info:
                await self.engine.assess_writing("test text", TaskType.TASK_1)
            
            assert exc_info.value.error_type == "rate_limit"
            assert exc_info.value.recoverable is True
    
    @pytest.mark.asyncio
    async def test_authentication_error_handling(self):
        """Test handling of OpenAI authentication errors"""
        import openai
        
        # Create a mock response object
        mock_response = Mock()
        mock_response.request = Mock()
        
        # Mock the client directly
        with patch.object(self.engine, 'client') as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=openai.AuthenticationError("Invalid API key", response=mock_response, body=None)
            )
            
            with pytest.raises(AIServiceError) as exc_info:
                await self.engine.assess_writing("test text", TaskType.TASK_1)
            
            assert exc_info.value.error_type == "auth"
            assert exc_info.value.recoverable is False
    
    @pytest.mark.asyncio
    async def test_timeout_error_handling(self):
        """Test handling of timeout errors"""
        # Mock the client to raise TimeoutError
        with patch.object(self.engine, 'client') as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=asyncio.TimeoutError("Request timed out")
            )
            
            with pytest.raises(AIServiceError) as exc_info:
                await self.engine.assess_writing("test text", TaskType.TASK_1)
            
            assert exc_info.value.error_type == "timeout"
            assert exc_info.value.retry_after == 60
    
    def test_invalid_json_response_handling(self):
        """Test handling of invalid JSON responses"""
        invalid_response = "This is not valid JSON"
        
        with pytest.raises(AIServiceError) as exc_info:
            self.engine.parse_response(invalid_response)
        
        assert exc_info.value.error_type == "parse_error"
        assert exc_info.value.recoverable is True
    
    def test_missing_fields_response_handling(self):
        """Test handling of responses with missing required fields"""
        incomplete_response = '{"task_achievement_score": 7.0}'
        
        with pytest.raises(AIServiceError) as exc_info:
            self.engine.parse_response(incomplete_response)
        
        assert exc_info.value.error_type == "format_error"
        assert exc_info.value.recoverable is True


class TestEvaluationServiceErrorHandling:
    """Test error handling in evaluation service"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_ai_engine = Mock()
        self.mock_user_repo = Mock()
        self.mock_submission_repo = Mock()
        self.mock_assessment_repo = Mock()
        self.mock_rate_limit_repo = Mock()
        
        self.service = EvaluationService(
            ai_engine=self.mock_ai_engine,
            user_repo=self.mock_user_repo,
            submission_repo=self.mock_submission_repo,
            assessment_repo=self.mock_assessment_repo,
            rate_limit_repo=self.mock_rate_limit_repo
        )
    
    @pytest.mark.asyncio
    async def test_rate_limit_check_user_not_found(self):
        """Test rate limit check when user is not found"""
        self.mock_user_repo.get_by_id = AsyncMock(return_value=None)
        
        with pytest.raises(DatabaseError) as exc_info:
            await self.service.check_rate_limit(12345)
        
        assert "User 12345 not found" in str(exc_info.value)
        assert exc_info.value.operation == "get_user"
    
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self):
        """Test rate limit exceeded scenario"""
        mock_user = Mock()
        mock_user.is_pro = False
        self.mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)
        self.mock_rate_limit_repo.get_daily_submission_count = AsyncMock(return_value=3)
        
        with pytest.raises(RateLimitError) as exc_info:
            await self.service.check_rate_limit(12345)
        
        assert exc_info.value.limit_type == "daily_submissions"
        assert exc_info.value.current_count == 3
        assert exc_info.value.limit == 3
    
    @pytest.mark.asyncio
    async def test_evaluation_with_database_failure_graceful_degradation(self):
        """Test evaluation continues with database failures"""
        # Mock successful validation and task detection
        self.service.text_validator.validate_submission = Mock(
            return_value=Mock(is_valid=True, word_count=100, errors=[], warnings=[])
        )
        self.service.task_detector.detect_task_type = Mock(
            return_value=Mock(detected_type=TaskType.TASK_1, requires_clarification=False)
        )
        
        # Mock user and rate limit success
        mock_user = Mock()
        mock_user.is_pro = False
        self.mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)
        self.mock_rate_limit_repo.get_daily_submission_count = AsyncMock(return_value=0)
        
        # Mock submission creation success
        mock_submission = Mock()
        mock_submission.id = 123
        self.mock_submission_repo.create = AsyncMock(return_value=mock_submission)
        
        # Mock AI assessment success
        mock_assessment = Mock()
        mock_assessment.task_achievement_score = 7.0
        mock_assessment.coherence_cohesion_score = 7.0
        mock_assessment.lexical_resource_score = 7.0
        mock_assessment.grammatical_accuracy_score = 7.0
        mock_assessment.overall_band_score = 7.0
        mock_assessment.detailed_feedback = "Good work"
        mock_assessment.improvement_suggestions = ["Keep practicing"]
        mock_assessment.score_justifications = {"task_achievement": "Well done"}
        
        self.mock_ai_engine.assess_writing = AsyncMock(return_value=Mock())
        self.mock_ai_engine.parse_response = Mock(return_value=mock_assessment)
        self.mock_ai_engine.validate_scores = Mock(return_value=True)
        
        # Mock assessment saving failure (should not fail evaluation)
        self.mock_assessment_repo.create = AsyncMock(
            side_effect=DatabaseError("DB error", "create_assessment")
        )
        
        # Mock rate limit increment failure (should not fail evaluation)
        self.mock_rate_limit_repo.increment_daily_count = AsyncMock(
            side_effect=DatabaseError("DB error", "increment_count")
        )
        
        request = EvaluationRequest(
            user_id=12345,
            text="This is a test writing sample for Task 1.",
            task_type=TaskType.TASK_1,
            force_task_type=True
        )
        
        result = await self.service.evaluate_writing(request)
        
        # Evaluation should succeed despite database failures
        assert result.success is True
        assert result.assessment is not None
    
    @pytest.mark.asyncio
    async def test_evaluation_with_ai_service_failure(self):
        """Test evaluation with AI service failure"""
        # Mock successful validation and task detection
        self.service.text_validator.validate_submission = Mock(
            return_value=Mock(is_valid=True, word_count=100, errors=[], warnings=[])
        )
        
        # Mock user and rate limit success
        mock_user = Mock()
        mock_user.is_pro = False
        self.mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)
        self.mock_rate_limit_repo.get_daily_submission_count = AsyncMock(return_value=0)
        
        # Mock submission creation success
        mock_submission = Mock()
        mock_submission.id = 123
        self.mock_submission_repo.create = AsyncMock(return_value=mock_submission)
        
        # Mock AI service failure
        self.mock_ai_engine.assess_writing = AsyncMock(
            side_effect=AIServiceError(
                "API timeout", "openai", "timeout", recoverable=True
            )
        )
        
        # Mock submission status update
        self.mock_submission_repo.update_status = AsyncMock()
        
        request = EvaluationRequest(
            user_id=12345,
            text="This is a test writing sample.",
            task_type=TaskType.TASK_1,
            force_task_type=True
        )
        
        with pytest.raises(AIServiceError):
            await self.service.evaluate_writing(request)
        
        # Verify submission was marked as failed
        self.mock_submission_repo.update_status.assert_called()


class TestServiceMonitor:
    """Test service monitoring and health checking"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.monitor = ServiceMonitor()
    
    @pytest.mark.asyncio
    async def test_service_health_check_success(self):
        """Test successful service health check"""
        with patch.object(self.monitor, '_check_openai_health', new_callable=AsyncMock):
            await self.monitor._check_service_health("openai_api")
            
            service = self.monitor.get_service_status("openai_api")
            assert service.status == ServiceStatus.HEALTHY
            assert service.consecutive_failures == 0
    
    @pytest.mark.asyncio
    async def test_service_health_check_failure(self):
        """Test service health check failure"""
        with patch.object(
            self.monitor, '_check_openai_health', 
            new_callable=AsyncMock, side_effect=Exception("API error")
        ):
            await self.monitor._check_service_health("openai_api")
            
            service = self.monitor.get_service_status("openai_api")
            # First failure should set status to UNHEALTHY (as passed to _update_service_status)
            assert service.status == ServiceStatus.UNHEALTHY
            assert service.consecutive_failures == 1
            assert "API error" in service.error_message
    
    def test_circuit_breaker_threshold(self):
        """Test circuit breaker activation after threshold failures"""
        # Simulate multiple failures
        for i in range(5):
            self.monitor._update_service_status(
                "openai_api", ServiceStatus.UNHEALTHY, 
                error_message=f"Error {i}"
            )
        
        service = self.monitor.get_service_status("openai_api")
        assert service.status == ServiceStatus.UNHEALTHY
        assert service.consecutive_failures == 5
    
    def test_fallback_response_ai_service(self):
        """Test fallback response for AI service issues"""
        # Set service as unhealthy
        self.monitor._update_service_status(
            "openai_api", ServiceStatus.UNHEALTHY,
            error_message="Multiple failures"
        )
        self.monitor.services["openai_api"].consecutive_failures = 5
        
        fallback = self.monitor.get_fallback_response("openai_api")
        
        assert "AI assessment service is temporarily unavailable" in fallback.message
        assert fallback.can_retry is True
        assert fallback.estimated_recovery_time == "5-10 minutes"
        assert fallback.alternative_actions is not None
    
    def test_fallback_response_database_service(self):
        """Test fallback response for database issues"""
        fallback = self.monitor.get_fallback_response("database")
        
        assert "Database temporarily unavailable" in fallback.message
        assert "evaluation can still proceed" in fallback.message
        assert fallback.can_retry is True
    
    def test_overall_health_calculation(self):
        """Test overall system health calculation"""
        # All services healthy
        for service_name in self.monitor.services.keys():
            self.monitor._update_service_status(service_name, ServiceStatus.HEALTHY)
        
        assert self.monitor.get_overall_health() == ServiceStatus.HEALTHY
        
        # One service degraded - need to simulate multiple failures to get degraded status
        self.monitor.services["openai_api"].consecutive_failures = 1
        self.monitor._update_service_status("openai_api", ServiceStatus.UNHEALTHY)
        # This should result in DEGRADED status due to consecutive_failures = 2 after increment
        assert self.monitor.get_overall_health() == ServiceStatus.DEGRADED
        
        # One service unhealthy - simulate enough failures
        self.monitor.services["database"].consecutive_failures = 4  # Will become 5 after increment
        self.monitor._update_service_status("database", ServiceStatus.UNHEALTHY)
        assert self.monitor.get_overall_health() == ServiceStatus.UNHEALTHY
    
    def test_service_availability_check(self):
        """Test service availability checking"""
        # Healthy service should be available
        self.monitor._update_service_status("openai_api", ServiceStatus.HEALTHY)
        assert self.monitor.is_service_available("openai_api") is True
        
        # Degraded service should still be available - simulate proper degraded state
        self.monitor.services["openai_api"].consecutive_failures = 1
        self.monitor._update_service_status("openai_api", ServiceStatus.UNHEALTHY)
        assert self.monitor.is_service_available("openai_api") is True  # Should be degraded, thus available
        
        # Unhealthy service should not be available - simulate enough failures
        self.monitor.services["openai_api"].consecutive_failures = 4  # Will become 5 after increment
        self.monitor._update_service_status("openai_api", ServiceStatus.UNHEALTHY)
        assert self.monitor.is_service_available("openai_api") is False
    
    def test_health_summary_generation(self):
        """Test health summary generation"""
        summary = self.monitor.get_health_summary()
        
        assert "overall_status" in summary
        assert "services" in summary
        assert "timestamp" in summary
        
        # Check service details
        for service_name in self.monitor.services.keys():
            assert service_name in summary["services"]
            service_data = summary["services"][service_name]
            assert "status" in service_data
            assert "last_check" in service_data
            assert "consecutive_failures" in service_data


if __name__ == "__main__":
    pytest.main([__file__])