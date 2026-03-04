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

# ── Load and CHUNK knowledge base ────────────────────────────────────────────
with open("knowledge.txt", "r", encoding="utf-8") as f:
    FULL_DOCUMENT = f.read()

# Split document into small chunks of ~1500 chars with overlap
CHUNK_SIZE = 1500
OVERLAP = 200

def make_chunks(text, size=CHUNK_SIZE, overlap=OVERLAP):
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks

CHUNKS = make_chunks(FULL_DOCUMENT)
logger.info(f"Document split into {len(CHUNKS)} chunks")

def get_relevant_chunks(query: str, top_n: int = 4) -> str:
    """Find the most relevant chunks for a query using keyword matching."""
    query_words = set(query.lower().split())
    # Remove common stop words
    stop_words = {"what","is","the","a","an","how","when","where","who","why","are","was",
                  "i","me","my","can","do","does","please","tell","about","for","of","in",
                  "to","and","or","it","its","this","that","with","on","at","by","from"}
    keywords = query_words - stop_words
    if not keywords:
        keywords = query_words

    scored = []
    for i, chunk in enumerate(CHUNKS):
        chunk_lower = chunk.lower()
        score = sum(chunk_lower.count(word) for word in keywords)
        scored.append((score, i, chunk))

    # Sort by score descending, take top_n
    scored.sort(key=lambda x: x[0], reverse=True)
    top_chunks = [chunk for _, _, chunk in scored[:top_n]]
    return "\n\n---\n\n".join(top_chunks)


# ── Gemini model ──────────────────────────────────────────────────────────────
SYSTEM_INSTRUCTION = (
    "You are a helpful customer support assistant for the IGNOU BBA in Retailing (BBARIL) programme. "
    "Answer questions using ONLY the document excerpts provided. Be concise and friendly. "
    "Use bullet points with - for lists. "
    "If the answer is not in the excerpts, say: I don't have that specific information. "
    "Please contact IGNOU at www.ignou.ac.in or visit your nearest Regional Centre."
)

MODEL_NAMES = [
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
]

model = None
for _name in MODEL_NAMES:
    try:
        _m = genai.GenerativeModel(model_name=_name, system_instruction=SYSTEM_INSTRUCTION)
        _m.generate_content("hi")
        model = _m
        logger.info(f"Using model: {_name}")
        break
    except Exception as _e:
        logger.warning(f"Model {_name} unavailable: {_e}")

if model is None:
    raise RuntimeError("No working Gemini model found! Check your GEMINI_API_KEY.")

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

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    try:
        # Get only relevant chunks — keeps token usage low
        relevant_context = get_relevant_chunks(user_text)
        prompt = f"Document excerpts:\n\n{relevant_context}\n\nQuestion: {user_text}"

        chat = get_or_create_chat(user_id)
        response = chat.send_message(prompt)
        reply_text = response.text

    except Exception as e:
        logger.error(f"Error for user {user_id}: {e}", exc_info=True)
        reply_text = (
            "Sorry, I ran into an issue. Please try again.\n"
            "Contact IGNOU at www.ignou.ac.in if this persists."
        )

    try:
        await update.message.reply_text(reply_text, parse_mode="Markdown", reply_markup=get_keyboard())
    except Exception:
        await update.message.reply_text(reply_text, reply_markup=get_keyboard())

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("🤖 BBARIL bot is running with Gemini (chunked retrieval)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
