import os
import logging
import asyncio
import signal
import sys
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
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

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

# State variables
BOT_IS_ACTIVE = False
application = None  # Global reference for cleanup

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command. Only advisors can use this command."""
    if not update.effective_user:
        logger.warning("Received /start command with no effective user")
        return
        
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id if update.effective_chat else "unknown"

    if user_id not in ADVISOR_USER_IDS:
        logger.info(f"Non-advisor user {user_id} in chat {chat_id} attempted to use /start. Denied.")
        await update.message.reply_text("Sorry, the /start command is only available to advisors.")
        return

    global BOT_IS_ACTIVE
    BOT_IS_ACTIVE = True
    logger.info(f"/start command executed by advisor {user_id}. Bot is now active in chat {chat_id}.")
    
    # Send confirmation to advisor
    await update.message.reply_text("✅ Bot is now active and will respond to student questions.")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /stop command. Only advisors can use this command."""
    if not update.effective_user:
        logger.warning("Received /stop command with no effective user")
        return
        
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id if update.effective_chat else "unknown"

    if user_id not in ADVISOR_USER_IDS:
        logger.info(f"Non-advisor user {user_id} in chat {chat_id} attempted to use /stop. Denied.")
        await update.message.reply_text("Sorry, the /stop command is only available to advisors.")
        return

    global BOT_IS_ACTIVE
    BOT_IS_ACTIVE = False
    logger.info(f"/stop command executed by advisor {user_id}. Bot is now inactive in chat {chat_id}.")
    
    # Send confirmation to advisor
    await update.message.reply_text("⏹️ Bot is now inactive and will not respond to student questions.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the current bot status. Only available to advisors."""
    if not update.effective_user:
        logger.warning("Received /status command with no effective user")
        return
        
    user_id = update.effective_user.id

    if user_id not in ADVISOR_USER_IDS:
        await update.message.reply_text("Sorry, the /status command is only available to advisors.")
        return

    status = "🟢 Active" if BOT_IS_ACTIVE else "🔴 Inactive"
    faq_status = "✅ Loaded" if FAQ_CONTENT else "❌ Not loaded"
    openai_status = "✅ Connected" if client else "❌ Not connected"
    
    status_message = f"""
📊 **Bot Status**
Status: {status}
FAQ: {faq_status}
OpenAI: {openai_status}
Advisors: {len(ADVISOR_USER_IDS)} configured
    """
    
    await update.message.reply_text(status_message, parse_mode='Markdown')

def get_llm_response(user_message: str) -> str:
    """
    Uses OpenAI to:
    1. Determine if the user_message is a question.
    2. If it's a question, answer it using FAQ_CONTENT.
    3. If not a question, return NOT_A_QUESTION_MARKER.
    4. If it's a question but cannot be answered from FAQ_CONTENT, return CANNOT_ANSWER_MARKER.
    """
    if not client:
        logger.error("OpenAI client not initialized. Check OPENAI_API_KEY.")
        return CANNOT_ANSWER_MARKER
        
    if not FAQ_CONTENT: 
        logger.warning("FAQ_CONTENT is not available. Returning CANNOT_ANSWER_MARKER.")
        return CANNOT_ANSWER_MARKER
        
    system_prompt = f"""You are a helpful AI assistant for students. Your knowledge base consists ONLY of the following text:

--- BEGIN FAQ KNOWLEDGE BASE ---
{FAQ_CONTENT}
--- END FAQ KNOWLEDGE BASE ---

Your tasks are:
1. Analyze the user's message.
2. First, determine if the user's message is a question seeking information OR if it's just a statement, greeting, chit-chat, or something that doesn't require an answer from the FAQ.
   * If the message is NOT a question or does not require an answer from the FAQ (e.g., "hello", "thanks", "ok", "good morning", "lol that's funny"), respond with the exact string: {NOT_A_QUESTION_MARKER}
3. If the message IS a question:
   * Try to answer it comprehensively using ONLY the information from the FAQ KNOWLEDGE BASE provided above.
   * If you can find a relevant answer in the FAQ KNOWLEDGE BASE, provide the answer directly. Do not refer to "the FAQ" in your answer, just provide the information as if you know it.
   * If the message is a question, but you cannot find an answer within the FAQ KNOWLEDGE BASE, respond with the exact string: {CANNOT_ANSWER_MARKER}

Do not use any external knowledge or information not present in the FAQ KNOWLEDGE BASE.
Be concise and helpful.
"""
    
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",  # Fixed model name
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            max_tokens=1000  # Prevent overly long responses
        )
        response_text = completion.choices[0].message.content.strip()
        logger.info(f"LLM processed message: '{user_message[:50]}...' -> Response type: {response_text[:50] if len(response_text) > 50 else response_text}")
        return response_text
    except Exception as e:
        logger.error(f"Error calling OpenAI: {e}")
        return CANNOT_ANSWER_MARKER 

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming text messages."""
    # Safety checks
    if not update.message or not update.message.text:
        return
        
    # Advisor check is the very first thing
    if update.effective_user and update.effective_user.id in ADVISOR_USER_IDS:
        logger.info(f"Message from advisor {update.effective_user.id} ignored.")
        return

    # Check if bot is active
    if not BOT_IS_ACTIVE:
        logger.info(f"Bot is inactive. Ignoring message in chat {update.effective_chat.id if update.effective_chat else 'unknown'}.")
        return
        
    user_message = update.message.text.strip()
    chat_id = update.message.chat_id
    
    # Skip commands
    if user_message.startswith("/"):
        return
        
    # Skip empty messages
    if not user_message:
        logger.info("Ignoring empty message.")
        return

    try:
        llm_answer = get_llm_response(user_message)
        
        if llm_answer == NOT_A_QUESTION_MARKER:
            logger.info(f"Message identified as not a question: '{user_message[:50]}...'")
            return
        elif llm_answer == CANNOT_ANSWER_MARKER or not llm_answer: 
            logger.info(f"Cannot answer question: '{user_message[:50]}...'")
            reply_text = f"I'm not sure how to answer that. {ADVISOR_TAG}, could you please help?"
            
            # Notify moderator if configured
            if MODERATOR_CHAT_ID:
                try:
                    chat_title = update.message.chat.title if update.message.chat else f"Chat {chat_id}"
                    message_link = f"https://t.me/c/{str(chat_id)[4:] if str(chat_id).startswith('-100') else chat_id}/{update.message.message_id}"
                    
                    moderator_message = (
                        f"❓ **Student Question Alert**\n"
                        f"**Chat:** {chat_title}\n"
                        f"**Question:** {user_message}\n"
                        f"**Reason:** Bot couldn't find answer in FAQ\n"
                        f"**Link:** {message_link}"
                    )
                    await context.bot.send_message(
                        chat_id=MODERATOR_CHAT_ID, 
                        text=moderator_message,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to send message to moderator chat {MODERATOR_CHAT_ID}: {e}")
            
            await update.message.reply_text(reply_text)
        else:
            logger.info(f"Answered question: '{user_message[:50]}...'")
            await update.message.reply_text(llm_answer)
            
    except Exception as e:
        logger.error(f"Error handling message '{user_message[:50]}...': {e}")
        await update.message.reply_text("Sorry, I encountered an error processing your message. Please try again later.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by updates."""
    logger.error(f"Exception while handling an update: {context.error}")

async def shutdown_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}. Shutting down gracefully...")
    global application
    if application:
        try:
            await application.stop()
            await application.shutdown()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    sys.exit(0)

async def main():
    """Configures and starts the bot with webhook or polling."""
    global application
    
    # Validate required environment variables
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set. Exiting.")
        return
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set. Exiting.")
        return
    if not FAQ_CONTENT: 
        logger.error("FAQ content is missing. Bot's primary function is impaired. Check faq.md.")
        return
    if not ADVISOR_USER_IDS:
        logger.warning("No advisor user IDs configured. Bot commands will not work.")

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    if WEBHOOK_DOMAIN:
        # Webhook mode
        webhook_full_url = f"{WEBHOOK_DOMAIN.rstrip('/')}/{WEBHOOK_URL_PATH.lstrip('/')}"
        logger.info(f"Starting bot in webhook mode")
        logger.info(f"Webhook URL: {webhook_full_url}")
        logger.info(f"Listening on {WEBHOOK_LISTEN_IP}:{WEBHOOK_PORT}")
        
        # Initialize and start the application
        await application.initialize()
        await application.start()
        
        # Set webhook
        await application.bot.set_webhook(
            url=webhook_full_url,
            allowed_updates=Update.ALL_TYPES,
        )
        
        logger.info("Bot started successfully in webhook mode")
        
        # Run webhook - this method handles the event loop properly
        application.run_webhook(
            listen=WEBHOOK_LISTEN_IP,
            port=WEBHOOK_PORT,
            url_path=WEBHOOK_URL_PATH,
            webhook_url=webhook_full_url
        )
    else:
        # Polling mode
        logger.info("Starting bot in polling mode...")
        
        try:
            await application.initialize()
            await application.start()
            logger.info("Bot is running in polling mode. Send /start to activate.")
            
            # Start polling
            await application.updater.start_polling(drop_pending_updates=True)
            
            # Keep running until interrupted
            try:
                while True:
                    await asyncio.sleep(1)
            except (KeyboardInterrupt, SystemExit):
                logger.info("Received shutdown signal...")
        except Exception as e:
            logger.error(f"Error in polling mode: {e}")
        finally:
            logger.info("Shutting down bot...")
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
            logger.info("Bot shut down gracefully.")

def main_sync():
    """Synchronous wrapper for the main function to handle webhook mode properly."""
    global application
    
    # Validate required environment variables
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set. Exiting.")
        return
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set. Exiting.")
        return
    if not FAQ_CONTENT: 
        logger.error("FAQ content is missing. Bot's primary function is impaired. Check faq.md.")
        return
    if not ADVISOR_USER_IDS:
        logger.warning("No advisor user IDs configured. Bot commands will not work.")

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    if WEBHOOK_DOMAIN:
        # Webhook mode - use synchronous approach
        webhook_full_url = f"{WEBHOOK_DOMAIN.rstrip('/')}/{WEBHOOK_URL_PATH.lstrip('/')}"
        logger.info(f"Starting bot in webhook mode")
        logger.info(f"Webhook URL: {webhook_full_url}")
        logger.info(f"Listening on {WEBHOOK_LISTEN_IP}:{WEBHOOK_PORT}")
        
        # Run webhook - this handles initialization internally
        application.run_webhook(
            listen=WEBHOOK_LISTEN_IP,
            port=WEBHOOK_PORT,
            url_path=WEBHOOK_URL_PATH,
            webhook_url=webhook_full_url,
            allowed_updates=Update.ALL_TYPES
        )
    else:
        # Polling mode - use async approach
        asyncio.run(main())

if __name__ == "__main__":
    try:
        if WEBHOOK_DOMAIN:
            # Webhook mode uses synchronous approach
            main_sync()
        else:
            # Polling mode uses async approach
            asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)