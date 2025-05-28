import os
import sys
import logging
import asyncio
import json
import time
from datetime import datetime
from aiohttp import web
from telegram import Update, ReactionTypeEmoji
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters, MessageReactionHandler
from telegram.constants import ChatAction
from openai import OpenAI
from openai.types.chat import ChatCompletionUserMessageParam, ChatCompletionSystemMessageParam
from dotenv import load_dotenv
from typing import List, Union

def setup_logging():
    """Set up logging that outputs everything to stdout."""
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s() - %(message)s'
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)

    return logging.getLogger(__name__)

# Initialize logging
logger = setup_logging()

load_dotenv()
logger.info("=== Bot Starting Up ===")
logger.debug("Loading environment variables...")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODERATOR_CHAT_ID = os.getenv("MODERATOR_CHAT_ID")
ADVISOR_USER_IDS_STR = os.getenv("ADVISOR_USER_IDS", "")
ADVISOR_USER_IDS = set()

# Log environment variable status
logger.debug(f"TELEGRAM_TOKEN: {'✓ Set' if TELEGRAM_TOKEN else '✗ Missing'}")
logger.debug(f"OPENAI_API_KEY: {'✓ Set' if OPENAI_API_KEY else '✗ Missing'}")
logger.debug(f"MODERATOR_CHAT_ID: {'✓ Set' if MODERATOR_CHAT_ID else '✗ Missing'}")
logger.debug(f"ADVISOR_USER_IDS_STR: {ADVISOR_USER_IDS_STR}")

if ADVISOR_USER_IDS_STR:
    try:
        ADVISOR_USER_IDS = set(map(int, ADVISOR_USER_IDS_STR.split(',')))
        logger.info(f"✓ Loaded {len(ADVISOR_USER_IDS)} advisor user IDs: {ADVISOR_USER_IDS}")
    except ValueError as e:
        logger.error(f"✗ Invalid format for ADVISOR_USER_IDS: {e}. Advisors will not be ignored.")

# Webhook settings
WEBHOOK_LISTEN_IP = os.getenv("WEBHOOK_LISTEN_IP", "0.0.0.0")
WEBHOOK_PORT = int(os.getenv("PORT", os.getenv("WEBHOOK_PORT", "8443")))
WEBHOOK_URL_PATH = os.getenv("WEBHOOK_URL_PATH", TELEGRAM_TOKEN or "")
WEBHOOK_DOMAIN = os.getenv("WEBHOOK_DOMAIN")

logger.debug(f"Webhook config - IP: {WEBHOOK_LISTEN_IP}, Port: {WEBHOOK_PORT}, Domain: {WEBHOOK_DOMAIN}")

# Initialize OpenAI client
try:
    client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
    if client:
        logger.info("✓ OpenAI client initialized successfully")
    else:
        logger.warning("✗ OpenAI client not initialized - API key missing")
except Exception as e:
    logger.error(f"✗ Failed to initialize OpenAI client: {e}")
    client = None

# Load FAQ content
FAQ_CONTENT = ""
try:
    logger.debug("Attempting to load FAQ content from faq.md...")
    with open("faq.md", "r", encoding="utf-8") as f:
        FAQ_CONTENT = f.read()
    if FAQ_CONTENT:
        logger.info(f"✓ Successfully loaded FAQ content from faq.md ({len(FAQ_CONTENT)} characters)")
    else:
        logger.warning("✗ faq.md is empty")
except FileNotFoundError:
    logger.error("✗ faq.md not found")
except Exception as e:
    logger.error(f"✗ Error reading faq.md: {e}")

# Special markers
NOT_A_QUESTION_MARKER = "[NOT_A_QUESTION]"
CANNOT_ANSWER_MARKER = "[CANNOT_ANSWER]"

logger.debug(f"Special markers configured: NOT_A_QUESTION='{NOT_A_QUESTION_MARKER}', CANNOT_ANSWER='{CANNOT_ANSWER_MARKER}'")

# State variables
BOT_IS_ACTIVE = True
application = None

def log_user_info(update: Update, action: str, additional_info: str = ""):
    """Log user information consistently with enhanced details."""
    user = update.effective_user
    chat = update.effective_chat

    user_info = {
        'user_id': user.id if user else 'unknown',
        'username': user.username if user else 'unknown',
        'first_name': user.first_name if user else 'unknown',
        'last_name': user.last_name if user else 'unknown',
        'chat_id': chat.id if chat else 'unknown',
        'chat_type': chat.type if chat else 'unknown',
        'chat_title': getattr(chat, 'title', 'private') if chat else 'unknown',
        'action': action,
        'timestamp': datetime.now().isoformat(),
        'additional_info': additional_info
    }

    logger.info(f"USER_ACTION: {json.dumps(user_info, ensure_ascii=False)}")
    return user_info

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command for advisors only."""
    logger.debug("Processing /start command...")

    if not update.message or not update.effective_user:
        logger.warning("✗ Received /start command with no message or user")
        return

    user_id = update.effective_user.id

    if user_id not in ADVISOR_USER_IDS:
        logger.warning(f"✗ Non-advisor user {user_id} attempted to use /start")
        log_user_info(update, "start_command_denied", "User not in advisor list")
        await update.message.reply_text("Sorry, this command is only available to advisors.")
        return

    global BOT_IS_ACTIVE
    old_status = BOT_IS_ACTIVE
    BOT_IS_ACTIVE = True

    logger.info(f"✓ /start command executed by advisor {user_id}. Status: {old_status} -> {BOT_IS_ACTIVE}")
    log_user_info(update, "start_command_success", f"Bot activated, previous_status={old_status}")

    await update.message.reply_text("✅ Bot is now active and will respond to student questions.")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /stop command for advisors only."""
    logger.debug("Processing /stop command...")

    if not update.message or not update.effective_user:
        logger.warning("✗ Received /stop command with no message or user")
        return

    user_id = update.effective_user.id

    if user_id not in ADVISOR_USER_IDS:
        logger.warning(f"✗ Non-advisor user {user_id} attempted to use /stop")
        log_user_info(update, "stop_command_denied", "User not in advisor list")
        await update.message.reply_text("Sorry, this command is only available to advisors.")
        return

    global BOT_IS_ACTIVE
    old_status = BOT_IS_ACTIVE
    BOT_IS_ACTIVE = False

    logger.info(f"✓ /stop command executed by advisor {user_id}. Status: {old_status} -> {BOT_IS_ACTIVE}")
    log_user_info(update, "stop_command_success", f"Bot deactivated, previous_status={old_status}")

    await update.message.reply_text("⏹️ Bot is now inactive and will not respond to student questions.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the current bot status for advisors."""
    logger.debug("Processing /status command...")

    if not update.message or not update.effective_user:
        logger.warning("✗ Received /status command with no message or user")
        return

    user_id = update.effective_user.id

    if user_id not in ADVISOR_USER_IDS:
        logger.warning(f"✗ Non-advisor user {user_id} attempted to use /status")
        log_user_info(update, "status_command_denied", "User not in advisor list")
        await update.message.reply_text("Sorry, this command is only available to advisors.")
        return

    status = "🟢 Active" if BOT_IS_ACTIVE else "🔴 Inactive"
    faq_status = "✅ Loaded" if FAQ_CONTENT else "❌ Not loaded"
    openai_status = "✅ Connected" if client else "❌ Not connected"

    status_info = {
        'bot_active': BOT_IS_ACTIVE,
        'faq_loaded': bool(FAQ_CONTENT),
        'openai_connected': bool(client),
        'advisors_count': len(ADVISOR_USER_IDS)
    }

    logger.info(f"✓ Status command executed by advisor {user_id}")
    log_user_info(update, "status_command_success", json.dumps(status_info))

    status_message = f"""
📊 **Bot Status**
Status: {status}
FAQ: {faq_status}
OpenAI: {openai_status}
Advisors: {len(ADVISOR_USER_IDS)} configured
    """

    await update.message.reply_text(status_message, parse_mode='Markdown')

def sanitize_markdown(text: str) -> str:
    """Sanitize markdown text to prevent Telegram parsing errors."""
    if not text:
        return text

    logger.debug(f"Sanitizing markdown text: '{text[:200]}{'...' if len(text) > 200 else ''}'")

    # Fix unmatched markdown characters
    for char in ['*', '_', '`']:
        count = text.count(char)
        if count % 2 != 0:
            last_pos = text.rfind(char)
            if last_pos >= 0:
                text = text[:last_pos] + '\\' + char + text[last_pos + 1:]
                logger.debug(f"Fixed unmatched {char}")

    # Fix unmatched square brackets
    if text.count('[') != text.count(']'):
        text = text.replace('[', '\\[').replace(']', '\\]')
        logger.debug("Fixed unmatched square brackets")

    # Escape other problematic characters
    for char in ['>', '<', '&']:
        if char in text:
            text = text.replace(char, f'\\{char}')

    logger.debug(f"Sanitized text: '{text[:200]}{'...' if len(text) > 200 else ''}'")
    return text

def get_llm_response(user_message: str, user_id: int = 0, chat_id: int = 0) -> str:
    """Get response from OpenAI using FAQ content."""
    start_time = time.time()
    logger.debug(f"Processing LLM request for user {user_id}: '{user_message[:100]}{'...' if len(user_message) > 100 else ''}'")

    if not client:
        logger.error("✗ OpenAI client not initialized")
        return CANNOT_ANSWER_MARKER

    if not FAQ_CONTENT:
        logger.warning("✗ FAQ_CONTENT not available")
        return CANNOT_ANSWER_MARKER

    system_prompt = f"""You are a helpful AI assistant for students. Your knowledge is limited to the following FAQ:

--- BEGIN FAQ ---
{FAQ_CONTENT}
--- END FAQ ---

Instructions:
1. If the user's message is not a question (e.g., greetings, statements), respond with: {NOT_A_QUESTION_MARKER}
2. If the message is a question:
   - Answer briefly and clearly using only the FAQ (use bullet points if necessary), combining relevant parts if necessary.
   - Do not mention the FAQ in your answer.
   - If the question cannot be answered with the FAQ, respond with: {CANNOT_ANSWER_MARKER}

Ensure your response is in valid Markdown format, with proper syntax for *, _, `, [], and (). Be concise and helpful.
"""

    try:
        logger.debug(f"Sending request to OpenAI API for user {user_id}")

        messages: List[Union[ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam]] = [
            ChatCompletionSystemMessageParam(role="system", content=system_prompt),
            ChatCompletionUserMessageParam(role="user", content=user_message),
        ]

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.2,
            max_tokens=1000
        )

        response_text = completion.choices[0].message.content
        if response_text is None:
            response_text = CANNOT_ANSWER_MARKER
        else:
            response_text = response_text.strip()

        processing_time = time.time() - start_time

        response_type = "not_question" if response_text == NOT_A_QUESTION_MARKER else \
                       "cannot_answer" if response_text == CANNOT_ANSWER_MARKER else \
                       "answered"

        logger.info(f"✓ LLM response: {response_type} ({processing_time:.2f}s)")
        logger.debug(f"LLM response preview: '{response_text[:200]}{'...' if len(response_text) > 200 else ''}'")

        if hasattr(completion, 'usage') and completion.usage is not None:
            logger.debug(f"Token usage: Prompt={completion.usage.prompt_tokens}, Completion={completion.usage.completion_tokens}")
        else:
            logger.debug("No token usage data available")

        return response_text

    except Exception as e:
        logger.error(f"✗ Error calling OpenAI: {e}")
        return CANNOT_ANSWER_MARKER

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming text messages with enhanced typing status."""
    if not update.message or not update.message.text or not update.effective_user or not update.effective_chat:
        logger.debug("Message ignored - missing required attributes")
        return

    message_text = update.message.text.strip()
    user = update.effective_user
    chat = update.effective_chat
    chat_id = chat.id

    logger.debug(f"Processing message from user {user.id} in chat {chat_id}: '{message_text[:100]}{'...' if len(message_text) > 100 else ''}'")

    # Skip advisors
    if user.id in ADVISOR_USER_IDS:
        logger.info(f"Message from advisor {user.id} ignored")
        log_user_info(update, "message_ignored", "User is advisor")
        return

    # Check bot status
    if not BOT_IS_ACTIVE:
        logger.info("Bot inactive - ignoring message")
        log_user_info(update, "message_ignored", "Bot inactive")
        return

    # Skip commands and empty messages
    if message_text.startswith("/") or not message_text:
        logger.debug(f"Ignoring {'command' if message_text.startswith('/') else 'empty'} message")
        return

    # Send typing status with enhanced logging
    try:
        logger.debug(f"Sending typing status to chat {chat_id}")
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        logger.info("✓ Typing status sent successfully")
    except Exception as e:
        logger.error(f"✗ Failed to send typing status: {e}")

    log_user_info(update, "message_processing", f"Message: '{message_text[:200]}{'...' if len(message_text) > 200 else ''}'")
    logger.info(f"Processing student message from user {user.id}: '{message_text[:100]}{'...' if len(message_text) > 100 else ''}'")

    try:
        llm_answer = get_llm_response(message_text, user_id=user.id, chat_id=chat_id)
        if llm_answer == NOT_A_QUESTION_MARKER:
            logger.info("Message identified as not a question")
            return

        elif llm_answer == CANNOT_ANSWER_MARKER or not llm_answer:
            logger.info("Cannot answer question")
            log_user_info(update, "message_cannot_answer")

            # Notify moderator
            if MODERATOR_CHAT_ID:
                try:
                    logger.debug(f"Sending notification to moderator chat {MODERATOR_CHAT_ID}")
                    chat_title = chat.title if chat.title else f"Chat {chat_id}"

                    message_link = f"https://t.me/c/{str(chat_id)[4:] if str(chat_id).startswith('-100') else chat_id}/{update.message.message_id}"

                    moderator_message = (
                        f"❓ **Student Question Alert**\n"
                        f"**Chat:** {chat_title}\n"
                        f"**User:** {user.first_name} {user.last_name or ''} (@{user.username or 'no_username'})\n"
                        f"**Question:** {message_text}\n"
                        f"**Link:** {message_link}"
                    )

                    await context.bot.send_message(
                        chat_id=MODERATOR_CHAT_ID,
                        text=moderator_message,
                        parse_mode='Markdown'
                    )
                    logger.info("✓ Moderator notification sent")

                except Exception as e:
                    logger.error(f"✗ Failed to notify moderator: {e}")

        else:
            logger.info("✅ Successfully answered question")
            log_user_info(update, "message_answered", f"Response length: {len(llm_answer)}")

            # Send response with markdown sanitization
            try:
                logger.debug("Attempting to send response with Markdown")
                await update.message.reply_text(llm_answer, parse_mode='Markdown')
                logger.debug("✓ Response sent with Markdown parsing")
            except Exception as markdown_error:
                logger.warning(f"✗ Markdown error: {markdown_error}")
                try:
                    sanitized = sanitize_markdown(llm_answer)
                    await update.message.reply_text(sanitized, parse_mode='Markdown')
                    logger.info("✓ Response sent with sanitized Markdown")
                except Exception as e:
                    logger.error(f"✗ Failed to send sanitized response: {e}")
                    if MODERATOR_CHAT_ID:
                        try:
                            moderator_message = (
                                f"Failed to send answer to user {user.id} "
                                f"(username: {user.username}, name: {user.first_name} {user.last_name or ''}). "
                                f"Please review and forward if appropriate.\n\n"
                                f"Original query: {message_text}\n\nLLM Answer:\n{llm_answer}"
                            )
                            await context.bot.send_message(chat_id=MODERATOR_CHAT_ID, text=moderator_message)
                            logger.info(f"✓ Sent to moderator {MODERATOR_CHAT_ID}")
                        except Exception as final_error:
                            logger.error(f"✗ Failed to notify moderator: {final_error}")

    except Exception as e:
        logger.error(f"✗ Error handling message: {e}")
        log_user_info(update, "message_error", f"Error: {str(e)}")

async def handle_reaction_downvote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles downvote reactions to delete messages with enhanced logging."""
    logger.debug("=== REACTION HANDLER TRIGGERED ===")
    logger.debug(f"Update type: {type(update)}")
    logger.debug(f"Message reaction: {update.message_reaction}")

    if not update.message_reaction or not update.message_reaction.user:
        logger.debug("No message reaction or user found")
        return

    reaction = update.message_reaction
    chat = reaction.chat
    message_id = reaction.message_id
    user = reaction.user
    user_id = user.id if user is not None else None

    logger.info(f"Reaction from user {user_id} in chat {chat.id} for message {message_id}")

    # Only advisors can trigger deletion
    if user_id not in ADVISOR_USER_IDS:
        logger.debug(f"Non-advisor user {user_id} reaction ignored")
        log_user_info(update, "reaction_ignored", "Non-advisor user")
        return

    # Check for new thumbs down reaction
    downvote_emoji = "👎"
    is_new_downvote = False

    if reaction.new_reaction:
        for rtype in reaction.new_reaction:
            if isinstance(rtype, ReactionTypeEmoji) and rtype.emoji == downvote_emoji:
                is_new_downvote = True
                break

    if not is_new_downvote:
        logger.debug("Reaction was not a new thumbs down")
        return

    # Skip deletion in moderator chat
    if MODERATOR_CHAT_ID and str(chat.id) == MODERATOR_CHAT_ID:
        logger.info(f"Skipping deletion in moderator chat {chat.id}")
        log_user_info(update, "downvote_skipped", "Moderator chat")
        return

    # Delete message
    try:
        logger.debug(f"Attempting to delete message {message_id} in chat {chat.id}")
        await context.bot.delete_message(chat_id=chat.id, message_id=message_id)
        logger.info(f"✓ Message {message_id} deleted successfully in chat {chat.id}")
        log_user_info(update, "message_deleted", f"Message {message_id} by advisor {user_id}")
    except Exception as e:
        logger.error(f"✗ Failed to delete message: {e}")
        log_user_info(update, "delete_failed", f"Error: {str(e)}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enhanced error logging."""
    error_info = {
        'error': str(context.error),
        'error_type': type(context.error).__name__,
        'update': str(update) if update else 'None',
        'timestamp': datetime.now().isoformat()
    }

    logger.error(f"✗ Exception: {context.error}")
    logger.debug(f"Error details: {json.dumps(error_info, ensure_ascii=False)}")

    if isinstance(update, Update) and update.effective_user:
        logger.error(f"Error occurred for user {update.effective_user.id}")

async def webhook_handler(request):
    """Handle incoming webhook requests with detailed logging."""
    request_start_time = time.time()
    client_ip = request.remote

    logger.debug(f"Webhook request from {client_ip}")

    if not application:
        logger.error("✗ Application not initialized")
        return web.Response(status=500)

    try:
        data = await request.json()
        logger.debug(f"Webhook data: {json.dumps(data, ensure_ascii=False)[:500]}{'...' if len(str(data)) > 500 else ''}")

        update = Update.de_json(data, application.bot)
        if update:
            logger.debug(f"Processing update: {update}")
            await application.process_update(update)
            processing_time = time.time() - request_start_time
            logger.info(f"✓ Webhook processed in {processing_time:.2f}s")
        else:
            logger.warning("✗ Failed to create Update object")

        return web.Response(status=200)

    except Exception as e:
        logger.error(f"✗ Webhook error: {e}")
        return web.Response(status=500)

async def health_check(request):
    """Health check endpoint with status logging."""
    logger.debug("Health check request")
    health_status = {
        'status': 'healthy',
        'bot_active': BOT_IS_ACTIVE,
        'faq_loaded': bool(FAQ_CONTENT),
        'openai_connected': bool(client),
        'timestamp': datetime.now().isoformat()
    }
    logger.debug(f"Health status: {health_status}")
    return web.Response(text="OK", status=200)

async def main():
    """Main function to start the bot with enhanced initialization logging."""
    global application
    logger.info("=== Bot Initialization ===")

    # Validate configuration
    if not TELEGRAM_TOKEN:
        logger.critical("✗ TELEGRAM_BOT_TOKEN missing - cannot start")
        return
    if not OPENAI_API_KEY:
        logger.warning("✗ OPENAI_API_KEY missing - limited functionality")

    logger.info("Creating Telegram application...")
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    logger.info("✓ Application created")

    logger.debug("Registering reaction handler")
    application.add_handler(MessageReactionHandler(handle_reaction_downvote))

    logger.debug("Registering command handlers")
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("status", status_command))

    logger.debug("Registering message handler")
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.debug("Registering error handler")
    application.add_error_handler(error_handler)
    logger.info("✓ All handlers registered")

    # Initialize application
    logger.debug("Initializing application...")
    await application.initialize()
    await application.start()
    logger.info("✓ Application started")

    # Send restart notification
    if ADVISOR_USER_IDS:
        restart_msg = "✅ Bot restarted and active" + (" (Webhook)" if WEBHOOK_DOMAIN else " (Polling)")
        success_count = 0

        for advisor_id in ADVISOR_USER_IDS:
            try:
                await application.bot.send_message(chat_id=advisor_id, text=restart_msg)
                success_count += 1
                logger.debug(f"Restart notification sent to {advisor_id}")
            except Exception as e:
                logger.error(f"✗ Failed to notify {advisor_id}: {e}")

        logger.info(f"Restart notifications sent: {success_count}/{len(ADVISOR_USER_IDS)}")

    # Start in webhook or polling mode
    if WEBHOOK_DOMAIN and WEBHOOK_URL_PATH:
        logger.info("=== Starting in Webhook Mode ===")
        webhook_url = f"https://{WEBHOOK_DOMAIN.rstrip('/')}/{WEBHOOK_URL_PATH.lstrip('/')}"
        logger.info(f"Webhook URL: {webhook_url}")

        # Set up webhook
        try:
            await application.bot.set_webhook(webhook_url, allowed_updates=["message", "message_reaction"])
            logger.info(f"✓ Webhook set: {webhook_url}")
        except Exception as e:
            logger.error(f"✗ Webhook setup failed: {e}")
            return

        # Create web server
        app = web.Application()
        app.router.add_post(f"/{WEBHOOK_URL_PATH}", webhook_handler)
        app.router.add_get("/health", health_check)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, WEBHOOK_LISTEN_IP, WEBHOOK_PORT)
        await site.start()
        logger.info(f"✓ Web server started on {WEBHOOK_LISTEN_IP}:{WEBHOOK_PORT}")

        # Run indefinitely
        while True:
            await asyncio.sleep(3600)
    else:
        logger.info("=== Starting in Polling Mode ===")
        application.run_polling(allowed_updates=["message", "message_reaction"])

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown signal received")
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
    finally:
        logger.info("=== Bot Shutdown Complete ===")
