"""
Simplified callback query handler for inline keyboard interactions.
Handles callbacks without database operations.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import logging

from src.handlers.simple_start_handler import get_main_menu_keyboard
from src.handlers.simple_submission_handler import SubmissionStates, handle_text_submission
from src.models.enums import TaskType

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "back_to_menu")
async def handle_back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Handle back to main menu callback."""
    await state.clear()
    
    welcome_text = """
🏠 *Main Menu*

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
    await state.clear()  # Clear any previous state
    
    task1_text = """
📊 *IELTS Writing Task 1 Submission*

🎯 *Task 1 Requirements:*
• Charts, Graphs, Tables, or Diagrams analysis
• 150+ words minimum
• Academic tone and vocabulary
• Clear data interpretation and trends

✍️ *Ready to submit?*
Just send me your Task 1 writing and I'll evaluate it instantly!

🚀 *100% FREE* - No registration required!
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
    await state.clear()  # Clear any previous state
    
    task2_text = """
📝 *IELTS Writing Task 2 Submission*

🎯 *Task 2 Requirements:*
• Opinion/Discussion Essay
• 250+ words minimum
• Clear position and arguments
• Formal academic style

✍️ *Ready to submit?*
Just send me your Task 2 essay and I'll evaluate it instantly!

🚀 *100% FREE* - No registration required!
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


@router.callback_query(F.data == "clarify_task1")
async def handle_clarify_task1(callback: CallbackQuery, state: FSMContext):
    """Handle Task 1 clarification."""
    await state.update_data(task_type=TaskType.TASK_1)
    
    # Get the stored text from state
    state_data = await state.get_data()
    text = state_data.get('text', '')
    
    if text:
        # Create a fake message object to process the text
        class FakeMessage:
            def __init__(self, text: str, user_id: int):
                self.text = text
                self.from_user = type('obj', (object,), {'id': user_id})()
            
            async def answer(self, text: str, **kwargs):
                # Return a fake message response that can be edited/deleted
                class FakeMessageResponse:
                    async def edit_text(self, text: str, **kwargs):
                        await callback.message.edit_text(text=text, **kwargs)
                    
                    async def delete(self):
                        pass  # Can't delete callback message
                
                # First edit the callback message
                await callback.message.edit_text(text=text, **kwargs)
                return FakeMessageResponse()
        
        fake_message = FakeMessage(text, callback.from_user.id)
        await handle_text_submission(fake_message, state)
    else:
        await callback.answer("❌ No text found. Please submit your writing again.")
    
    await callback.answer()


@router.callback_query(F.data == "clarify_task2")
async def handle_clarify_task2(callback: CallbackQuery, state: FSMContext):
    """Handle Task 2 clarification."""
    await state.update_data(task_type=TaskType.TASK_2)
    
    # Get the stored text from state
    state_data = await state.get_data()
    text = state_data.get('text', '')
    
    if text:
        # Create a fake message object to process the text
        class FakeMessage:
            def __init__(self, text: str, user_id: int):
                self.text = text
                self.from_user = type('obj', (object,), {'id': user_id})()
            
            async def answer(self, text: str, **kwargs):
                # Return a fake message response that can be edited/deleted
                class FakeMessageResponse:
                    async def edit_text(self, text: str, **kwargs):
                        await callback.message.edit_text(text=text, **kwargs)
                    
                    async def delete(self):
                        pass  # Can't delete callback message
                
                # First edit the callback message
                await callback.message.edit_text(text=text, **kwargs)
                return FakeMessageResponse()
        
        fake_message = FakeMessage(text, callback.from_user.id)
        await handle_text_submission(fake_message, state)
    else:
        await callback.answer("❌ No text found. Please submit your writing again.")
    
    await callback.answer()


@router.callback_query(F.data == "view_history")
async def handle_view_history(callback: CallbackQuery, state: FSMContext):
    """Handle history request - simplified to just show info."""
    await state.clear()
    
    history_text = """
📈 *Writing History*

ℹ️ *History Feature Not Available*

This is a *simplified, database-free version* of the IELTS Writing Bot.

🚀 *Features Available:*
• ✅ Instant AI evaluation
• ✅ Task 1 & Task 2 support  
• ✅ Detailed feedback
• ✅ 100% FREE access

💡 *No Registration Required* - Just submit your writing and get instant feedback!
"""
    
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_menu")]
    ])
    
    await callback.message.edit_text(
        text=history_text,
        reply_markup=back_keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()
