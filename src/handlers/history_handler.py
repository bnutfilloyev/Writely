"""
History handler for displaying user's past submissions and scores.
Implements requirements 4.2, 4.3, 4.4 for tracking and displaying submission history.
"""
from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging

from src.services.user_service import UserService
from src.services.evaluation_service import EvaluationService
from src.services.result_formatter import ResultFormatter
from src.services.ai_assessment_engine import AIAssessmentEngine
from src.repositories.user_repository import UserRepository
from src.repositories.submission_repository import SubmissionRepository
from src.repositories.assessment_repository import AssessmentRepository
from src.repositories.rate_limit_repository import RateLimitRepository
from src.models.submission import TaskType

logger = logging.getLogger(__name__)
router = Router()


def get_history_navigation_keyboard(has_more: bool = False) -> InlineKeyboardMarkup:
    """Create navigation keyboard for history display."""
    buttons = []
    
    if has_more:
        buttons.append([InlineKeyboardButton(text="📄 Show More", callback_data="show_more_history")])
    
    buttons.append([InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


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


async def handle_history_request(message: Message, session: AsyncSession, limit: int = 5):
    """
    Handle band score history request.
    
    Requirements:
    - 4.2: Display past submissions with dates and scores
    - 4.3: Show progress trends if multiple submissions exist
    - 4.4: Inform user if no history exists
    """
    try:
        # Get user service
        user_service = UserService(session)
        user_profile = await user_service.get_user_profile(message.from_user.id)
        
        if not user_profile:
            await message.answer(
                text="❌ User profile not found. Please start the bot with /start first.",
                reply_markup=get_history_navigation_keyboard()
            )
            return
        
        # Get evaluation service and history
        evaluation_service = await create_evaluation_service(session)
        history = await evaluation_service.get_user_evaluation_history(
            user_id=user_profile.telegram_id, 
            limit=limit
        )
        
        if not history:
            # No history exists - requirement 4.4
            formatter = ResultFormatter()
            display_name = user_profile.first_name or user_profile.username or "there"
            no_history_message = formatter.format_history_display([], display_name)
            
            await message.answer(
                text=no_history_message.text,
                reply_markup=get_history_navigation_keyboard(),
                parse_mode=no_history_message.parse_mode
            )
            return
        
        # Format and send history using formatter
        formatter = ResultFormatter()
        display_name = user_profile.first_name or user_profile.username or "there"
        formatted_history = formatter.format_history_display(
            history=history,
            user_name=display_name,
            total_submissions=user_profile.total_submissions if hasattr(user_profile, 'total_submissions') else len(history)
        )
        
        await message.answer(
            text=formatted_history.text,
            reply_markup=get_history_navigation_keyboard(len(history) == limit),
            parse_mode=formatted_history.parse_mode
        )
        
    except Exception as e:
        logger.error(f"Error retrieving history for user {message.from_user.id}: {e}")
        await message.answer(
            text="❌ Sorry, there was an error retrieving your history. Please try again later.",
            reply_markup=get_history_navigation_keyboard()
        )


