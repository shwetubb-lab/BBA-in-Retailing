import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ChatAction
import google.generativeai as genai

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Env vars ──────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    raise ValueError("CRITICAL ERROR: Missing TELEGRAM_TOKEN or GEMINI_API_KEY. Please check your environment variables.")

# ── Configure Gemini ──────────────────────────────────────────────────────────
genai.configure(api_key=GEMINI_API_KEY)

# ── Load Knowledge Base ──────────────────────────────────────────────────────
try:
    with open("knowledge.txt", "r", encoding="utf-8") as f:
        FULL_DOCUMENT = f.read()
    logger.info("Successfully loaded knowledge.txt into memory.")
except FileNotFoundError:
    FULL_DOCUMENT = "The BBARIL programme guide is currently unavailable."
    logger.error("knowledge.txt not found! Please ensure the file is in the same directory.")

# ── Gemini Model Configuration ────────────────────────────────────────────────
# Here is the upgraded "Verified Facts Only" prompt
SYSTEM_INSTRUCTION = f"""You are the official customer support assistant for the IGNOU BBA in Retailing (BBARIL) programme. 
Your goal is to provide highly accurate, verified, and helpful answers to students.

Below is the complete official Programme Guide. Use this as your primary source of truth for all curriculum, fee, and structural questions.
--- START OF PROGRAMME GUIDE ---
{FULL_DOCUMENT}
--- END OF PROGRAMME GUIDE ---

STRICT VERIFICATION RULES:
1. If the student asks about static information (like what courses are in Semester 1), answer using ONLY the Programme Guide above.
2. If the student asks about LIVE, dynamic, or time-sensitive information (like "What is the exact admission deadline for this year?", "Is the student portal down?", or "Where is the link to pay exam fees?"), YOU MUST USE YOUR GOOGLE SEARCH TOOL.
3. When searching the internet, you must prioritize results from the official IGNOU website (ignou.ac.in). You can append "site:ignou.ac.in" to your search queries to force verified results.
4. If you find the answer on the live web, provide the verified answer and include the exact URL so the student can click it.
5. If you cannot find a verified answer in the guide or on the official website, do NOT guess. State: "I want to make sure I give you verified information, but I don't have that exact detail right now. Please check www.ignou.ac.in directly."
6. Format your responses clearly using bold text and bullet points. Keep it concise.
"""

# Try loading with Google Search tool first. If the server SDK version rejects it, fallback gracefully.
try:
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_INSTRUCTION,
        tools="google_search" 
    )
    logger.info("Gemini Model initialized successfully with Google Search enabled.")
except Exception as e:
    logger.warning(f"Failed to initialize with search tools. Falling back to standard model. Error: {e}")
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_INSTRUCTION
    )
    logger.info("Gemini Model initialized successfully (without explicit search tools).")

# ── Chat sessions ─────────────────────────────────────────────────────────────
chat_sessions = {}

SUGGESTED_QUESTIONS = [
    "What is BBARIL?",
    "Admission requirements",
    "Fee structure",
    "Programme duration",
    "Internship details",
    "Exam & evaluation",
    "Support services",
    "Course structure",
]

def get_keyboard():
    buttons = [KeyboardButton(q) for q in SUGGESTED_QUESTIONS]
    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)

def get_or_create_chat(user_id: int):
    if user_id not in chat_sessions:
        chat_sessions[user_id] = model.start_chat(history=[])
    return chat_sessions[user_id]

# ── Handlers ──────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_sessions[user.id] = model.start_chat(history=[])
    welcome_text = (
        f"👋 Hello {user.first_name}! I'm the *IGNOU BBARIL Programme Assistant*.\n\n"
        "I can help with admissions, courses, fees, examinations, internships and more.\n\n"
        "Choose a topic below or type your own question:"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=get_keyboard())

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_sessions[update.effective_user.id] = model.start_chat(history=[])
    await update.message.reply_text(
        "🔄 Conversation reset! Ask me anything about the BBARIL programme.",
        reply_markup=get_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "*BBARIL Programme Assistant*\n\n"
        "Commands:\n"
        "/start - Welcome & quick questions\n"
        "/reset - Clear conversation\n"
        "/help - This message\n\n"
        "Topics: admissions, fees, courses, internship, exams, support services."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text.strip()
    
    if not user_text:
        return

    # Show typing indicator while the AI thinks and searches the web
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    try:
        chat = get_or_create_chat(user_id)
        
        # Added a 60-second timeout so the AI has time to read the doc AND run a Google Search
        response = chat.send_message(user_text, request_options={"timeout": 60.0})
        reply_text = response.text

    except Exception as e:
        logger.error(f"Error for user {user_id}: {e}", exc_info=True)
        reply_text = (
            "Oops, I ran into a technical glitch! 🛠️ Please try asking your question again.\n\n"
            "If this keeps happening, you can always find help on the IGNOU website at www.ignou.ac.in."
        )

    # Telegram's strict markdown parser sometimes crashes on raw AI text.
    # This try/except ensures the message ALWAYS sends, even if formatting fails.
    try:
        await update.message.reply_text(reply_text, parse_mode="Markdown", reply_markup=get_keyboard())
    except Exception as e:
        logger.warning(f"Markdown parsing failed, falling back to plain text. Error: {e}")
        await update.message.reply_text(reply_text, reply_markup=get_keyboard())

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🤖 BBARIL bot is running with Full Context Memory and Verified Web Grounding...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
