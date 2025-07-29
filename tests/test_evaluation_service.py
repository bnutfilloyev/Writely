"""
Unit tests for evaluation service
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.services.evaluation_service import (
    EvaluationService, EvaluationRequest, EvaluationResult, RateLimitStatus
)
from src.services.text_processor import ValidationResult, TaskDetectionResult, ValidationError
from src.services.ai_assessment_engine import StructuredAssessment, RawAssessment
from src.models.submission import TaskType, ProcessingStatus
from src.models.user import User
from src.models.submission import Submission
from src.models.assessment import Assessment


class TestEvaluationService:
    """Test cases for EvaluationService"""
    
    def setup_method(self):
        # Create mock repositories
        self.mock_ai_engine = MagicMock()  # AI engine methods are not async
        self.mock_user_repo = AsyncMock()
        self.mock_submission_repo = AsyncMock()
        self.mock_assessment_repo = AsyncMock()
        self.mock_rate_limit_repo = AsyncMock()
        
        # Create service instance
        self.service = EvaluationService(
            ai_engine=self.mock_ai_engine,
            user_repo=self.mock_user_repo,
            submission_repo=self.mock_submission_repo,
            assessment_repo=self.mock_assessment_repo,
            rate_limit_repo=self.mock_rate_limit_repo
        )
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_free_user_within_limit(self):
        """Test rate limit check for free user within daily limit"""
        # Setup
        mock_user = User(id=1, telegram_id=123, is_pro=False)
        self.mock_user_repo.get_by_id.return_value = mock_user
        self.mock_rate_limit_repo.get_daily_submission_count.return_value = 1
        
        # Execute
        result = await self.service.check_rate_limit(1)
        
        # Assert
        assert result.is_allowed
        assert result.daily_count == 1
        assert result.daily_limit == 3
        assert result.message is None
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_free_user_exceeded(self):
        """Test rate limit check for free user who exceeded daily limit"""
        # Setup
        mock_user = User(id=1, telegram_id=123, is_pro=False)
        self.mock_user_repo.get_by_id.return_value = mock_user
        self.mock_rate_limit_repo.get_daily_submission_count.return_value = 3
        
        # Execute
        result = await self.service.check_rate_limit(1)
        
        # Assert
        assert not result.is_allowed
        assert result.daily_count == 3
        assert result.daily_limit == 3
        assert "Daily submission limit reached" in result.message
        assert "Upgrade to Pro" in result.message
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_pro_user(self):
        """Test rate limit check for pro user"""
        # Setup
        mock_user = User(id=1, telegram_id=123, is_pro=True)
        self.mock_user_repo.get_by_id.return_value = mock_user
        self.mock_rate_limit_repo.get_daily_submission_count.return_value = 10
        
        # Execute
        result = await self.service.check_rate_limit(1)
        
        # Assert
        assert result.is_allowed
        assert result.daily_count == 10
        assert result.daily_limit == 50
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_user_not_found(self):
        """Test rate limit check when user not found"""
        # Setup
        self.mock_user_repo.get_by_id.return_value = None
        
        # Execute
        result = await self.service.check_rate_limit(999)
        
        # Assert
        assert not result.is_allowed
        assert "User not found" in result.message
    
    @pytest.mark.asyncio
    async def test_validate_submission_valid_text(self):
        """Test text validation with valid text"""
        text = "This is a valid English text with more than fifty words to pass the validation. " * 3
        
        with patch.object(self.service.text_validator, 'validate_submission') as mock_validate:
            mock_validate.return_value = ValidationResult(
                is_valid=True,
                errors=[],
                warnings=[],
                word_count=60,
                detected_language='en',
                confidence_score=0.9
            )
            
            result = await self.service.validate_submission(text)
            
            assert result.is_valid
            assert len(result.errors) == 0
            assert result.word_count == 60
    
    @pytest.mark.asyncio
    async def test_validate_submission_invalid_text(self):
        """Test text validation with invalid text"""
        text = "Too short"
        
        with patch.object(self.service.text_validator, 'validate_submission') as mock_validate:
            mock_validate.return_value = ValidationResult(
                is_valid=False,
                errors=[ValidationError.TOO_SHORT],
                warnings=[],
                word_count=2,
                detected_language='en',
                confidence_score=0.9
            )
            
            result = await self.service.validate_submission(text)
            
            assert not result.is_valid
            assert ValidationError.TOO_SHORT in result.errors
            assert result.word_count == 2
    
    @pytest.mark.asyncio
    async def test_detect_task_type_clear_task1(self):
        """Test task type detection with clear Task 1 indicators"""
        text = "The chart shows data from 2010 to 2020 with increasing trends."
        
        with patch.object(self.service.task_detector, 'detect_task_type') as mock_detect:
            mock_detect.return_value = TaskDetectionResult(
                detected_type=TaskType.TASK_1,
                confidence_score=0.8,
                reasoning="Strong Task 1 indicators detected",
                requires_clarification=False
            )
            
            result = await self.service.detect_task_type(text)
            
            assert result.detected_type == TaskType.TASK_1
            assert result.confidence_score == 0.8
            assert not result.requires_clarification
    
    @pytest.mark.asyncio
    async def test_detect_task_type_ambiguous(self):
        """Test task type detection with ambiguous text"""
        text = "This is ambiguous text without clear indicators."
        
        with patch.object(self.service.task_detector, 'detect_task_type') as mock_detect:
            mock_detect.return_value = TaskDetectionResult(
                detected_type=None,
                confidence_score=0.4,
                reasoning="Ambiguous content",
                requires_clarification=True
            )
            
            result = await self.service.detect_task_type(text)
            
            assert result.detected_type is None
            assert result.requires_clarification
    
    @pytest.mark.asyncio
    async def test_evaluate_writing_success_flow(self):
        """Test complete successful evaluation workflow"""
        # Setup request
        request = EvaluationRequest(
            user_id=1,
            text="The chart shows increasing trends from 2010 to 2020. " * 10,
            task_type=TaskType.TASK_1,
            force_task_type=True
        )
        
        # Mock rate limit check
        self.mock_user_repo.get_by_id.return_value = User(id=1, telegram_id=123, is_pro=False)
        self.mock_rate_limit_repo.get_daily_submission_count.return_value = 1
        
        # Mock validation
        with patch.object(self.service.text_validator, 'validate_submission') as mock_validate:
            mock_validate.return_value = ValidationResult(
                is_valid=True,
                errors=[],
                warnings=[],
                word_count=80,
                detected_language='en',
                confidence_score=0.9
            )
            
            # Mock submission creation
            mock_submission = Submission(id=1, user_id=1, text=request.text, 
                                       task_type=TaskType.TASK_1, word_count=80)
            self.mock_submission_repo.create.return_value = mock_submission
            
            # Mock AI assessment
            mock_raw_assessment = RawAssessment(
                content='{"task_achievement_score": 7.0, "coherence_cohesion_score": 6.5, "lexical_resource_score": 6.0, "grammatical_accuracy_score": 6.5, "overall_band_score": 6.5, "detailed_feedback": "Good work", "improvement_suggestions": ["Improve vocabulary", "Work on grammar"], "score_justifications": {"task_achievement": "Good", "coherence_cohesion": "Adequate", "lexical_resource": "Basic", "grammatical_accuracy": "Good"}}',
                usage_tokens=500,
                model_used="gpt-4"
            )
            # assess_writing is async, so we need to use AsyncMock for this method
            self.mock_ai_engine.assess_writing = AsyncMock(return_value=mock_raw_assessment)
            
            mock_structured_assessment = StructuredAssessment(
                task_achievement_score=7.0,
                coherence_cohesion_score=6.5,
                lexical_resource_score=6.0,
                grammatical_accuracy_score=6.5,
                overall_band_score=6.5,
                detailed_feedback="Good work",
                improvement_suggestions=["Improve vocabulary", "Work on grammar"],
                score_justifications={
                    "task_achievement": "Good",
                    "coherence_cohesion": "Adequate", 
                    "lexical_resource": "Basic",
                    "grammatical_accuracy": "Good"
                }
            )
            self.mock_ai_engine.parse_response.return_value = mock_structured_assessment
            self.mock_ai_engine.validate_scores.return_value = True
            
            # Mock assessment creation
            mock_assessment = Assessment(id=1, submission_id=1, overall_band_score=6.5)
            self.mock_assessment_repo.create.return_value = mock_assessment
            
            # Execute
            result = await self.service.evaluate_writing(request)
            
            # Assert
            assert result.success
            assert result.submission_id == 1
            assert result.assessment is not None
            assert result.assessment.overall_band_score == 6.5
            assert not result.requires_task_clarification
            
            # Verify repository calls
            self.mock_submission_repo.create.assert_called_once()
            self.mock_rate_limit_repo.increment_daily_count.assert_called_once_with(1)
            self.mock_assessment_repo.create.assert_called_once()
            self.mock_submission_repo.update_status.assert_called_with(1, ProcessingStatus.COMPLETED)
    
    @pytest.mark.asyncio
    async def test_evaluate_writing_rate_limit_exceeded(self):
        """Test evaluation when rate limit is exceeded"""
        # Setup request
        request = EvaluationRequest(user_id=1, text="Test text")
        
        # Mock rate limit exceeded
        self.mock_user_repo.get_by_id.return_value = User(id=1, telegram_id=123, is_pro=False)
        self.mock_rate_limit_repo.get_daily_submission_count.return_value = 3
        
        # Execute
        result = await self.service.evaluate_writing(request)
        
        # Assert
        assert not result.success
        assert "Daily submission limit reached" in result.error_message
        assert result.submission_id is None
    
    @pytest.mark.asyncio
    async def test_evaluate_writing_validation_failed(self):
        """Test evaluation when text validation fails"""
        # Setup request
        request = EvaluationRequest(user_id=1, text="Short")
        
        # Mock rate limit OK
        self.mock_user_repo.get_by_id.return_value = User(id=1, telegram_id=123, is_pro=False)
        self.mock_rate_limit_repo.get_daily_submission_count.return_value = 1
        
        # Mock validation failure
        with patch.object(self.service.text_validator, 'validate_submission') as mock_validate:
            mock_validate.return_value = ValidationResult(
                is_valid=False,
                errors=[ValidationError.TOO_SHORT],
                warnings=[],
                word_count=1,
                detected_language='en',
                confidence_score=0.9
            )
            
            # Execute
            result = await self.service.evaluate_writing(request)
            
            # Assert
            assert not result.success
            assert "too short" in result.error_message.lower()
            assert result.validation_result is not None
    
    @pytest.mark.asyncio
    async def test_evaluate_writing_task_clarification_needed(self):
        """Test evaluation when task type clarification is needed"""
        # Setup request without forced task type
        request = EvaluationRequest(user_id=1, text="Ambiguous text " * 20)
        
        # Mock rate limit OK
        self.mock_user_repo.get_by_id.return_value = User(id=1, telegram_id=123, is_pro=False)
        self.mock_rate_limit_repo.get_daily_submission_count.return_value = 1
        
        # Mock validation OK
        with patch.object(self.service.text_validator, 'validate_submission') as mock_validate:
            mock_validate.return_value = ValidationResult(
                is_valid=True,
                errors=[],
                warnings=[],
                word_count=60,
                detected_language='en',
                confidence_score=0.9
            )
            
            # Mock task detection requiring clarification
            with patch.object(self.service.task_detector, 'detect_task_type') as mock_detect:
                mock_detect.return_value = TaskDetectionResult(
                    detected_type=None,
                    confidence_score=0.4,
                    reasoning="Ambiguous content",
                    requires_clarification=True
                )
                
                # Execute
                result = await self.service.evaluate_writing(request)
                
                # Assert
                assert not result.success
                assert result.requires_task_clarification
                assert "Unable to determine task type" in result.error_message
    
    @pytest.mark.asyncio
    async def test_evaluate_writing_ai_assessment_failure(self):
        """Test evaluation when AI assessment fails"""
        # Setup request
        request = EvaluationRequest(
            user_id=1,
            text="The chart shows data " * 20,
            task_type=TaskType.TASK_1,
            force_task_type=True
        )
        
        # Mock successful setup
        self.mock_user_repo.get_by_id.return_value = User(id=1, telegram_id=123, is_pro=False)
        self.mock_rate_limit_repo.get_daily_submission_count.return_value = 1
        
        with patch.object(self.service.text_validator, 'validate_submission') as mock_validate:
            mock_validate.return_value = ValidationResult(
                is_valid=True,
                errors=[],
                warnings=[],
                word_count=80,
                detected_language='en',
                confidence_score=0.9
            )
            
            # Mock submission creation
            mock_submission = Submission(id=1, user_id=1, text=request.text, 
                                       task_type=TaskType.TASK_1, word_count=80)
            self.mock_submission_repo.create.return_value = mock_submission
            
            # Mock AI assessment failure
            self.mock_ai_engine.assess_writing = AsyncMock(side_effect=Exception("API Error"))
            
            # Execute
            result = await self.service.evaluate_writing(request)
            
            # Assert
            assert not result.success
            assert result.submission_id == 1
            assert "Assessment failed" in result.error_message
            
            # Verify submission marked as failed
            self.mock_submission_repo.update_status.assert_called_with(1, ProcessingStatus.FAILED)
    
    @pytest.mark.asyncio
    async def test_get_user_evaluation_history(self):
        """Test getting user evaluation history"""
        # Setup mock history data
        mock_submission = MagicMock()
        mock_submission.task_type.value = "task_1"
        mock_submission.submitted_at = datetime(2024, 1, 1)
        mock_submission.word_count = 150
        
        mock_assessment = MagicMock()
        mock_assessment.submission_id = 1
        mock_assessment.overall_band_score = 6.5
        mock_assessment.submission = mock_submission
        
        self.mock_assessment_repo.get_user_history.return_value = [mock_assessment]
        
        # Execute
        history = await self.service.get_user_evaluation_history(1, 5)
        
        # Assert
        assert len(history) == 1
        assert history[0]['submission_id'] == 1
        assert history[0]['task_type'] == "task_1"
        assert history[0]['overall_band_score'] == 6.5
        assert history[0]['word_count'] == 150
        
        self.mock_assessment_repo.get_user_history.assert_called_once_with(1, 5)
    
    @pytest.mark.asyncio
    async def test_get_user_evaluation_history_error(self):
        """Test getting user evaluation history when error occurs"""
        # Setup mock error
        self.mock_assessment_repo.get_user_history.side_effect = Exception("Database error")
        
        # Execute
        history = await self.service.get_user_evaluation_history(1)
        
        # Assert
        assert history == []
    
    def test_format_validation_errors(self):
        """Test formatting of validation errors"""
        # Test empty text error
        validation_result = ValidationResult(
            is_valid=False,
            errors=[ValidationError.EMPTY_TEXT],
            warnings=[],
            word_count=0
        )
        
        message = self.service._format_validation_errors(validation_result)
        assert "Please provide some text" in message
        
        # Test too short error
        validation_result = ValidationResult(
            is_valid=False,
            errors=[ValidationError.TOO_SHORT],
            warnings=[],
            word_count=10
        )
        
        message = self.service._format_validation_errors(validation_result)
        assert "too short" in message.lower()
        assert "10 words" in message
        
        # Test not English error
        validation_result = ValidationResult(
            is_valid=False,
            errors=[ValidationError.NOT_ENGLISH],
            warnings=[],
            word_count=50
        )
        
        message = self.service._format_validation_errors(validation_result)
        assert "English" in message
        
        # Test multiple errors with warnings
        validation_result = ValidationResult(
            is_valid=False,
            errors=[ValidationError.TOO_SHORT, ValidationError.NOT_ENGLISH],
            warnings=["Additional warning"],
            word_count=10
        )
        
        message = self.service._format_validation_errors(validation_result)
        assert "too short" in message.lower()
        assert "English" in message
        assert "Additional warning" in message