import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
from openai import OpenAI
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODERATOR_CHAT_ID = os.getenv("MODERATOR_CHAT_ID")
ADVISOR_TAG = os.getenv("ADVISOR_TAG", "@advisors")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Load raw FAQ content at startup
FAQ_CONTENT = ""
try:
    with open("faq.md", "r", encoding="utf-8") as f:
        FAQ_CONTENT = f.read()
    if FAQ_CONTENT:
        logger.info(f"Successfully loaded FAQ content from faq.md ({len(FAQ_CONTENT)} characters).")
    else:
        logger.warning("faq.md is empty. Bot may not be able to answer questions accurately.")
except FileNotFoundError:
    logger.error("faq.md not found. Bot will not be able to answer questions from FAQ.")
except Exception as e:
    logger.error(f"Error reading faq.md: {e}")

# Special markers
NOT_A_QUESTION_MARKER = "[NOT_A_QUESTION]"
CANNOT_ANSWER_MARKER = "[CANNOT_ANSWER]"

# State variable to control bot's activity
BOT_IS_ACTIVE = False

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    global BOT_IS_ACTIVE
    BOT_IS_ACTIVE = True
    await update.message.reply_text("Hello! I'm now active and ready to help with FAQs. Send your questions!")
    logger.info(f"/start command received. Bot is now active in chat {update.effective_chat.id}.")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /stop command."""
    global BOT_IS_ACTIVE
    BOT_IS_ACTIVE = False
    await update.message.reply_text("I've been stopped. I will ignore messages until you send /start.")
    logger.info(f"/stop command received. Bot is now inactive in chat {update.effective_chat.id}.")

def get_llm_response(user_message: str) -> str:
    """
    Uses OpenAI to:
    1. Determine if the user_message is a question.
    2. If it's a question, answer it using FAQ_CONTENT.
    3. If not a question, return NOT_A_QUESTION_MARKER.
    4. If it's a question but cannot be answered from FAQ_CONTENT, return CANNOT_ANSWER_MARKER.
    """
    if not FAQ_CONTENT: # If FAQ content failed to load
        logger.warning("FAQ_CONTENT is not available. Returning CANNOT_ANSWER_MARKER.")
        return CANNOT_ANSWER_MARKER

    system_prompt = f"""You are a helpful AI assistant for students. Your knowledge base consists ONLY of the following text:
--- BEGIN FAQ KNOWLEDGE BASE ---
{FAQ_CONTENT}
--- END FAQ KNOWLEDGE BASE ---

Your tasks are:
1.  Analyze the user's message.
2.  First, determine if the user's message is a question seeking information OR if it's just a statement, greeting, chit-chat, or something that doesn't require an answer from the FAQ.
    *   If the message is NOT a question or does not require an answer from the FAQ (e.g., "hello", "thanks", "ok", "good morning", "lol that's funny"), respond with the exact string: {NOT_A_QUESTION_MARKER}
3.  If the message IS a question:
    *   Try to answer it comprehensively using ONLY the information from the FAQ KNOWLEDGE BASE provided above.
    *   If you can find a relevant answer in the FAQ KNOWLEDGE BASE, provide the answer directly. Do not refer to "the FAQ" in your answer, just provide the information as if you know it.
    *   If the message is a question, but you cannot find an answer within the FAQ KNOWLEDGE BASE, respond with the exact string: {CANNOT_ANSWER_MARKER}

Do not use any external knowledge or information not present in the FAQ KNOWLEDGE BASE.
Be concise and helpful.
"""

    try:
        completion = client.chat.completions.create(
            model="gpt-4.1-mini-2025-04-14",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2, # Slightly more creative for answering, but still factual
        )
        response_text = completion.choices[0].message.content.strip()
        logger.info(f"LLM raw response for user message '{user_message}': '{response_text}'")
        return response_text
    except Exception as e:
        logger.error(f"Error calling OpenAI: {e}")
        return CANNOT_ANSWER_MARKER # Fallback if API call fails

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming text messages."""
    global BOT_IS_ACTIVE
    if not BOT_IS_ACTIVE:
        if update.message.text and not update.message.text.startswith('/'):
            logger.info(f"Bot is not active. Ignoring message in chat {update.effective_chat.id}.")
        return

    user_message = update.message.text
    chat_id = update.message.chat_id

    if not user_message or user_message.startswith("/"):
        if not user_message:
            logger.info("Ignoring empty message.")
        return

    llm_answer = get_llm_response(user_message)

    if llm_answer == NOT_A_QUESTION_MARKER:
        logger.info(f"Message '{user_message}' identified as not a question. Skipping.")
        return
    elif llm_answer == CANNOT_ANSWER_MARKER or not llm_answer: # also handle empty response as cannot answer
        logger.info(f"LLM indicated it cannot answer or returned empty for: '{user_message}'. Notifying advisors.")
        reply_text = f"I'm not sure how to answer that. {ADVISOR_TAG}, could you please help?"
        
        if MODERATOR_CHAT_ID:
            try:
                moderator_message = (
                    f"❓ Student question in chat {update.message.chat.title or chat_id} "
                    f"(message link: {update.message.link}):\n"
                    f"{user_message}\n\n"
                    f"🤖 Bot couldn't find an answer in the FAQ or failed to process."
                )
                await context.bot.send_message(chat_id=MODERATOR_CHAT_ID, text=moderator_message)
            except Exception as e:
                logger.error(f"Failed to send message to moderator chat {MODERATOR_CHAT_ID}: {e}")
        
        await update.message.reply_text(reply_text)
    else:
        logger.info(f"LLM provided answer for: '{user_message}'. Replying.")
        await update.message.reply_text(llm_answer)

def main():
    """Starts the bot."""
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set. Exiting.")
        return
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set. Exiting.")
        return
    if not FAQ_CONTENT: # Added check here
        logger.error("FAQ content is missing or could not be loaded. Bot's primary function is impaired. Please check faq.md.")
        # Decide if you want to exit or run with impaired functionality
        # return # Uncomment to exit if FAQ is critical

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is starting... Send /start to activate.")
    application.run_polling()
    logger.info("Bot has stopped.")

if __name__ == "__main__":
    main()
