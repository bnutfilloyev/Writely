"""
End-to-end tests simulating complete user journeys.
Tests the entire user experience from start to evaluation completion.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, date
from aiogram.types import Message, User, Chat, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.handlers.start_handler import handle_start_command
from src.handlers.submission_handler import handle_text_submission, SubmissionStates
from src.handlers.history_handler import handle_history_request
from src.handlers.callback_handler import (
    handle_submit_task1, handle_submit_task2, handle_show_history,
    handle_clarify_task1, handle_clarify_task2, handle_back_to_menu
)
from src.services.evaluation_service import EvaluationService, EvaluationResult
from src.services.user_service import UserService, UserProfile
from src.services.rate_limit_service import RateLimitService, RateLimitResult, RateLimitStatus
from src.models.submission import TaskType
from tests.test_data.ielts_samples import IELTSTestData, MOCK_OPENAI_RESPONSES


class TestCompleteUserJourneys:
    """Test complete user journeys from start to finish."""
    
    @pytest.fixture
    def mock_telegram_user(self):
        """Create mock Telegram user."""
        return User(
            id=12345,
            is_bot=False,
            first_name="John",
            username="john_doe"
        )
    
    @pytest.fixture
    def mock_chat(self):
        """Create mock Telegram chat."""
        return Chat(id=12345, type="private")
    
    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return AsyncMock(spec=AsyncSession)
    
    @pytest.fixture
    def mock_state(self):
        """Create mock FSM state."""
        state = AsyncMock(spec=FSMContext)
        state.get_state.return_value = None
        state.get_data.return_value = {}
        state.update_data = AsyncMock()
        state.set_state = AsyncMock()
        state.clear = AsyncMock()
        return state
    
    def create_mock_message(self, text: str, user: User, chat: Chat) -> Message:
        """Create mock message with specified text."""
        message = MagicMock(spec=Message)
        message.text = text
        message.from_user = user
        message.chat = chat
        message.answer = AsyncMock()
        message.message_id = 123
        return message
    
    def create_mock_callback(self, data: str, user: User, chat: Chat) -> CallbackQuery:
        """Create mock callback query."""
        callback = MagicMock(spec=CallbackQuery)
        callback.data = data
        callback.from_user = user
        callback.message = MagicMock()
        callback.message.chat = chat
        callback.message.edit_text = AsyncMock()
        callback.answer = AsyncMock()
        return callback
    
    @pytest.mark.asyncio
    async def test_new_user_complete_task2_journey(
        self, mock_telegram_user, mock_chat, mock_session, mock_state
    ):
        """Test complete journey: new user -> start -> Task 2 submission -> evaluation -> history."""
        
        # Step 1: User sends /start command
        start_message = self.create_mock_message("/start", mock_telegram_user, mock_chat)
        
        with patch('src.handlers.start_handler.UserService') as mock_user_service:
            # Mock user creation
            user_profile = UserProfile(
                telegram_id=12345,
                username="john_doe",
                first_name="John",
                created_at=datetime.now(),
                is_pro=False,
                daily_submissions=0,
                last_submission_date=None,
                total_submissions=0
            )
            mock_user_service_instance = AsyncMock()
            mock_user_service_instance.get_or_create_user.return_value = user_profile
            mock_user_service.return_value = mock_user_service_instance
            
            await handle_start_command(start_message, mock_session)
            
            # Verify welcome message was sent
            start_message.answer.assert_called_once()
            welcome_text = start_message.answer.call_args[1]['text']
            assert "Hello John!" in welcome_text
            assert "Welcome to the IELTS Writing Evaluation Bot" in welcome_text
        
        # Step 2: User clicks "Submit Writing Task 2" button
        task2_callback = self.create_mock_callback("submit_task2", mock_telegram_user, mock_chat)
        
        await handle_submit_task2(task2_callback, mock_state)
        
        # Verify state was set for Task 2 submission
        mock_state.set_state.assert_called_with(SubmissionStates.waiting_for_text)
        mock_state.update_data.assert_called_with(task_type=TaskType.TASK_2)
        
        # Verify Task 2 instructions were shown
        task2_callback.message.edit_text.assert_called_once()
        instructions_text = task2_callback.message.edit_text.call_args[1]['text']
        assert "IELTS Writing Task 2 Submission" in instructions_text
        
        # Step 3: User submits Task 2 essay
        task2_sample = IELTSTestData.get_task2_samples()[0]  # Get intermediate level sample
        submission_message = self.create_mock_message(task2_sample.text, mock_telegram_user, mock_chat)
        
        with patch('src.handlers.submission_handler.create_evaluation_service') as mock_eval_service, \
             patch('src.handlers.submission_handler.RateLimitService') as mock_rate_service, \
             patch('src.handlers.submission_handler.UserService') as mock_user_service:
            
            # Mock rate limit check (allowed)
            rate_limit_result = RateLimitResult(
                status=RateLimitStatus.ALLOWED,
                current_count=1,
                daily_limit=3,
                remaining=2,
                can_submit=True
            )
            mock_rate_service_instance = AsyncMock()
            mock_rate_service_instance.check_rate_limit.return_value = rate_limit_result
            mock_rate_service.return_value = mock_rate_service_instance
            
            # Mock user service
            mock_user_service_instance = AsyncMock()
            mock_user_service_instance.get_or_create_user.return_value = user_profile
            mock_user_service.return_value = mock_user_service_instance
            
            # Mock successful evaluation
            from src.services.ai_assessment_engine import StructuredAssessment
            from src.services.evaluation_service import ValidationResult, TaskDetectionResult
            
            assessment = StructuredAssessment(
                task_achievement_score=6.5,
                coherence_cohesion_score=6.0,
                lexical_resource_score=6.5,
                grammatical_accuracy_score=6.0,
                overall_band_score=6.0,
                detailed_feedback=MOCK_OPENAI_RESPONSES['medium_quality']['detailed_feedback'],
                improvement_suggestions=MOCK_OPENAI_RESPONSES['medium_quality']['improvement_suggestions'],
                score_justifications=MOCK_OPENAI_RESPONSES['medium_quality']['score_justifications']
            )
            
            evaluation_result = EvaluationResult(
                success=True,
                submission_id=1,
                assessment=assessment,
                validation_result=ValidationResult(
                    is_valid=True,
                    word_count=task2_sample.word_count,
                    errors=[],
                    warnings=[]
                ),
                task_detection_result=TaskDetectionResult(
                    detected_type=TaskType.TASK_2,
                    confidence_score=0.9,
                    reasoning="Strong Task 2 indicators detected",
                    requires_clarification=False
                )
            )
            
            mock_eval_service_instance = AsyncMock()
            mock_eval_service_instance.evaluate_writing.return_value = evaluation_result
            mock_eval_service.return_value = mock_eval_service_instance
            
            # Mock processing message
            processing_msg = AsyncMock()
            processing_msg.delete = AsyncMock()
            submission_message.answer.return_value = processing_msg
            
            await handle_text_submission(submission_message, mock_state, mock_session)
            
            # Verify evaluation was performed
            mock_eval_service_instance.evaluate_writing.assert_called_once()
            
            # Verify processing message was shown and deleted
            processing_msg.delete.assert_called_once()
            
            # Verify result was sent (multiple calls due to processing message)
            assert submission_message.answer.call_count >= 2
            
            # Verify state was cleared after successful submission
            mock_state.clear.assert_called_once()
        
        # Step 4: User checks history
        history_callback = self.create_mock_callback("show_history", mock_telegram_user, mock_chat)
        
        with patch('src.handlers.callback_handler.handle_history_request') as mock_history_handler:
            await handle_show_history(history_callback, mock_session)
            
            # Verify history handler was called
            mock_history_handler.assert_called_once()
            history_callback.answer.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_task_type_clarification_journey(
        self, mock_telegram_user, mock_chat, mock_session, mock_state
    ):
        """Test journey requiring task type clarification."""
        
        # Step 1: User submits ambiguous text
        ambiguous_sample = IELTSTestData.get_edge_cases()[2]  # Ambiguous text
        submission_message = self.create_mock_message(ambiguous_sample.text, mock_telegram_user, mock_chat)
        
        with patch('src.handlers.submission_handler.create_evaluation_service') as mock_eval_service, \
             patch('src.handlers.submission_handler.RateLimitService') as mock_rate_service, \
             patch('src.handlers.submission_handler.UserService') as mock_user_service:
            
            # Mock services
            rate_limit_result = RateLimitResult(
                status=RateLimitStatus.ALLOWED,
                current_count=1,
                daily_limit=3,
                remaining=2,
                can_submit=True
            )
            mock_rate_service_instance = AsyncMock()
            mock_rate_service_instance.check_rate_limit.return_value = rate_limit_result
            mock_rate_service.return_value = mock_rate_service_instance
            
            user_profile = UserProfile(
                telegram_id=12345,
                username="john_doe",
                first_name="John",
                created_at=datetime.now(),
                is_pro=False,
                daily_submissions=1,
                last_submission_date=date.today(),
                total_submissions=5
            )
            mock_user_service_instance = AsyncMock()
            mock_user_service_instance.get_or_create_user.return_value = user_profile
            mock_user_service.return_value = mock_user_service_instance
            
            # Mock evaluation requiring clarification
            from src.services.evaluation_service import ValidationResult, TaskDetectionResult
            
            clarification_result = EvaluationResult(
                success=False,
                requires_task_clarification=True,
                validation_result=ValidationResult(
                    is_valid=True,
                    word_count=ambiguous_sample.word_count,
                    errors=[],
                    warnings=[]
                ),
                task_detection_result=TaskDetectionResult(
                    detected_type=None,
                    confidence_score=0.4,
                    reasoning="Ambiguous content requires clarification",
                    requires_clarification=True
                ),
                error_message="Unable to determine task type. Please specify Task 1 or Task 2."
            )
            
            mock_eval_service_instance = AsyncMock()
            mock_eval_service_instance.evaluate_writing.return_value = clarification_result
            mock_eval_service.return_value = mock_eval_service_instance
            
            # Mock processing message
            processing_msg = AsyncMock()
            processing_msg.delete = AsyncMock()
            submission_message.answer.return_value = processing_msg
            
            await handle_text_submission(submission_message, mock_state, mock_session)
            
            # Verify clarification was requested
            mock_state.update_data.assert_called_with(text=ambiguous_sample.text)
            mock_state.set_state.assert_called_with(SubmissionStates.waiting_for_task_clarification)
        
        # Step 2: User clarifies as Task 1
        clarify_callback = self.create_mock_callback("clarify_task1", mock_telegram_user, mock_chat)
        mock_state.get_data.return_value = {'text': ambiguous_sample.text}
        
        with patch('src.handlers.callback_handler.handle_text_submission') as mock_text_handler:
            await handle_clarify_task1(clarify_callback, mock_state, mock_session)
            
            # Verify state was updated with task type
            mock_state.update_data.assert_called_with(task_type=TaskType.TASK_1)
            
            # Verify text handler was called for re-evaluation
            mock_text_handler.assert_called_once()
            clarify_callback.answer.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_journey(
        self, mock_telegram_user, mock_chat, mock_session, mock_state
    ):
        """Test journey when user exceeds rate limit."""
        
        # User submits text when at rate limit
        task2_sample = IELTSTestData.get_task2_samples()[0]
        submission_message = self.create_mock_message(task2_sample.text, mock_telegram_user, mock_chat)
        
        with patch('src.handlers.submission_handler.RateLimitService') as mock_rate_service:
            # Mock rate limit exceeded
            rate_limit_result = RateLimitResult(
                status=RateLimitStatus.LIMIT_REACHED,
                current_count=3,
                daily_limit=3,
                remaining=0,
                can_submit=False,
                message="You've reached your daily limit of 3 submissions. Upgrade to Pro for unlimited evaluations!"
            )
            mock_rate_service_instance = AsyncMock()
            mock_rate_service_instance.check_rate_limit.return_value = rate_limit_result
            mock_rate_service.return_value = mock_rate_service_instance
            
            await handle_text_submission(submission_message, mock_state, mock_session)
            
            # Verify rate limit message was sent
            assert submission_message.answer.call_count >= 1
            
            # Verify state was cleared
            mock_state.clear.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_pro_user_unlimited_submissions_journey(
        self, mock_telegram_user, mock_chat, mock_session, mock_state
    ):
        """Test pro user can make unlimited submissions."""
        
        # Create pro user profile
        pro_user_profile = UserProfile(
            telegram_id=12345,
            username="john_doe",
            first_name="John",
            created_at=datetime.now(),
            is_pro=True,
            daily_submissions=10,  # Would exceed free limit
            last_submission_date=date.today(),
            total_submissions=50
        )
        
        task1_sample = IELTSTestData.get_task1_samples()[0]
        submission_message = self.create_mock_message(task1_sample.text, mock_telegram_user, mock_chat)
        
        with patch('src.handlers.submission_handler.create_evaluation_service') as mock_eval_service, \
             patch('src.handlers.submission_handler.RateLimitService') as mock_rate_service, \
             patch('src.handlers.submission_handler.UserService') as mock_user_service:
            
            # Mock rate limit check for pro user (allowed)
            rate_limit_result = RateLimitResult(
                status=RateLimitStatus.ALLOWED,
                current_count=10,
                daily_limit=50,  # Pro limit
                remaining=40,
                can_submit=True
            )
            mock_rate_service_instance = AsyncMock()
            mock_rate_service_instance.check_rate_limit.return_value = rate_limit_result
            mock_rate_service.return_value = mock_rate_service_instance
            
            # Mock user service
            mock_user_service_instance = AsyncMock()
            mock_user_service_instance.get_or_create_user.return_value = pro_user_profile
            mock_user_service.return_value = mock_user_service_instance
            
            # Mock successful evaluation
            from src.services.ai_assessment_engine import StructuredAssessment
            from src.services.evaluation_service import ValidationResult, TaskDetectionResult
            
            assessment = StructuredAssessment(
                task_achievement_score=7.0,
                coherence_cohesion_score=6.5,
                lexical_resource_score=7.5,
                grammatical_accuracy_score=6.0,
                overall_band_score=6.8,
                detailed_feedback=MOCK_OPENAI_RESPONSES['high_quality']['detailed_feedback'],
                improvement_suggestions=MOCK_OPENAI_RESPONSES['high_quality']['improvement_suggestions'],
                score_justifications=MOCK_OPENAI_RESPONSES['high_quality']['score_justifications']
            )
            
            evaluation_result = EvaluationResult(
                success=True,
                submission_id=1,
                assessment=assessment,
                validation_result=ValidationResult(
                    is_valid=True,
                    word_count=task1_sample.word_count,
                    errors=[],
                    warnings=[]
                ),
                task_detection_result=TaskDetectionResult(
                    detected_type=TaskType.TASK_1,
                    confidence_score=0.95,
                    reasoning="Clear Task 1 indicators detected",
                    requires_clarification=False
                )
            )
            
            mock_eval_service_instance = AsyncMock()
            mock_eval_service_instance.evaluate_writing.return_value = evaluation_result
            mock_eval_service.return_value = mock_eval_service_instance
            
            # Mock processing message
            processing_msg = AsyncMock()
            processing_msg.delete = AsyncMock()
            submission_message.answer.return_value = processing_msg
            
            await handle_text_submission(submission_message, mock_state, mock_session)
            
            # Verify evaluation was performed successfully
            mock_eval_service_instance.evaluate_writing.assert_called_once()
            processing_msg.delete.assert_called_once()
            mock_state.clear.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validation_error_journey(
        self, mock_telegram_user, mock_chat, mock_session, mock_state
    ):
        """Test journey with validation errors (too short text)."""
        
        # User submits text that's too short
        short_sample = IELTSTestData.get_edge_cases()[0]  # Too short text
        submission_message = self.create_mock_message(short_sample.text, mock_telegram_user, mock_chat)
        
        with patch('src.handlers.submission_handler.create_evaluation_service') as mock_eval_service, \
             patch('src.handlers.submission_handler.RateLimitService') as mock_rate_service, \
             patch('src.handlers.submission_handler.UserService') as mock_user_service:
            
            # Mock services
            rate_limit_result = RateLimitResult(
                status=RateLimitStatus.ALLOWED,
                current_count=1,
                daily_limit=3,
                remaining=2,
                can_submit=True
            )
            mock_rate_service_instance = AsyncMock()
            mock_rate_service_instance.check_rate_limit.return_value = rate_limit_result
            mock_rate_service.return_value = mock_rate_service_instance
            
            user_profile = UserProfile(
                telegram_id=12345,
                username="john_doe",
                first_name="John",
                created_at=datetime.now(),
                is_pro=False,
                daily_submissions=1,
                last_submission_date=date.today(),
                total_submissions=5
            )
            mock_user_service_instance = AsyncMock()
            mock_user_service_instance.get_or_create_user.return_value = user_profile
            mock_user_service.return_value = mock_user_service_instance
            
            # Mock validation error
            from src.services.evaluation_service import ValidationResult
            from src.services.text_processor import ValidationError
            
            validation_error_result = EvaluationResult(
                success=False,
                validation_result=ValidationResult(
                    is_valid=False,
                    word_count=short_sample.word_count,
                    errors=[ValidationError.TOO_SHORT],
                    warnings=[]
                ),
                error_message=f"Text is too short ({short_sample.word_count} words). Please provide at least 50 words for accurate evaluation."
            )
            
            mock_eval_service_instance = AsyncMock()
            mock_eval_service_instance.evaluate_writing.return_value = validation_error_result
            mock_eval_service.return_value = mock_eval_service_instance
            
            await handle_text_submission(submission_message, mock_state, mock_session)
            
            # Verify error message was sent
            assert submission_message.answer.call_count >= 1
            
            # Verify state was cleared
            mock_state.clear.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_navigation_back_to_menu_journey(
        self, mock_telegram_user, mock_chat, mock_session, mock_state
    ):
        """Test user navigation back to main menu."""
        
        # User clicks back to menu from any state
        back_callback = self.create_mock_callback("back_to_menu", mock_telegram_user, mock_chat)
        
        await handle_back_to_menu(back_callback, mock_state)
        
        # Verify state was cleared
        mock_state.clear.assert_called_once()
        
        # Verify main menu was shown
        back_callback.message.edit_text.assert_called_once()
        menu_text = back_callback.message.edit_text.call_args[1]['text']
        assert "Main Menu" in menu_text
        
        back_callback.answer.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_multiple_submissions_progress_tracking(
        self, mock_telegram_user, mock_chat, mock_session
    ):
        """Test progress tracking across multiple submissions."""
        
        # Simulate user with history
        user_profile = UserProfile(
            telegram_id=12345,
            username="john_doe",
            first_name="John",
            created_at=datetime.now(),
            is_pro=False,
            daily_submissions=2,
            last_submission_date=date.today(),
            total_submissions=5
        )
        
        # Mock history data showing improvement
        history_data = [
            {
                'submission_id': 3,
                'task_type': 'task_2',
                'overall_band_score': 7.0,
                'submitted_at': datetime.now(),
                'word_count': 280
            },
            {
                'submission_id': 2,
                'task_type': 'task_1',
                'overall_band_score': 6.5,
                'submitted_at': datetime.now(),
                'word_count': 180
            },
            {
                'submission_id': 1,
                'task_type': 'task_2',
                'overall_band_score': 6.0,
                'submitted_at': datetime.now(),
                'word_count': 250
            }
        ]
        
        history_message = self.create_mock_message("history", mock_telegram_user, mock_chat)
        
        with patch('src.handlers.history_handler.create_evaluation_service') as mock_eval_service, \
             patch('src.handlers.history_handler.UserService') as mock_user_service:
            
            # Mock services
            mock_user_service_instance = AsyncMock()
            mock_user_service_instance.get_user_profile.return_value = user_profile
            mock_user_service.return_value = mock_user_service_instance
            
            mock_eval_service_instance = AsyncMock()
            mock_eval_service_instance.get_user_evaluation_history.return_value = history_data
            mock_eval_service.return_value = mock_eval_service_instance
            
            await handle_history_request(history_message, mock_session)
            
            # Verify history was retrieved and formatted
            mock_eval_service_instance.get_user_evaluation_history.assert_called_once()
            history_message.answer.assert_called_once()
            
            # Verify progress tracking is shown
            history_text = history_message.answer.call_args[1]['text']
            assert "Progress Trend:" in history_text
            assert "improving" in history_text.lower() or "📈" in history_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])