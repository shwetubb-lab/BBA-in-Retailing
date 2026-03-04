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
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

# ── Configure Gemini ──────────────────────────────────────────────────────────
genai.configure(api_key=GEMINI_API_KEY)

# ── Load Knowledge Base ──────────────────────────────────────────────────────
# Instead of chunking, we load the entire document. Gemini 2.5 Flash can easily 
# read and comprehend the whole file instantly.
try:
    with open("knowledge.txt", "r", encoding="utf-8") as f:
        FULL_DOCUMENT = f.read()
    logger.info("Successfully loaded knowledge.txt into memory.")
except FileNotFoundError:
    FULL_DOCUMENT = "The BBARIL programme guide is currently unavailable."
    logger.error("knowledge.txt not found! Please ensure the file is in the directory.")

# ── Gemini model with Search Intelligence ─────────────────────────────────────
SYSTEM_INSTRUCTION = f"""You are the official customer support assistant for the IGNOU BBA in Retailing (BBARIL) programme. 
Your goal is to provide highly accurate, precise, and helpful answers to students.

Below is the complete official Programme Guide. Use this as your primary source of truth.
--- START OF PROGRAMME GUIDE ---
{FULL_DOCUMENT}
--- END OF PROGRAMME GUIDE ---

RULES:
1. Always base your answers on the Programme Guide provided above.
2. If the user asks about live updates, current admission deadlines for this year, or information clearly not in the guide, use your Google Search tool to check www.ignou.ac.in.
3. If you still cannot find the answer after searching the document and the web, state: "I don't have that exact information right now! For the most accurate details, please check the official website at www.ignou.ac.in or reach out to your nearest Regional Centre."
4. Format your responses clearly using bold text and bullet points where helpful.
"""

try:
    # We use Gemini 2.5 Flash and enable the Google Search tool
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_INSTRUCTION,
        tools="google_search_retrieval" # This gives the bot live internet access
    )
    logger.info("Gemini Model initialized successfully with Google Search enabled.")
except Exception as e:
    raise RuntimeError(f"Failed to initialize Gemini model: {e}")

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
    await update.message.reply_text(
        f"👋 Hello {user.first_name}! I'm the *IGNOU BBARIL Programme Assistant*.\n\n"
        "I can help with admissions, courses, fees, examinations, internships and more.\n\n"
        "Choose a topic below or type your own question:",
        parse_mode="Markdown",
        reply_markup=get_keyboard()
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_sessions[update.effective_user.id] = model.start_chat(history=[])
    await update.message.reply_text(
        "🔄 Conversation reset! Ask me anything about the BBARIL programme.",
        reply_markup=get_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*BBARIL Programme Assistant*\n\n"
        "Commands:\n"
        "/start - Welcome & quick questions\n"
        "/reset - Clear conversation\n"
        "/help - This message\n\n"
        "Topics: admissions, fees, courses, internship, exams, support services.",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text.strip()
    
    if not user_text:
        return

    # Show typing indicator while the AI thinks and searches
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    try:
        chat = get_or_create_chat(user_id)
        # The AI now reads the text, checks the whole document in its system instructions, 
        # and runs a Google Search if needed.
        response = chat.send_message(user_text)
        reply_text = response.text

    except Exception as e:
        logger.error(f"Error for user {user_id}: {e}", exc_info=True)
        reply_text = (
            "Oops, I ran into a technical glitch! 🛠️ Please try asking your question again.\n\n"
            "If this keeps happening, you can always find help on the IGNOU website at www.ignou.ac.in."
        )

    try:
        await update.message.reply_text(reply_text, parse_mode="Markdown", reply_markup=get_keyboard())
    except Exception:
        # Fallback if markdown formatting fails
        await update.message.reply_text(reply_text, reply_markup=get_keyboard())

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🤖 BBARIL bot is running with Full Context Memory and Live Web Search...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
