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

SYSTEM_INSTRUCTION = (
    "You are a helpful and friendly customer support assistant for the BBA in Retailing "
    "(BBARIL) programme at IGNOU (Indira Gandhi National Open University). "
    "Answer questions based ONLY on the programme guide content provided in each message. "
    "Be concise and warm. Use bullet points with * for lists. "
    "If the answer is not in the document say: I don't have that specific information in "
    "the programme guide. Please contact IGNOU directly at www.ignou.ac.in or visit your "
    "nearest Regional Centre. Always be encouraging and supportive to students."
)

# Auto-detect working model
MODEL_NAMES = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-pro",
]

model = None
for _model_name in MODEL_NAMES:
    try:
        _test = genai.GenerativeModel(
            model_name=_model_name,
            system_instruction=SYSTEM_INSTRUCTION,
        )
        _test.generate_content("hi")
        model = _test
        logger.info(f"Using Gemini model: {_model_name}")
        break
    except Exception as _e:
        logger.warning(f"Model {_model_name} not available: {_e}")

if model is None:
    raise RuntimeError("No working Gemini model found! Check your GEMINI_API_KEY.")

# ── Load knowledge base ───────────────────────────────────────────────────────
with open("knowledge.txt", "r", encoding="utf-8") as f:
    DOCUMENT_KNOWLEDGE = f.read()

# ── In-memory chat sessions per user ─────────────────────────────────────────
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
    welcome = (
        f"👋 Hello {user.first_name}! I'm the *IGNOU BBARIL Programme Assistant*.\n\n"
        "I can help you with questions about the *BBA in Retailing* programme — "
        "admissions, courses, fees, examinations, internships, and more.\n\n"
        "Choose a topic below or type your own question:"
    )
    await update.message.reply_text(
        welcome,
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
    help_text = (
        "*BBARIL Programme Assistant — Help*\n\n"
        "I answer questions about the IGNOU BBA in Retailing programme.\n\n"
        "*Commands:*\n"
        "/start — Welcome message & quick questions\n"
        "/reset — Clear conversation history\n"
        "/help — Show this message\n\n"
        "*Topics I can help with:*\n"
        "* Programme overview & eligibility\n"
        "* Fee structure & admission process\n"
        "* Course structure & subjects\n"
        "* Internship & OJT requirements\n"
        "* Assignments & examinations\n"
        "* Regional centres & support services\n\n"
        "Just type your question and I'll answer from the official programme guide!"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text.strip()

    if not user_text:
        return

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING
    )

    try:
        chat = get_or_create_chat(user_id)
        prompt = f"Using this programme guide:\n\n{DOCUMENT_KNOWLEDGE}\n\nAnswer this question: {user_text}"
        response = chat.send_message(prompt)
        reply_text = response.text

    except Exception as e:
        logger.error(f"Gemini API error for user {user_id}: {e}", exc_info=True)
        reply_text = (
            "Sorry, I ran into an issue. Please try again in a moment.\n"
            "If the problem persists, contact IGNOU directly at www.ignou.ac.in"
        )

    # Send reply — fallback to plain text if Markdown parse fails
    try:
        await update.message.reply_text(
            reply_text,
            parse_mode="Markdown",
            reply_markup=get_keyboard()
        )
    except Exception:
        await update.message.reply_text(
            reply_text,
            reply_markup=get_keyboard()
        )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("🤖 BBARIL bot is running with Gemini...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
