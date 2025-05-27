import os
import logging
import asyncio # Added for set_webhook
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
ADVISOR_USER_IDS_STR = os.getenv("ADVISOR_USER_IDS", "")
ADVISOR_USER_IDS = set()
if ADVISOR_USER_IDS_STR:
    try:
        ADVISOR_USER_IDS = set(map(int, ADVISOR_USER_IDS_STR.split(',')))
        logger.info(f"Loaded {len(ADVISOR_USER_IDS)} advisor user IDs: {ADVISOR_USER_IDS}")
    except ValueError:
        logger.error("Invalid format for ADVISOR_USER_IDS. Please use comma-separated integer IDs. Advisors will not be ignored.")

# Webhook settings from environment variables
WEBHOOK_LISTEN_IP = os.getenv("WEBHOOK_LISTEN_IP", "0.0.0.0")
WEBHOOK_PORT = int(os.getenv("PORT", os.getenv("WEBHOOK_PORT", "8080")))
WEBHOOK_URL_PATH = os.getenv("WEBHOOK_URL_PATH", TELEGRAM_TOKEN)
WEBHOOK_DOMAIN = os.getenv("WEBHOOK_DOMAIN")

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
    """Handles the /start command. Only advisors can use this command."""
    user_id = update.effective_user.id if update.effective_user else None
    chat_id = update.effective_chat.id

    if not user_id or user_id not in ADVISOR_USER_IDS:
        logger.info(f"User {user_id} (not an advisor) in chat {chat_id} attempted to use /start. Denied.")
        await update.message.reply_text("Sorry, the /start command is only available to advisors.")
        return

    # User is an advisor, proceed to change state
    global BOT_IS_ACTIVE
    BOT_IS_ACTIVE = True
    logger.info(f"/start command executed by advisor {user_id}. Bot is now active in chat {chat_id}. No reply sent to advisor.")
    # No direct reply to advisor, just log and change state

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /stop command. Only advisors can use this command."""
    user_id = update.effective_user.id if update.effective_user else None
    chat_id = update.effective_chat.id

    if not user_id or user_id not in ADVISOR_USER_IDS:
        logger.info(f"User {user_id} (not an advisor) in chat {chat_id} attempted to use /stop. Denied.")
        await update.message.reply_text("Sorry, the /stop command is only available to advisors.")
        return

    # User is an advisor, proceed to change state
    global BOT_IS_ACTIVE
    BOT_IS_ACTIVE = False
    logger.info(f"/stop command executed by advisor {user_id}. Bot is now inactive in chat {chat_id}. No reply sent to advisor.")
    # No direct reply to advisor, just log and change state

def get_llm_response(user_message: str) -> str:
    """
    Uses OpenAI to:
    1. Determine if the user_message is a question.
    2. If it's a question, answer it using FAQ_CONTENT.
    3. If not a question, return NOT_A_QUESTION_MARKER.
    4. If it's a question but cannot be answered from FAQ_CONTENT, return CANNOT_ANSWER_MARKER.
    """
    if not FAQ_CONTENT: 
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
            temperature=0.2, 
        )
        response_text = completion.choices[0].message.content.strip()
        logger.info(f"LLM raw response for user message '{user_message}': '{response_text}'")
        return response_text
    except Exception as e:
        logger.error(f"Error calling OpenAI: {e}")
        return CANNOT_ANSWER_MARKER 

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming text messages."""
    # Advisor check is the very first thing
    if update.effective_user and update.effective_user.id in ADVISOR_USER_IDS:
        logger.info(f"Message from advisor {update.effective_user.id} in chat {update.effective_chat.id}. Ignoring.")
        return

    # Python treats BOT_IS_ACTIVE as local if assigned to in this scope, 
    # but here we only READ it. So, `global` keyword is not strictly necessary
    # for reading if there's no assignment to BOT_IS_ACTIVE in this function.
    # However, for clarity and consistency, especially if one might add an assignment later,
    # explicitly declaring `global BOT_IS_ACTIVE` can be good practice even for reads.
    # For now, PTB examples often omit it if only reading and it's clear from context.
    # Let's rely on Python's scope rules: it will find BOT_IS_ACTIVE in the global scope if not local.
    if not BOT_IS_ACTIVE: # Reading global state
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
    elif llm_answer == CANNOT_ANSWER_MARKER or not llm_answer: 
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

async def main(): # Changed to async to use await for set_webhook
    """Configures and starts the bot with webhook or polling."""
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set. Exiting.")
        return
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set. Exiting.")
        return
    if not FAQ_CONTENT: 
        logger.error("FAQ content is missing. Bot's primary function is impaired. Check faq.md.")
    if not ADVISOR_USER_IDS_STR:
        logger.warning("ADVISOR_USER_IDS not set. Bot will not ignore advisor messages.")
    elif not ADVISOR_USER_IDS:
        logger.warning("ADVISOR_USER_IDS failed to parse. Advisors will not be ignored.")

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    if WEBHOOK_DOMAIN: # If WEBHOOK_DOMAIN is set, run in webhook mode
        webhook_full_url = f"{WEBHOOK_DOMAIN.rstrip('/')}/{WEBHOOK_URL_PATH.lstrip('/')}"
        logger.info(f"Setting webhook to: {webhook_full_url}")
        logger.info(f"Bot will listen on {WEBHOOK_LISTEN_IP}:{WEBHOOK_PORT} at path /{WEBHOOK_URL_PATH.lstrip('/')}")
        
        await application.bot.set_webhook(
            url=webhook_full_url,
            allowed_updates=Update.ALL_TYPES, # Or specify more granularly like [Update.MESSAGE, Update.CALLBACK_QUERY]
            # drop_pending_updates=True # Optional: drop updates that accumulated while bot was offline
        )
        
        # The PTB library's run_webhook starts its own web server (e.g. aiohttp based)
        # It needs to be run within an asyncio event loop, which ApplicationBuilder handles if main is async
        application.run_webhook(
            listen=WEBHOOK_LISTEN_IP,
            port=WEBHOOK_PORT,
            url_path=WEBHOOK_URL_PATH # This should be just the path part, not the full URL
        )
        logger.info(f"Bot started in webhook mode. Listening on {WEBHOOK_LISTEN_IP}:{WEBHOOK_PORT}")
    else: # Fallback to polling if WEBHOOK_DOMAIN is not set
        logger.info("WEBHOOK_DOMAIN not set. Starting bot in polling mode...")
        logger.info("Bot is starting... Send /start to activate.")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Bot has stopped polling.")

if __name__ == "__main__":
    # For run_webhook to work correctly with ApplicationBuilder, main needs to be run in an event loop
    # If main is async, ApplicationBuilder().token().build() handles this.
    # If there were issues, one might need to explicitly use asyncio.run(main())
    # However, PTB's Application structure usually manages the loop when run_webhook or run_polling is called.
    asyncio.run(main()) # Ensure main runs in an event loop
