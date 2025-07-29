"""
Unit tests for Telegram bot message handlers.
Tests all handler logic with mocked Telegram message objects.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, date
from aiogram.types import Message, User, Chat, CallbackQuery
from aiogram.fsm.context import FSMContext

from src.handlers.start_handler import handle_start_command, get_main_menu_keyboard
from src.handlers.submission_handler import (
    handle_text_submission, 
    SubmissionStates,
    get_task_clarification_keyboard
)
from src.handlers.history_handler import handle_history_request
from src.handlers.callback_handler import (
    handle_back_to_menu,
    handle_submit_task1,
    handle_submit_task2,
    handle_show_history,
    handle_clarify_task1
)
from src.services.user_service import UserProfile
from src.services.evaluation_service import EvaluationResult, ValidationResult, TaskDetectionResult
from src.services.ai_assessment_engine import StructuredAssessment
from src.services.rate_limit_service import RateLimitResult, RateLimitStatus
from src.models.submission import TaskType


class TestStartHandler:
    """Test cases for start command handler."""
    
    @pytest.fixture
    def mock_message(self):
        """Create mock Telegram message."""
        message = MagicMock()
        message.from_user = MagicMock()
        message.from_user.id = 12345
        message.from_user.username = "john_doe"
        message.from_user.first_name = "John"
        message.answer = AsyncMock()
        return message
    
    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return AsyncMock()
    
    @pytest.fixture
    def mock_user_profile(self):
        """Create mock user profile."""
        return UserProfile(
            telegram_id=12345,
            username="john_doe",
            first_name="John",
            created_at=datetime.now(),
            is_pro=False,
            daily_submissions=0,
            last_submission_date=None,
            total_submissions=0
        )
    
    def test_get_main_menu_keyboard(self):
        """Test main menu keyboard creation."""
        keyboard = get_main_menu_keyboard()
        
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) == 3
        assert keyboard.inline_keyboard[0][0].text == "📄 Submit Writing Task 1"
        assert keyboard.inline_keyboard[1][0].text == "📝 Submit Writing Task 2"
        assert keyboard.inline_keyboard[2][0].text == "📊 Check Band Score History"
    
    @patch('src.handlers.start_handler.UserService')
    async def test_handle_start_command_new_user(self, mock_user_service, mock_message, mock_session, mock_user_profile):
        """Test start command for new user."""
        # Setup mocks
        mock_service_instance = AsyncMock()
        mock_service_instance.get_or_create_user.return_value = mock_user_profile
        mock_user_service.return_value = mock_service_instance
        
        # Execute handler
        await handle_start_command(mock_message, mock_session)
        
        # Verify user service was called correctly
        mock_service_instance.get_or_create_user.assert_called_once_with(
            telegram_id=12345,
            username="john_doe",
            first_name="John"
        )
        
        # Verify message was sent
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        
        assert "Hello John!" in call_args[1]['text']
        assert "Welcome to the IELTS Writing Evaluation Bot" in call_args[1]['text']
        assert call_args[1]['parse_mode'] == "Markdown"
        assert call_args[1]['reply_markup'] is not None
    
    @patch('src.handlers.start_handler.UserService')
    async def test_handle_start_command_existing_user(self, mock_user_service, mock_message, mock_session):
        """Test start command for existing user."""
        # Setup existing user profile
        existing_profile = UserProfile(
            telegram_id=12345,
            username="john_doe",
            first_name="John",
            created_at=datetime.now(),
            is_pro=True,
            daily_submissions=2,
            last_submission_date=date.today(),
            total_submissions=15
        )
        
        mock_service_instance = AsyncMock()
        mock_service_instance.get_or_create_user.return_value = existing_profile
        mock_user_service.return_value = mock_service_instance
        
        # Execute handler
        await handle_start_command(mock_message, mock_session)
        
        # Verify message was sent with correct greeting
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        assert "Hello John!" in call_args[1]['text']


class TestSubmissionHandler:
    """Test cases for text submission handler."""
    
    @pytest.fixture
    def mock_message(self):
        """Create mock message with text."""
        message = MagicMock()
        message.from_user = MagicMock()
        message.from_user.id = 12345
        message.from_user.username = "john_doe"
        message.from_user.first_name = "John"
        message.text = "This is a sample IELTS Task 2 essay about education..."
        message.answer = AsyncMock()
        return message
    
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
    
    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return AsyncMock()
    
    @pytest.fixture
    def mock_successful_evaluation(self):
        """Create mock successful evaluation result."""
        assessment = StructuredAssessment(
            task_achievement_score=7.0,
            coherence_cohesion_score=6.5,
            lexical_resource_score=7.5,
            grammatical_accuracy_score=6.0,
            overall_band_score=6.8,
            detailed_feedback="Good essay with clear arguments...",
            improvement_suggestions=["Work on grammar accuracy", "Use more varied vocabulary"],
            score_justifications={"task_achievement": "Clear position presented"}
        )
        
        return EvaluationResult(
            success=True,
            submission_id=123,
            assessment=assessment,
            validation_result=ValidationResult(
                is_valid=True,
                word_count=280,
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
    
    @patch('src.handlers.submission_handler.create_evaluation_service')
    @patch('src.handlers.submission_handler.RateLimitService')
    @patch('src.handlers.submission_handler.UserService')
    async def test_handle_text_submission_success(
        self, mock_user_service, mock_rate_limit_service, mock_eval_service,
        mock_message, mock_state, mock_session, mock_successful_evaluation
    ):
        """Test successful text submission handling."""
        # Setup mocks
        mock_processing_msg = AsyncMock()
        mock_processing_msg.delete = AsyncMock()
        mock_message.answer.return_value = mock_processing_msg
        
        # Rate limit service
        rate_limit_result = RateLimitResult(
            status=RateLimitStatus.ALLOWED,
            current_count=1,
            daily_limit=3,
            remaining=2,
            can_submit=True
        )
        mock_rate_service_instance = AsyncMock()
        mock_rate_service_instance.check_rate_limit.return_value = rate_limit_result
        mock_rate_limit_service.return_value = mock_rate_service_instance
        
        # User service
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
        
        # Evaluation service
        mock_eval_service_instance = AsyncMock()
        mock_eval_service_instance.evaluate_writing.return_value = mock_successful_evaluation
        mock_eval_service.return_value = mock_eval_service_instance
        
        # Execute handler
        await handle_text_submission(mock_message, mock_state, mock_session)
        
        # Verify processing message was shown and deleted
        assert mock_message.answer.call_count >= 2  # Processing message + result
        mock_processing_msg.delete.assert_called_once()
        
        # Verify state was cleared
        mock_state.clear.assert_called_once()
        
        # Verify evaluation was called
        mock_eval_service_instance.evaluate_writing.assert_called_once()
    
    @patch('src.handlers.submission_handler.create_evaluation_service')
    @patch('src.handlers.submission_handler.RateLimitService')
    async def test_handle_text_submission_rate_limit_exceeded(
        self, mock_rate_limit_service, mock_eval_service,
        mock_message, mock_state, mock_session
    ):
        """Test text submission when rate limit is exceeded."""
        # Setup rate limit exceeded
        rate_limit_result = RateLimitResult(
            status=RateLimitStatus.LIMIT_REACHED,
            current_count=3,
            daily_limit=3,
            remaining=0,
            can_submit=False,
            message="You've reached your daily limit of 3 submissions."
        )
        mock_rate_service_instance = AsyncMock()
        mock_rate_service_instance.check_rate_limit.return_value = rate_limit_result
        mock_rate_limit_service.return_value = mock_rate_service_instance
        
        # Execute handler
        await handle_text_submission(mock_message, mock_state, mock_session)
        
        # Verify error message was sent (may be called multiple times due to processing messages)
        assert mock_message.answer.call_count >= 1
        # Check the final call contains the error message
        final_call = mock_message.answer.call_args
        assert "limited" in final_call[1]['text'] or "error" in final_call[1]['text'].lower()
        
        # Verify state was cleared
        mock_state.clear.assert_called_once()
    
    @patch('src.handlers.submission_handler.create_evaluation_service')
    @patch('src.handlers.submission_handler.RateLimitService')
    @patch('src.handlers.submission_handler.UserService')
    async def test_handle_text_submission_requires_clarification(
        self, mock_user_service, mock_rate_limit_service, mock_eval_service,
        mock_message, mock_state, mock_session
    ):
        """Test text submission that requires task type clarification."""
        # Setup mocks for clarification needed
        mock_processing_msg = AsyncMock()
        mock_processing_msg.delete = AsyncMock()
        mock_message.answer.return_value = mock_processing_msg
        
        # Rate limit OK
        rate_limit_result = RateLimitResult(
            status=RateLimitStatus.ALLOWED,
            current_count=1,
            daily_limit=3,
            remaining=2,
            can_submit=True
        )
        mock_rate_service_instance = AsyncMock()
        mock_rate_service_instance.check_rate_limit.return_value = rate_limit_result
        mock_rate_limit_service.return_value = mock_rate_service_instance
        
        # User service
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
        
        # Evaluation service returns clarification needed
        clarification_result = EvaluationResult(
            success=False,
            requires_task_clarification=True,
            validation_result=ValidationResult(
                is_valid=True,
                word_count=200,
                errors=[],
                warnings=[]
            ),
            task_detection_result=TaskDetectionResult(
                detected_type=None,
                confidence_score=0.4,
                reasoning="Ambiguous content",
                requires_clarification=True
            ),
            error_message="Unable to determine task type. Please specify Task 1 or Task 2."
        )
        mock_eval_service_instance = AsyncMock()
        mock_eval_service_instance.evaluate_writing.return_value = clarification_result
        mock_eval_service.return_value = mock_eval_service_instance
        
        # Execute handler
        await handle_text_submission(mock_message, mock_state, mock_session)
        
        # Verify clarification message was sent
        assert mock_message.answer.call_count >= 2
        
        # Verify state was updated for clarification
        mock_state.update_data.assert_called_with(text=mock_message.text)
        mock_state.set_state.assert_called_with(SubmissionStates.waiting_for_task_clarification)
    
    def test_get_task_clarification_keyboard(self):
        """Test task clarification keyboard creation."""
        keyboard = get_task_clarification_keyboard()
        
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) == 3
        assert keyboard.inline_keyboard[0][0].text == "📄 Task 1 (Charts/Graphs)"
        assert keyboard.inline_keyboard[1][0].text == "📝 Task 2 (Essay)"
        assert keyboard.inline_keyboard[2][0].text == "🔙 Back to Menu"
    
    # async def test_send_evaluation_result(self, mock_message, mock_successful_evaluation):
    #     """Test evaluation result formatting and sending."""
    #     # This function doesn't exist in current implementation
    #     pass


class TestHistoryHandler:
    """Test cases for history handler."""
    
    @pytest.fixture
    def mock_message(self):
        """Create mock message."""
        message = MagicMock()
        message.from_user = MagicMock()
        message.from_user.id = 12345
        message.from_user.username = "john_doe"
        message.from_user.first_name = "John"
        message.answer = AsyncMock()
        return message
    
    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return AsyncMock()
    
    @pytest.fixture
    def mock_user_profile(self):
        """Create mock user profile."""
        return UserProfile(
            telegram_id=12345,
            username="john_doe",
            first_name="John",
            created_at=datetime.now(),
            is_pro=False,
            daily_submissions=2,
            last_submission_date=date.today(),
            total_submissions=5
        )
    
    @pytest.fixture
    def mock_history_data(self):
        """Create mock history data."""
        return [
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
    
    @patch('src.handlers.history_handler.create_evaluation_service')
    @patch('src.handlers.history_handler.UserService')
    async def test_handle_history_request_with_data(
        self, mock_user_service, mock_eval_service,
        mock_message, mock_session, mock_user_profile, mock_history_data
    ):
        """Test history request with existing data."""
        # Setup user service
        mock_user_service_instance = AsyncMock()
        mock_user_service_instance.get_user_profile.return_value = mock_user_profile
        mock_user_service.return_value = mock_user_service_instance
        
        # Setup evaluation service
        mock_eval_service_instance = AsyncMock()
        mock_eval_service_instance.get_user_evaluation_history.return_value = mock_history_data
        mock_eval_service.return_value = mock_eval_service_instance
        
        # Execute handler
        await handle_history_request(mock_message, mock_session)
        
        # Verify services were called
        mock_user_service_instance.get_user_profile.assert_called_once_with(12345)
        mock_eval_service_instance.get_user_evaluation_history.assert_called_once()
        
        # Verify message was sent
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        
        # Check history formatting
        history_text = call_args[1]['text']
        assert "Band Score History - John" in history_text
        assert "Progress Trend:" in history_text
        assert "Recent Submissions:" in history_text
        assert "7.0" in history_text  # Latest score
        assert call_args[1]['parse_mode'] == "Markdown"
    
    @patch('src.handlers.history_handler.UserService')
    async def test_handle_history_request_no_history(
        self, mock_user_service, mock_message, mock_session, mock_user_profile
    ):
        """Test history request with no existing data."""
        # Setup user service
        mock_user_service_instance = AsyncMock()
        mock_user_service_instance.get_user_profile.return_value = mock_user_profile
        mock_user_service.return_value = mock_user_service_instance
        
        # Setup evaluation service to return empty history
        with patch('src.handlers.history_handler.create_evaluation_service') as mock_eval_service:
            mock_eval_service_instance = AsyncMock()
            mock_eval_service_instance.get_user_evaluation_history.return_value = []
            mock_eval_service.return_value = mock_eval_service_instance
            
            # Execute handler
            await handle_history_request(mock_message, mock_session)
        
        # Verify message was sent
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        
        # Check no history message
        history_text = call_args[1]['text']
        assert "You haven't submitted any writing" in history_text
        assert "Get started by:" in history_text
    
    # async def test_send_no_history_message(self, mock_message, mock_user_profile):
    #     """Test no history message formatting."""
    #     # This function doesn't exist in current implementation
    #     pass


class TestCallbackHandler:
    """Test cases for callback query handler."""
    
    @pytest.fixture
    def mock_callback(self):
        """Create mock callback query."""
        callback = MagicMock()
        callback.from_user = MagicMock()
        callback.from_user.id = 12345
        callback.from_user.username = "john_doe"
        callback.from_user.first_name = "John"
        callback.message = MagicMock()
        callback.message.edit_text = AsyncMock()
        callback.answer = AsyncMock()
        callback.data = "test_data"
        return callback
    
    @pytest.fixture
    def mock_state(self):
        """Create mock FSM state."""
        state = AsyncMock(spec=FSMContext)
        state.clear = AsyncMock()
        state.set_state = AsyncMock()
        state.update_data = AsyncMock()
        state.get_data.return_value = {}
        return state
    
    async def test_handle_back_to_menu(self, mock_callback, mock_state):
        """Test back to menu callback."""
        await handle_back_to_menu(mock_callback, mock_state)
        
        # Verify state was cleared
        mock_state.clear.assert_called_once()
        
        # Verify message was edited
        mock_callback.message.edit_text.assert_called_once()
        call_args = mock_callback.message.edit_text.call_args
        assert "Main Menu" in call_args[1]['text']
        
        # Verify callback was answered
        mock_callback.answer.assert_called_once()
    
    async def test_handle_submit_task1(self, mock_callback, mock_state):
        """Test Task 1 submission callback."""
        await handle_submit_task1(mock_callback, mock_state)
        
        # Verify state was set
        mock_state.set_state.assert_called_once_with(SubmissionStates.waiting_for_text)
        mock_state.update_data.assert_called_once_with(task_type=TaskType.TASK_1)
        
        # Verify message was edited
        mock_callback.message.edit_text.assert_called_once()
        call_args = mock_callback.message.edit_text.call_args
        assert "IELTS Writing Task 1 Submission" in call_args[1]['text']
        assert "Tips for Task 1:" in call_args[1]['text']
    
    async def test_handle_submit_task2(self, mock_callback, mock_state):
        """Test Task 2 submission callback."""
        await handle_submit_task2(mock_callback, mock_state)
        
        # Verify state was set
        mock_state.set_state.assert_called_once_with(SubmissionStates.waiting_for_text)
        mock_state.update_data.assert_called_once_with(task_type=TaskType.TASK_2)
        
        # Verify message was edited
        mock_callback.message.edit_text.assert_called_once()
        call_args = mock_callback.message.edit_text.call_args
        assert "IELTS Writing Task 2 Submission" in call_args[1]['text']
        assert "Tips for Task 2:" in call_args[1]['text']
    
    @patch('src.handlers.callback_handler.handle_history_request')
    async def test_handle_show_history(self, mock_history_handler, mock_callback):
        """Test show history callback."""
        mock_session = AsyncMock()
        
        await handle_show_history(mock_callback, mock_session)
        
        # Verify history handler was called
        mock_history_handler.assert_called_once()
        
        # Verify callback was answered
        mock_callback.answer.assert_called_once()
    
    @patch('src.handlers.callback_handler.handle_text_submission')
    async def test_handle_clarify_task1(self, mock_text_handler, mock_callback, mock_state):
        """Test task clarification for Task 1."""
        # Setup state data with stored text
        mock_state.get_data.return_value = {'text': 'Sample writing text...'}
        mock_session = AsyncMock()
        
        await handle_clarify_task1(mock_callback, mock_state, mock_session)
        
        # Verify state was updated
        mock_state.update_data.assert_called_once_with(task_type=TaskType.TASK_1)
        
        # Verify text handler was called
        mock_text_handler.assert_called_once()
        
        # Verify callback was answered
        mock_callback.answer.assert_called_once()
    
    async def test_handle_clarify_task1_no_text(self, mock_callback, mock_state):
        """Test task clarification when no text is stored."""
        # Setup state data without text
        mock_state.get_data.return_value = {}
        mock_session = AsyncMock()
        
        await handle_clarify_task1(mock_callback, mock_state, mock_session)
        
        # Verify error callback was answered
        mock_callback.answer.assert_called_once_with("❌ No text found. Please submit your writing again.")
        
        # Verify state was cleared
        mock_state.clear.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])