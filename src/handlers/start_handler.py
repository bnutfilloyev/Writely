"""
Start command handler for the IELTS Telegram bot.
Implements requirement 1.1: Display greeting and main menu options.
"""
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.user_service import UserService

router = Router()


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Create main menu inline keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="� Submit WTask 1 (Charts/Graphs)", callback_data="submit_task1")],
        [InlineKeyboardButton(text="📝 Submit Task 2 (Essays)", callback_data="submit_task2")],
        [InlineKeyboardButton(text="� CView My Progress History", callback_data="show_history")],
        [InlineKeyboardButton(text="ℹ️ About Writely Robot", callback_data="about_bot")]
    ])
    return keyboard


@router.message(CommandStart())
async def handle_start_command(message: Message, session: AsyncSession):
    """
    Handle /start command with greeting and main menu.
    
    Requirements:
    - 1.1: Display greeting message and three options
    """
    user_service = UserService(session)
    
    # Get or create user profile
    user_profile = await user_service.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    
    # Create personalized greeting
    display_name = user_profile.first_name or user_profile.username or "there"
    
    greeting_text = f"""
🤖✨ *Hello {display_name}!* ✨🤖

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 *Welcome to Writely Robot!* 🎯
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚀 *Your AI-powered IELTS writing coach is here!*
Ready to help you achieve your target band score! 📈

✨ *What I can do for you:*
📊 *Task 1:* Charts, graphs, diagrams evaluation
📝 *Task 2:* Essay writing assessment  
🎯 *Scoring:* All four IELTS criteria analyzed
💡 *Feedback:* Personalized improvement tips
📈 *Progress:* Track your writing journey
🤖 *AI Model:* Advanced language analysis

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 *Choose an option below to start improving!* 👇
"""
    
    await message.answer(
        text=greeting_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )