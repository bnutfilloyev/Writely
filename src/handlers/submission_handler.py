"""
Text submission handler for IELTS writing evaluation.
Implements requirements 2.1, 2.2, 2.3, 2.4, 2.5 for text processing and validation.
"""
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from datetime import datetime

from src.services.evaluation_service import EvaluationService, EvaluationRequest
from src.services.user_service import UserService
from src.services.rate_limit_service import RateLimitService
from src.services.result_formatter import ResultFormatter
from src.services.ai_assessment_engine import AIAssessmentEngine
from src.repositories.user_repository import UserRepository
from src.repositories.submission_repository import SubmissionRepository
from src.repositories.assessment_repository import AssessmentRepository
from src.repositories.rate_limit_repository import RateLimitRepository
from src.models.submission import TaskType
from src.exceptions import (
    ErrorHandler, ErrorContext, ValidationError, RateLimitError, 
    DatabaseError, AIServiceError, ConfigurationError
)

# Create global error handler instance
error_handler = ErrorHandler()

logger = logging.getLogger(__name__)
router = Router()


class SubmissionStates(StatesGroup):
    """States for submission workflow."""
    waiting_for_text = State()
    waiting_for_task_clarification = State()


def get_task_clarification_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for task type clarification."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Task 1 (Charts/Graphs)", callback_data="clarify_task1")],
        [InlineKeyboardButton(text="📝 Task 2 (Essay)", callback_data="clarify_task2")],
        [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_menu")]
    ])
    return keyboard


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard with back to menu option."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_menu")]
    ])
    return keyboard


async def create_evaluation_service(session: AsyncSession) -> EvaluationService:
    """Create evaluation service with all dependencies."""
    from src.config.settings import settings
    
    ai_engine = AIAssessmentEngine(
        api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_MODEL,
        base_url=settings.OPENROUTER_BASE_URL,
        site_url=settings.OPENROUTER_SITE_URL,
        site_name=settings.OPENROUTER_SITE_NAME
    )
    user_repo = UserRepository(session)
    submission_repo = SubmissionRepository(session)
    assessment_repo = AssessmentRepository(session)
    rate_limit_repo = RateLimitRepository(session)
    
    return EvaluationService(
        ai_engine=ai_engine,
        user_repo=user_repo,
        submission_repo=submission_repo,
        assessment_repo=assessment_repo,
        rate_limit_repo=rate_limit_repo
    )


@router.message(F.text & ~F.text.startswith('/'))
async def handle_text_submission(message: Message, state: FSMContext, session: AsyncSession):
    """
    Handle text submissions for evaluation with comprehensive error handling.
    
    Requirements:
    - 2.1: Detect task type from content analysis
    - 2.2: Ask user to specify if detection fails
    - 2.3: Validate text is in English
    - 2.4: Check minimum word count (50 words)
    - 2.5: Warn about maximum word count (1000 words)
    - 6.1-6.4: Comprehensive error handling
    """
    current_state = await state.get_state()
    
    # Only process text if we're waiting for submission or in clarification state
    if current_state not in [SubmissionStates.waiting_for_text.state, 
                            SubmissionStates.waiting_for_task_clarification.state, None]:
        return
    
    # Create error context for comprehensive error handling
    error_context = ErrorContext(
        user_id=message.from_user.id,
        username=message.from_user.username,
        message_text=message.text[:100] + "..." if len(message.text) > 100 else message.text,
        handler_name="handle_text_submission",
        timestamp=datetime.now()
    )
    
    processing_msg = None
    
    try:
        # Show processing message for long-running operations
        processing_msg = await error_handler.send_processing_message(
            message, "🔄 Processing your submission..."
        )
        
        # Create evaluation service
        evaluation_service = await create_evaluation_service(session)
        
        # Get user (with error handling)
        try:
            user_service = UserService(session)
            user_profile = await user_service.get_or_create_user(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name
            )
        except Exception as e:
            logger.error(f"Failed to get/create user: {e}")
            raise DatabaseError(
                f"Failed to access user profile: {str(e)}",
                operation="get_or_create_user",
                table="users",
                recoverable=True
            )
        
        # Update processing message
        await error_handler.update_processing_message(
            processing_msg, "🔍 Analyzing your text..."
        )
        
        # Get task type from state if we're in clarification mode
        state_data = await state.get_data()
        forced_task_type = state_data.get('task_type')
        
        # Create evaluation request
        request = EvaluationRequest(
            user_id=user_profile.telegram_id,
            text=message.text,
            task_type=forced_task_type,
            force_task_type=forced_task_type is not None
        )
        
        # Update processing message for AI evaluation
        await error_handler.update_processing_message(
            processing_msg, "🤖 Getting AI assessment..."
        )
        
        # Evaluate the writing
        result = await evaluation_service.evaluate_writing(request)
        
        # Clean up processing message
        await error_handler.cleanup_processing_message(processing_msg)
        processing_msg = None
        
        if result.success:
            # Format and send successful evaluation result
            formatter = ResultFormatter()
            formatted_result = formatter.format_evaluation_result(result)
            
            # Add progress tracking if user has history (with fallback)
            try:
                history = await evaluation_service.get_user_evaluation_history(
                    user_profile.telegram_id, limit=5
                )
                progress_text = formatter.format_progress_tracking(result, history)
            except Exception as e:
                logger.warning(f"Failed to get user history: {e}")
                progress_text = ""
            
            await message.answer(
                text=formatted_result.text + progress_text,
                reply_markup=get_back_to_menu_keyboard(),
                parse_mode=formatted_result.parse_mode
            )
            await state.clear()
            
        elif result.requires_task_clarification:
            # Store text and ask for task type clarification
            await state.update_data(text=message.text)
            await state.set_state(SubmissionStates.waiting_for_task_clarification)
            
            await message.answer(
                text=(
                    "🤔 I couldn't automatically determine if this is a Task 1 or Task 2 writing.\n\n"
                    "Please help me by selecting the correct task type:"
                ),
                reply_markup=get_task_clarification_keyboard()
            )
            
        else:
            # Handle evaluation errors
            formatter = ResultFormatter()
            formatted_error = formatter.format_evaluation_result(result)
            
            await message.answer(
                text=formatted_error.text,
                reply_markup=get_back_to_menu_keyboard(),
                parse_mode=formatted_error.parse_mode
            )
            await state.clear()
            
    except (ValidationError, RateLimitError, DatabaseError, AIServiceError, ConfigurationError) as e:
        # Handle known exceptions with user-friendly responses
        error_response = error_handler.handle_error(e, error_context)
        
        # Clean up processing message
        if processing_msg:
            await error_handler.cleanup_processing_message(processing_msg)
        
        await message.answer(
            text=error_response.message,
            reply_markup=error_response.keyboard or get_back_to_menu_keyboard(),
            parse_mode=error_response.parse_mode
        )
        await state.clear()
        
    except Exception as e:
        # Handle unexpected errors
        error_response = error_handler.handle_error(
            e, error_context, 
            fallback_message="Sorry, there was an error processing your submission. Please try again."
        )
        
        # Clean up processing message
        if processing_msg:
            await error_handler.cleanup_processing_message(processing_msg)
        
        await message.answer(
            text=error_response.message,
            reply_markup=error_response.keyboard or get_back_to_menu_keyboard(),
            parse_mode=error_response.parse_mode
        )
        await state.clear()





@router.message(SubmissionStates.waiting_for_text)
async def handle_awaited_text(message: Message, state: FSMContext, session: AsyncSession):
    """Handle text when specifically waiting for submission."""
    await handle_text_submission(message, state, session)