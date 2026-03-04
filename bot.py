import os
import json
import logging
import nest_asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import AsyncOpenAI
from duckduckgo_search import AsyncDDGS

# 1. APPLY NEST_ASYNCIO (Fixes the "Event loop is already running" crash)
nest_asyncio.apply()

# --- CONFIGURATION ---
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"

# Initialize OpenAI Async Client
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Enable logging to see what's happening in the terminal
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- THE "ACTION" FUNCTION (TOOL) ---
# 2. ASYNC SEARCH (Fixes the blocking timeout/rate limit crash)
async def search_university_website(query: str) -> str:
    """Performs a live web search to find current information."""
    logger.info(f"Executing web search for: {query}")
    try:
        async with AsyncDDGS() as ddgs:
            results = await ddgs.atext(query, max_results=3)
            
        if results:
            return "\n".join([f"- {res['title']}: {res['body']}" for res in results])
        else:
            return "No recent information found on the web."
    except Exception as e:
        logger.error(f"Search error: {e}")
        return f"Search failed due to an error: {str(e)}"

# Define the Tool Schema for OpenAI
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_university_website",
            "description": "Searches the web for up-to-date, real-time information about university deadlines, exam dates, internships, or notices.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query. E.g., 'IGNOU term end exam submission deadline June 2026 site:ignou.ac.in'",
                    }
                },
                "required": ["query"],
            },
        }
    }
]

# --- TELEGRAM BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a greeting when the user starts the bot."""
    await update.message.reply_text(
        "Hello! I am your student support assistant. Ask me a question about exam dates, submission deadlines, or program updates, and I will check the live web for you."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The core Agentic workflow: Think -> Action -> Resolution"""
    user_text = update.message.text
    chat_id = update.message.chat_id

    # Keep the typing indicator spinning
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')

    # Prepare the initial message for the LLM. 
    # Notice the system prompt is specifically tailored for excellent student support.
    messages = [
        {"role": "system", "content": "You are a highly helpful student support assistant for the IGNOU BBA in Retailing program. If a student asks about dates, deadlines, internships, or current events, ALWAYS use the search_university_website tool to verify the live information before answering. Be encouraging and clear."},
        {"role": "user", "content": user_text}
    ]

    try:
        # Step 1: LLM evaluates the request
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo", 
            messages=messages,
            tools=tools,
            tool_choice="auto" 
        )
        
        response_message = response.choices[0].message
        
        # Step 2: Did the LLM decide to use a tool?
        if response_message.tool_calls:
            tool_call = response_message.tool_calls[0]
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)

            if function_name == "search_university_website":
                # Execute the async search
                search_query = function_args.get("query")
                search_result = await search_university_website(search_query)

                # 3. OPENAI DICTIONARY FIX (Prevents the Pydantic validation crash)
                messages.append(response_message.model_dump(exclude_unset=True))
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": search_result
                })

                # Refresh the typing indicator
                await context.bot.send_chat_action(chat_id=chat_id, action='typing')

                # Step 3: Send live data back to LLM for the final reply
                second_response = await client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=messages
                )
                final_reply = second_response.choices[0].message.content
                await update.message.reply_text(final_reply)

        else:
            # The LLM decided it didn't need to search
            await update.message.reply_text(response_message.content)

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await update.message.reply_text("I'm sorry, I ran into a temporary connection error. Please try asking again in a moment!")

# --- MAIN RUNNER ---
def main():
    """Start the bot."""
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running and listening for messages...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
