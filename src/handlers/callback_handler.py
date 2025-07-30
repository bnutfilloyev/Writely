"""
Callback query handler for inline keyboard interactions.
Handles all callback queries from inline keyboards throughout the bot.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from src.handlers.start_handler import get_main_menu_keyboard
from src.handlers.submission_handler import SubmissionStates, handle_text_submission
from src.handlers.history_handler import handle_history_request
from src.models.submission import TaskType

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "back_to_menu")
async def handle_back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Handle back to main menu callback."""
    await state.clear()
    
    welcome_text = """
🏠✨ *Main Menu* ✨🏠


🤖 *Writely Robot* - Your IELTS Writing Coach


🎯 *Choose an option below to continue:*
"""
    
    await callback.message.edit_text(
        text=welcome_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "submit_task1")
async def handle_submit_task1(callback: CallbackQuery, state: FSMContext):
    """Handle Task 1 submission request."""
    await state.set_state(SubmissionStates.waiting_for_text)
    await state.update_data(task_type=TaskType.TASK_1)
    
    task1_text = """
📊✨ *IELTS Writing Task 1 Submission* ✨📊


📈 *Charts, Graphs, Tables & Diagrams*


🎯 *Ready to evaluate your Task 1 writing!*
Please send me your complete response below.

💡 *Pro Tips for Task 1:*
📏 *Length:* Aim for 150+ words
📊 *Overview:* Include main trends/patterns  
🔢 *Data:* Use specific numbers from visuals
📝 *Structure:* Intro → Overview → Details
⏰ *Time:* Should take ~20 minutes


✍️ *Just type or paste your writing below:*
"""
    
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_menu")]
    ])
    
    await callback.message.edit_text(
        text=task1_text,
        reply_markup=back_keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "submit_task2")
async def handle_submit_task2(callback: CallbackQuery, state: FSMContext):
    """Handle Task 2 submission request."""
    await state.set_state(SubmissionStates.waiting_for_text)
    await state.update_data(task_type=TaskType.TASK_2)
    
    task2_text = """
📝✨ *IELTS Writing Task 2 Submission* ✨📝


🎭 *Essays & Opinion Writing*


🎯 *Ready to evaluate your Task 2 essay!*
Please send me your complete response below.

💡 *Pro Tips for Task 2:*
📏 *Length:* Aim for 250+ words
🎯 *Position:* Present a clear stance
💭 *Arguments:* Support with examples
🔗 *Cohesion:* Use linking words
📚 *Vocabulary:* Show range & accuracy
⏰ *Time:* Should take ~40 minutes


✍️ *Just type or paste your essay below:*
"""
    
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_menu")]
    ])
    
    await callback.message.edit_text(
        text=task2_text,
        reply_markup=back_keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "about_bot")
async def handle_about_bot(callback: CallbackQuery):
    """Handle about bot callback."""
    about_text = """
🤖✨ *About Writely Robot* ✨🤖


🎯 *Your AI-Powered IELTS Writing Coach*


🚀 *What I Do:*
📊 Evaluate IELTS Writing Task 1 & Task 2
🎯 Provide detailed band scores (0-9 scale)
💡 Give personalized improvement suggestions
📈 Track your writing progress over time

🧠 *AI Technology:*
🤖 *Model:* Llama 3.1 8B Instruct (Free)
🌐 *Provider:* OpenRouter AI
⚡ *Speed:* Real-time evaluation
🎯 *Accuracy:* IELTS-trained assessment

📊 *Scoring Criteria:*
🎯 *Task Achievement/Response*
🔗 *Coherence & Cohesion*  
📚 *Lexical Resource*
✍️ *Grammatical Range & Accuracy*

👨‍💼 *Created by:* @bnutfilloyev
🆓 *Cost:* Completely FREE to use!
🌟 *Mission:* Help you achieve your IELTS goals


💬 *Ready to improve your writing?* 🚀
"""
    
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_menu")]
    ])
    
    await callback.message.edit_text(
        text=about_text,
        reply_markup=back_keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "show_history")
async def handle_show_history(callback: CallbackQuery, session: AsyncSession):
    """Handle show history callback."""
    # Create a temporary message object for the history handler
    temp_message = callback.message
    temp_message.from_user = callback.from_user
    
    await handle_history_request(temp_message, session)
    await callback.answer()


@router.callback_query(F.data == "show_more_history")
async def handle_show_more_history(callback: CallbackQuery, session: AsyncSession):
    """Handle show more history callback."""
    # Create a temporary message object for the history handler with higher limit
    temp_message = callback.message
    temp_message.from_user = callback.from_user
    
    await handle_history_request(temp_message, session, limit=10)
    await callback.answer()


@router.callback_query(F.data == "clarify_task1")
async def handle_clarify_task1(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Handle task type clarification for Task 1."""
    # Get the stored text from state
    state_data = await state.get_data()
    stored_text = state_data.get('text')
    
    if not stored_text:
        await callback.answer("❌ No text found. Please submit your writing again.")
        await state.clear()
        return
    
    # Update state with task type and process the text
    await state.update_data(task_type=TaskType.TASK_1)
    
    # Create a temporary message object with the stored text
    temp_message = callback.message
    temp_message.text = stored_text
    temp_message.from_user = callback.from_user
    
    # Process the submission with forced task type
    await handle_text_submission(temp_message, state, session)
    await callback.answer()


@router.callback_query(F.data == "clarify_task2")
async def handle_clarify_task2(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Handle task type clarification for Task 2."""
    # Get the stored text from state
    state_data = await state.get_data()
    stored_text = state_data.get('text')
    
    if not stored_text:
        await callback.answer("❌ No text found. Please submit your writing again.")
        await state.clear()
        return
    
    # Update state with task type and process the text
    await state.update_data(task_type=TaskType.TASK_2)
    
    # Create a temporary message object with the stored text
    temp_message = callback.message
    temp_message.text = stored_text
    temp_message.from_user = callback.from_user
    
    # Process the submission with forced task type
    await handle_text_submission(temp_message, state, session)
    await callback.answer()


@router.callback_query()
async def handle_unknown_callback(callback: CallbackQuery):
    """Handle unknown callback queries."""
    logger.warning(f"Unknown callback query: {callback.data} from user {callback.from_user.id}")
    await callback.answer("❌ Unknown action. Please try again.")