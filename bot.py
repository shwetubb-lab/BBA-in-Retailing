import logging
import nest_asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
from duckduckgo_search import DDGS

# 1. APPLY NEST_ASYNCIO (Prevents Telegram event loop crashes)
nest_asyncio.apply()

# --- CONFIGURATION ---
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"

# Initialize Google Gemini
genai.configure(api_key=GEMINI_API_KEY)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- THE "ACTION" FUNCTION (TOOL) ---
# Gemini reads your Python docstrings directly to understand the tool!
def search_university_website(query: str) -> str:
    """Searches the web for up-to-date, real-time information about university deadlines, exam dates, internships, or notices.
    
    Args:
        query: The search query. E.g., 'IGNOU term end exam submission deadline June 2026 site:ignou.ac.in'
    """
    logger.info(f"Executing web search for: {query}")
    try:
        # We use the standard synchronous DDGS here because Gemini's auto-caller handles the execution
        results = DDGS().text(query, max_results=3)
        if results:
            return "\n".join([f"- {res['title']}: {res['body']}" for res in results])
        else:
            return "No recent information found on the web."
    except Exception as e:
        logger.error(f"Search error: {e}")
        return f"Search failed due to an error: {str(e)}"

# --- INITIALIZE GEMINI MODEL ---
# We pass the tool directly and set the system instruction
system_prompt = (
    "You are a highly helpful student support assistant for the IGNOU BBA in Retailing program. "
    "If a student asks about dates, deadlines, internships, or current events, ALWAYS use the "
    "search_university_website tool to verify the live information before answering. Be encouraging and clear."
)

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash", 
    tools=[search_university_website],
    system_instruction=system_prompt
)

# --- TELEGRAM BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a greeting when the user starts the bot."""
    # Create a new, unique chat session for this specific user
    context.user_data['chat_session'] = model.start_chat(enable_automatic_function_calling=True)
    
    await update.message.reply_text(
        "Hello! I am your student support assistant. Ask me a question about exam dates, submission deadlines, or program updates, and I will check the live web for you."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The core workflow using Gemini's auto-function calling."""
    user_text = update.message.text
    chat_id = update.message.chat_id

    # Ensure the user has an active chat session (in case they didn't type /start)
    if 'chat_session' not in context.user_data:
         context.user_data['chat_session'] = model.start_chat(enable_automatic_function_calling=True)
    
    chat_session = context.user_data['chat_session']

    # Keep the typing indicator spinning
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')

    try:
        # Gemini handles the Think -> Action -> Resolution loop automatically!
        # We use send_message_async so it doesn't freeze the Telegram bot.
        response = await chat_session.send_message_async(user_text)
        
        await update.message.reply_text(response.text)

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await update.message.reply_text("I'm sorry, I ran into a temporary connection error. Please try asking again in a moment!")

# --- MAIN RUNNER ---
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Gemini Bot is running and listening for messages...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
