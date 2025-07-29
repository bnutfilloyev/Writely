"""
Simplified text submission handler for IELTS writing evaluation.
Processes text directly without database storage - fully free service.
"""
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging
import os

from src.services.ai_assessment_engine import AIAssessmentEngine, StructuredAssessment
from src.services.text_processor import TextValidator, TaskTypeDetector, ValidationError
from src.services.simple_result_formatter import ResultFormatter
from src.exceptions import AIServiceError

logger = logging.getLogger(__name__)
router = Router()


class SubmissionStates(StatesGroup):
    """States for submission workflow."""
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
    """Create back to menu keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_menu")]
    ])
    return keyboard


async def create_ai_engine() -> AIAssessmentEngine:
    """Create AI assessment engine with configuration from environment."""
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    model = os.getenv("OPENAI_MODEL", "meta-llama/llama-3.1-8b-instruct:free")
    site_url = os.getenv("OPENROUTER_SITE_URL", "https://ielts-telegram-bot.local")
    site_name = os.getenv("OPENROUTER_SITE_NAME", "IELTS Writing Bot")
    
    return AIAssessmentEngine(
        api_key=api_key,
        base_url=base_url,
        model=model,
        site_url=site_url,
        site_name=site_name
    )


@router.message(F.text & ~F.text.startswith('/'))
async def handle_text_submission(message: Message, state: FSMContext):
    """
    Handle text submissions for evaluation - simplified version without database.
    """
    try:
        # Show processing message
        processing_msg = await message.answer("🔄 Processing your submission...")
        
        # Create text validator and task detector
        text_validator = TextValidator()
        task_detector = TaskTypeDetector()
        
        # Validate the text
        validation_result = text_validator.validate_submission(message.text)
        if not validation_result.is_valid:
            await processing_msg.delete()
            # Format the validation errors
            error_messages = []
            for error in validation_result.errors:
                if error == ValidationError.TOO_SHORT:
                    error_messages.append("Text is too short (minimum 50 words required)")
                elif error == ValidationError.TOO_LONG:
                    error_messages.append("Text is too long (maximum 1000 words recommended)")
                elif error == ValidationError.NOT_ENGLISH:
                    error_messages.append("Text must be in English")
                elif error == ValidationError.EMPTY_TEXT:
                    error_messages.append("Text cannot be empty")
                else:
                    error_messages.append(str(error.value))
            
            error_text = "\n".join(error_messages)
            await message.answer(
                f"❌ {error_text}\n\n"
                f"Please fix the issue and try again.",
                reply_markup=get_back_to_menu_keyboard()
            )
            return
        
        # Update processing message
        await processing_msg.edit_text("🔍 Analyzing your text...")
        
        # Get task type from state if we're in clarification mode
        state_data = await state.get_data()
        forced_task_type = state_data.get('task_type')
        
        # Detect task type if not forced
        if forced_task_type:
            task_type = forced_task_type
        else:
            detection_result = task_detector.detect_task_type(message.text)
            if detection_result.confidence_score < 0.7:
                # Store text and ask for clarification
                await state.update_data(text=message.text)
                await state.set_state(SubmissionStates.waiting_for_task_clarification)
                
                await processing_msg.delete()
                await message.answer(
                    "🤔 I couldn't automatically determine if this is a Task 1 or Task 2 writing.\n\n"
                    "Please help me by selecting the correct task type:",
                    reply_markup=get_task_clarification_keyboard()
                )
                return
            
            task_type = detection_result.detected_type
        
        # Update processing message for AI evaluation
        await processing_msg.edit_text("🤖 Getting AI assessment...")
        
        # Create AI engine and get assessment
        ai_engine = await create_ai_engine()
        raw_assessment = await ai_engine.assess_writing(message.text, task_type)
        structured_assessment = ai_engine.parse_response(raw_assessment.content)
        
        # Clean up processing message
        await processing_msg.delete()
        
        # Format and send result
        formatter = ResultFormatter()
        formatted_result = formatter.format_structured_assessment(structured_assessment, task_type)
        
        await message.answer(
            text=formatted_result.text,
            reply_markup=get_back_to_menu_keyboard(),
            parse_mode=formatted_result.parse_mode
        )
        
        # Clear state
        await state.clear()
        
    except AIServiceError as e:
        if 'processing_msg' in locals():
            await processing_msg.delete()
        await message.answer(
            f"🤖 AI Service Error: {str(e)}\n\n"
            f"Please try again in a few moments.",
            reply_markup=get_back_to_menu_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Unexpected error in text submission: {e}")
        if 'processing_msg' in locals():
            await processing_msg.delete()
        await message.answer(
            "❌ An unexpected error occurred. Please try again.",
            reply_markup=get_back_to_menu_keyboard()
        )


@router.message(SubmissionStates.waiting_for_task_clarification)
async def handle_awaited_text(message: Message, state: FSMContext):
    """Handle text when waiting for task clarification."""
    await handle_text_submission(message, state)
