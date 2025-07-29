"""
Simplified start command handler for the IELTS Telegram bot.
No database dependencies - fully free service.
"""
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

router = Router()


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Create main menu inline keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Submit Task 1 (Charts/Graphs)", callback_data="submit_task1")],
        [InlineKeyboardButton(text="📝 Submit Task 2 (Essays)", callback_data="submit_task2")],
        [InlineKeyboardButton(text="📈 View History Info", callback_data="view_history")],
        [InlineKeyboardButton(text="ℹ️ About Writely Robot", callback_data="about_bot")]
    ])
    return keyboard


@router.message(CommandStart())
async def handle_start_command(message: Message):
    """
    Handle /start command with greeting and main menu.
    """
    user_name = message.from_user.first_name or "there"
    
    welcome_text = f"""
🏠 *Welcome {user_name}!*

🤖 *Writely Robot* - Your IELTS Writing Coach

🚀 *100% FREE IELTS Writing Evaluation!*

✅ *What I can help you with:*
📊 • *Task 1:* Charts, graphs, tables analysis
📝 • *Task 2:* Opinion essays and discussions
🎯 • *Instant AI feedback* with detailed scoring
💡 • *Improvement suggestions* for better scores

🎯 *Choose an option below to get started:*
"""
    
    await message.answer(
        text=welcome_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.message(F.text.in_(["/help", "help", "Help"]))
async def handle_help_command(message: Message):
    """Handle help command."""
    help_text = """
❓ *Help & Instructions*

🤖 *How to use Writely Robot:*

1️⃣ *Choose Task Type*
   • Click "📊 Submit Task 1" for charts/graphs
   • Click "📝 Submit Task 2" for essays

2️⃣ *Send Your Writing*
   • Just type or paste your text
   • Minimum 50 words required
   • Maximum 1000 words recommended

3️⃣ *Get Instant Feedback*
   • AI analyzes your writing
   • Detailed scoring breakdown
   • Specific improvement tips

📊 *Scoring Criteria:*
• Task Achievement/Response
• Coherence & Cohesion  
• Lexical Resource
• Grammatical Range & Accuracy

🚀 *Completely FREE* - No registration needed!
"""
    
    await message.answer(
        text=help_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.message(F.text.in_(["/about", "about", "About"]))
async def handle_about_command(message: Message):
    """Handle about command."""
    about_text = """
ℹ️ *About Writely Robot*

🤖 *Writely Robot* is your personal IELTS Writing coach, powered by advanced AI to help you improve your writing skills and achieve higher band scores.

🧠 *AI Technology:*
• Powered by Meta Llama 3.3 70B model
• Trained on IELTS writing standards
• Provides human-like feedback

🎯 *Key Features:*
• ✅ Instant evaluation (under 30 seconds)
• ✅ Band score prediction (0-9 scale)
• ✅ Detailed feedback breakdown
• ✅ Personalized improvement tips
• ✅ Task 1 & Task 2 support
• ✅ 100% FREE access

👨‍💻 *Developer:* @bnutfilloyev
🌟 *Version:* Simplified Free Edition
🔄 *Status:* Active & Continuously Improving

💡 *Tip:* Use this bot regularly to track your progress and improve your IELTS writing skills!
"""
    
    await message.answer(
        text=about_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )
