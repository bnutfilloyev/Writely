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
        [InlineKeyboardButton(text="📄 Submit Writing Task 1", callback_data="submit_task1")],
        [InlineKeyboardButton(text="📝 Submit Writing Task 2", callback_data="submit_task2")],
        [InlineKeyboardButton(text="📊 Check Band Score History", callback_data="show_history")]
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
    
    greeting_text = (
        f"👋 Hello {display_name}! Welcome to the IELTS Writing Evaluation Bot.\n\n"
        "I can help you improve your IELTS writing skills by providing detailed feedback "
        "and band scores for both Task 1 and Task 2 essays.\n\n"
        "📝 **What I can do:**\n"
        "• Evaluate your writing with detailed band scores\n"
        "• Provide specific improvement suggestions\n"
        "• Track your progress over time\n"
        "• Support both Task 1 and Task 2 formats\n\n"
        "Choose an option below to get started:"
    )
    
    await message.answer(
        text=greeting_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )