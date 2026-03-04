import os
import json
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import AsyncOpenAI
from duckduckgo_search import DDGS

# --- CONFIGURATION ---
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"

# Initialize OpenAI Async Client
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- THE "ACTION" FUNCTION (TOOL) ---
def search_university_website(query: str) -> str:
    """
    Performs a live web search to find current information.
    In a production app, you could replace this with a Google Custom Search API 
    specifically scoped to 'site:ignou.ac.in'.
    """
    logger.info(f"Executing web search for: {query}")
    try:
        results = DDGS().text(query, max_results=3)
        # Combine the snippets from the search results into one text block
        if results:
            return "\n".join([f"- {res['title']}: {res['body']}" for res in results])
        else:
            return "No recent information found on the web."
    except Exception as e:
        return f"Search failed due to an error: {str(e)}"

# Define the Tool Schema for OpenAI so it knows this function exists
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_university_website",
            "description": "Searches the web for up-to-date, real-time information about university deadlines, exam dates, or notices.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to look up. E.g., 'IGNOU term end exam submission deadline June 2026 site:ignou.ac.in'",
                    }
                },
                "required": ["query"],
            },
        }
    }
]

# --- TELEGRAM BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "Hello! I am an intelligent student advisory bot. Ask me a question about exam dates or deadlines, and I will check the live web for you."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The core Agentic workflow: Think -> Action -> Resolution"""
    user_text = update.message.text
    chat_id = update.message.chat_id

    # 1. Keep the typing indicator spinning while we process
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')

    # Prepare the initial message for the LLM
    messages = [
        {"role": "system", "content": "You are a helpful university student support assistant. If a student asks about dates, deadlines, or current events, ALWAYS use the search_university_website tool to verify the information before answering."},
        {"role": "user", "content": user_text}
    ]

    try:
        # 2. THE BRAIN (LLM evaluates the request)
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo", # or gpt-4o for better reasoning
            messages=messages,
            tools=tools,
            tool_choice="auto" 
        )
        
        response_message = response.choices[0].message
        
        # 3. THE TRIGGER (Did the LLM decide to use a tool?)
        if response_message.tool_calls:
            # The LLM wants to search the web!
            tool_call = response_message.tool_calls[0]
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)

            if function_name == "search_university_website":
                # 4. THE ACTION (Execute the local Python function)
                search_query = function_args.get("query")
                search_result = search_university_website(search_query)

                # Append the LLM's tool call request and our tool's result to the history
                messages.append(response_message)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": search_result
                })

                # Refresh the typing indicator since this takes time
                await context.bot.send_chat_action(chat_id=chat_id, action='typing')

                # 5. THE RESOLUTION (Send the live data back to the LLM to write the final reply)
                second_response = await client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=messages
                )
                final_reply = second_response.choices[0].message.content
                await update.message.reply_text(final_reply)

        else:
            # The LLM decided it didn't need to search (e.g., for a simple greeting)
            await update.message.reply_text(response_message.content)

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await update.message.reply_text("Sorry, I ran into an error trying to process your request.")

# --- MAIN RUNNER ---
def main():
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))

    # Message handler for all text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run the bot until the user presses Ctrl-C
    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
