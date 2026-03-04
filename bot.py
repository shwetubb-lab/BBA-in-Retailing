import os
import logging
import google.generativeai as genai
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ChatAction

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Env vars (set these in Railway/Render dashboard — never hardcode!) ────────
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

# ── Configure Gemini ──────────────────────────────────────────────────────────
genai.configure(api_key=GEMINI_API_KEY)

# ── Load knowledge base ───────────────────────────────────────────────────────
with open("knowledge.txt", "r", encoding="utf-8") as f:
    DOCUMENT_KNOWLEDGE = f.read()

SYSTEM_PROMPT = f"""You are a helpful and friendly customer support assistant for the BBA in Retailing (BBARIL) programme at IGNOU (Indira Gandhi National Open University).

You answer questions based ONLY on the programme guide document provided below.

Rules:
- Answer only from the document content
- Be concise, warm, and helpful — this is Telegram, so keep responses readable on mobile
- Use simple formatting: bold with *text*, bullet points with •
- If the answer is not in the document, say: "I don't have that specific information in the programme guide. Please contact IGNOU directly at www.ignou.ac.in or visit your nearest Regional Centre."
- Always be encouraging and supportive to students

PROGRAMME GUIDE DOCUMENT:
{DOCUMENT_KNOWLEDGE}"""

# ── In-memory conversation history per user ───────────────────────────────────
conversation_histories = {}
MAX_HISTORY = 10

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


def get_suggestions_keyboard():
    buttons = [KeyboardButton(q) for q in SUGGESTED_QUESTIONS]
    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)


def get_gemini_response(user_id: int, user_text: str) -> str:
    if user_id not in conversation_histories:
        conversation_histories[user_id] = []

    history = conversation_histories[user_id]

    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=SYSTEM_PROMPT,
    )
    chat = model.start_chat(history=history)
    response = chat.send_message(user_text)
    reply = response.text

    history.append({"role": "user", "parts": user_text})
    history.append({"role": "model", "parts": reply})

    if len(history) > MAX_HISTORY * 2:
        conversation_histories[user_id] = history[-(MAX_HISTORY * 2):]

    return reply


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conversation_histories[user.id] = []

    welcome = (
        f"👋 Hello {user.first_name}! I'm the *IGNOU BBARIL Programme Assistant*.\n\n"
        "I can help you with questions about the *BBA in Retailing* programme — "
        "admissions, courses, fees, examinations, internships, and more.\n\n"
        "Choose a topic below or type your own question:"
    )
    await update.message.reply_text(
        welcome,
        parse_mode="Markdown",
        reply_markup=get_suggestions_keyboard()
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conversation_histories[update.effective_user.id] = []
    await update.message.reply_text(
        "🔄 Conversation reset! Ask me anything about the BBARIL programme.",
        reply_markup=get_suggestions_keyboard()
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
        "• Programme overview & eligibility\n"
        "• Fee structure & admission process\n"
        "• Course structure & subjects\n"
        "• Internship & OJT requirements\n"
        "• Assignments & examinations\n"
        "• Regional centres & support services\n\n"
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
        reply_text = get_gemini_response(user_id, user_text)
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        reply_text = (
            "⚠️ Sorry, I ran into an issue. Please try again in a moment.\n"
            "If the problem persists, contact IGNOU directly at www.ignou.ac.in"
        )

    await update.message.reply_text(
        reply_text,
        parse_mode="Markdown",
        reply_markup=get_suggestions_keyboard()
    )


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
