import os
import logging
import asyncio
import json
import time
from datetime import datetime
from aiohttp import web, ClientSession
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
from openai import OpenAI
from dotenv import load_dotenv

# Enhanced logging configuration
def setup_logging():
    """Set up comprehensive logging with multiple handlers."""
    
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s() - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Console handler (INFO level)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler for all logs (DEBUG level)
    file_handler = logging.FileHandler('logs/bot_debug.log', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)
    
    # File handler for errors only
    error_handler = logging.FileHandler('logs/bot_errors.log', encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(error_handler)
    
    # File handler for user interactions
    interaction_handler = logging.FileHandler('logs/user_interactions.log', encoding='utf-8')
    interaction_handler.setLevel(logging.INFO)
    interaction_handler.setFormatter(detailed_formatter)
    
    # Create a custom logger for user interactions
    interaction_logger = logging.getLogger('user_interactions')
    interaction_logger.addHandler(interaction_handler)
    interaction_logger.setLevel(logging.INFO)
    interaction_logger.propagate = False  # Don't propagate to root logger
    
    return logging.getLogger(__name__), interaction_logger

# Initialize logging
logger, interaction_logger = setup_logging()

load_dotenv()
logger.info("=== Bot Starting Up ===")
logger.debug("Loading environment variables...")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODERATOR_CHAT_ID = os.getenv("MODERATOR_CHAT_ID")
ADVISOR_TAG = os.getenv("ADVISOR_TAG", "@advisors")
ADVISOR_USER_IDS_STR = os.getenv("ADVISOR_USER_IDS", "")
ADVISOR_USER_IDS = set()

# Log environment variable status
logger.debug(f"TELEGRAM_TOKEN: {'✓ Set' if TELEGRAM_TOKEN else '✗ Missing'}")
logger.debug(f"OPENAI_API_KEY: {'✓ Set' if OPENAI_API_KEY else '✗ Missing'}")
logger.debug(f"MODERATOR_CHAT_ID: {'✓ Set' if MODERATOR_CHAT_ID else '✗ Missing'}")
logger.debug(f"ADVISOR_TAG: {ADVISOR_TAG}")
logger.debug(f"ADVISOR_USER_IDS_STR: {ADVISOR_USER_IDS_STR}")

if ADVISOR_USER_IDS_STR:
    try:
        ADVISOR_USER_IDS = set(map(int, ADVISOR_USER_IDS_STR.split(',')))
        logger.info(f"✓ Loaded {len(ADVISOR_USER_IDS)} advisor user IDs: {ADVISOR_USER_IDS}")
    except ValueError as e:
        logger.error(f"✗ Invalid format for ADVISOR_USER_IDS: {e}. Please use comma-separated integer IDs. Advisors will not be ignored.")

# Webhook settings from environment variables
WEBHOOK_LISTEN_IP = os.getenv("WEBHOOK_LISTEN_IP", "0.0.0.0")
WEBHOOK_PORT = int(os.getenv("PORT", os.getenv("WEBHOOK_PORT", "8080")))
WEBHOOK_URL_PATH = os.getenv("WEBHOOK_URL_PATH", TELEGRAM_TOKEN)
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

# Load raw FAQ content at startup
FAQ_CONTENT = ""
try:
    logger.debug("Attempting to load FAQ content from faq.md...")
    with open("faq.md", "r", encoding="utf-8") as f:
        FAQ_CONTENT = f.read()
    if FAQ_CONTENT:
        logger.info(f"✓ Successfully loaded FAQ content from faq.md ({len(FAQ_CONTENT)} characters)")
        logger.debug(f"FAQ preview: {FAQ_CONTENT[:200]}...")
    else:
        logger.warning("✗ faq.md is empty. Bot may not be able to answer questions accurately.")
except FileNotFoundError:
    logger.error("✗ faq.md not found. Bot will not be able to answer questions from FAQ.")
except Exception as e:
    logger.error(f"✗ Error reading faq.md: {e}")

# Special markers
NOT_A_QUESTION_MARKER = "[NOT_A_QUESTION]"
CANNOT_ANSWER_MARKER = "[CANNOT_ANSWER]"

logger.debug(f"Special markers configured: NOT_A_QUESTION='{NOT_A_QUESTION_MARKER}', CANNOT_ANSWER='{CANNOT_ANSWER_MARKER}'")

# State variables
BOT_IS_ACTIVE = True
application = None  # Global reference for cleanup

def log_user_info(update: Update, action: str, additional_info: str = ""):
    """Helper function to log user information consistently."""
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
    
    interaction_logger.info(f"USER_ACTION: {json.dumps(user_info, ensure_ascii=False)}")
    return user_info

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command. Only advisors can use this command."""
    logger.debug("Processing /start command...")
    
    if not update.effective_user:
        logger.warning("✗ Received /start command with no effective user")
        return
    
    user_info = log_user_info(update, "start_command_attempt")
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id if update.effective_chat else "unknown"

    logger.debug(f"Start command from user {user_id} in chat {chat_id}")

    if user_id not in ADVISOR_USER_IDS:
        logger.warning(f"✗ Non-advisor user {user_id} in chat {chat_id} attempted to use /start. Access denied.")
        log_user_info(update, "start_command_denied", "User not in advisor list")
        await update.message.reply_text("Sorry, the /start command is only available to advisors.")
        return

    global BOT_IS_ACTIVE
    old_status = BOT_IS_ACTIVE
    BOT_IS_ACTIVE = True
    
    logger.info(f"✓ /start command executed by advisor {user_id}. Bot status changed: {old_status} -> {BOT_IS_ACTIVE} in chat {chat_id}")
    log_user_info(update, "start_command_success", f"Bot activated, previous_status={old_status}")
    
    # Send confirmation to advisor
    await update.message.reply_text("✅ Bot is now active and will respond to student questions.")
    logger.debug("Start command confirmation sent to advisor")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /stop command. Only advisors can use this command."""
    logger.debug("Processing /stop command...")
    
    if not update.effective_user:
        logger.warning("✗ Received /stop command with no effective user")
        return
    
    user_info = log_user_info(update, "stop_command_attempt")
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id if update.effective_chat else "unknown"

    logger.debug(f"Stop command from user {user_id} in chat {chat_id}")

    if user_id not in ADVISOR_USER_IDS:
        logger.warning(f"✗ Non-advisor user {user_id} in chat {chat_id} attempted to use /stop. Access denied.")
        log_user_info(update, "stop_command_denied", "User not in advisor list")
        await update.message.reply_text("Sorry, the /stop command is only available to advisors.")
        return

    global BOT_IS_ACTIVE
    old_status = BOT_IS_ACTIVE
    BOT_IS_ACTIVE = False
    
    logger.info(f"✓ /stop command executed by advisor {user_id}. Bot status changed: {old_status} -> {BOT_IS_ACTIVE} in chat {chat_id}")
    log_user_info(update, "stop_command_success", f"Bot deactivated, previous_status={old_status}")
    
    # Send confirmation to advisor
    await update.message.reply_text("⏹️ Bot is now inactive and will not respond to student questions.")
    logger.debug("Stop command confirmation sent to advisor")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the current bot status. Only available to advisors."""
    logger.debug("Processing /status command...")
    
    if not update.effective_user:
        logger.warning("✗ Received /status command with no effective user")
        return
    
    user_info = log_user_info(update, "status_command_attempt")
    user_id = update.effective_user.id

    if user_id not in ADVISOR_USER_IDS:
        logger.warning(f"✗ Non-advisor user {user_id} attempted to use /status. Access denied.")
        log_user_info(update, "status_command_denied", "User not in advisor list")
        await update.message.reply_text("Sorry, the /status command is only available to advisors.")
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
    
    logger.info(f"✓ Status command executed by advisor {user_id}. Current status: {status_info}")
    log_user_info(update, "status_command_success", json.dumps(status_info))
    
    status_message = f"""
📊 **Bot Status**
Status: {status}
FAQ: {faq_status}
OpenAI: {openai_status}
Advisors: {len(ADVISOR_USER_IDS)} configured
    """
    
    await update.message.reply_text(status_message, parse_mode='Markdown')
    logger.debug("Status information sent to advisor")

def get_llm_response(user_message: str, user_id: int = None, chat_id: int = None) -> str:
    """
    Uses OpenAI to:
    1. Determine if the user_message is a question.
    2. If it's a question, answer it using FAQ_CONTENT.
    3. If not a question, return NOT_A_QUESTION_MARKER.
    4. If it's a question but cannot be answered from FAQ_CONTENT, return CANNOT_ANSWER_MARKER.
    """
    start_time = time.time()
    logger.debug(f"Processing LLM request for user {user_id} in chat {chat_id}: '{user_message[:100]}{'...' if len(user_message) > 100 else ''}'")
    
    if not client:
        logger.error("✗ OpenAI client not initialized. Check OPENAI_API_KEY.")
        return CANNOT_ANSWER_MARKER
        
    if not FAQ_CONTENT: 
        logger.warning("✗ FAQ_CONTENT is not available. Returning CANNOT_ANSWER_MARKER.")
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
Be concise and helpful, answer must be markdown formatted.
"""
    
    try:
        logger.debug(f"Sending request to OpenAI API for user {user_id}")
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            max_tokens=1000
        )
        
        response_text = completion.choices[0].message.content.strip()
        processing_time = time.time() - start_time
        
        # Log the response details
        response_type = "not_question" if response_text == NOT_A_QUESTION_MARKER else \
                       "cannot_answer" if response_text == CANNOT_ANSWER_MARKER else \
                       "answered"
        
        logger.info(f"✓ LLM processed message from user {user_id}: '{user_message[:50]}{'...' if len(user_message) > 50 else ''}' -> {response_type} ({processing_time:.2f}s)")
        logger.debug(f"LLM response preview: '{response_text[:100]}{'...' if len(response_text) > 100 else ''}'")
        
        # Log token usage if available
        if hasattr(completion, 'usage'):
            logger.debug(f"Token usage - Prompt: {completion.usage.prompt_tokens}, Completion: {completion.usage.completion_tokens}, Total: {completion.usage.total_tokens}")
        
        return response_text
        
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"✗ Error calling OpenAI for user {user_id} after {processing_time:.2f}s: {e}")
        return CANNOT_ANSWER_MARKER 

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming text messages."""
    message_start_time = time.time()
    logger.debug(f"Received message in handle_message: {update.message}")
    
    # Safety checks
    if not update.message or not update.message.text:
        logger.debug("Message ignored - no message or text content")
        return
    
    # Log basic message info
    user = update.effective_user
    chat = update.effective_chat
    message_text = update.message.text.strip()
    
    logger.debug(f"Processing message from user {user.id if user else 'unknown'} in chat {chat.id if chat else 'unknown'}: '{message_text[:100]}{'...' if len(message_text) > 100 else ''}'")
    
    # Advisor check is the very first thing
    if user and user.id in ADVISOR_USER_IDS:
        logger.info(f"Message from advisor {user.id} (@{user.username}) ignored - advisors don't trigger bot responses")
        log_user_info(update, "message_ignored", "User is advisor")
        return

    # Check if bot is active
    if not BOT_IS_ACTIVE:
        logger.info(f"Bot is inactive. Ignoring message from user {user.id if user else 'unknown'} in chat {chat.id if chat else 'unknown'}")
        log_user_info(update, "message_ignored", "Bot inactive")
        return
    
    user_message = message_text
    chat_id = update.message.chat_id
    
    # Skip commands
    if user_message.startswith("/"):
        logger.debug(f"Ignoring command message: {user_message}")
        log_user_info(update, "message_ignored", "Message is command")
        return
        
    # Skip empty messages
    if not user_message:
        logger.debug("Ignoring empty message")
        log_user_info(update, "message_ignored", "Empty message")
        return

    # Log the actual message processing
    log_user_info(update, "message_processing", f"Message: '{user_message[:200]}{'...' if len(user_message) > 200 else ''}'")
    logger.info(f"Processing student message from user {user.id} (@{user.username}) in chat {chat_id}: '{user_message[:100]}{'...' if len(user_message) > 100 else ''}'")

    try:
        llm_answer = get_llm_response(user_message, user_id=user.id, chat_id=chat_id)
        processing_time = time.time() - message_start_time
        
        if llm_answer == NOT_A_QUESTION_MARKER:
            logger.info(f"✓ Message identified as not a question from user {user.id}: '{user_message[:50]}{'...' if len(user_message) > 50 else ''}' ({processing_time:.2f}s)")
            log_user_info(update, "message_not_question", f"Processing time: {processing_time:.2f}s")
            return
            
        elif llm_answer == CANNOT_ANSWER_MARKER or not llm_answer: 
            logger.info(f"✗ Cannot answer question from user {user.id}: '{user_message[:50]}{'...' if len(user_message) > 50 else ''}' ({processing_time:.2f}s)")
            log_user_info(update, "message_cannot_answer", f"Processing time: {processing_time:.2f}s")
        
            # Notify moderator if configured
            if MODERATOR_CHAT_ID:
                try:
                    logger.debug(f"Sending notification to moderator chat {MODERATOR_CHAT_ID}")
                    chat_title = update.message.chat.title if update.message.chat else f"Chat {chat_id}"
                    message_link = f"https://t.me/c/{str(chat_id)[4:] if str(chat_id).startswith('-100') else chat_id}/{update.message.message_id}"
                    
                    moderator_message = (
                        f"❓ **Student Question Alert**\n"
                        f"**Chat:** {chat_title}\n"
                        f"**User:** {user.first_name} {user.last_name or ''} (@{user.username or 'no_username'})\n"
                        f"**Question:** {user_message}\n"
                        f"**Reason:** Bot couldn't find answer in FAQ\n"
                        f"**Link:** {message_link}"
                    )
                    
                    await context.bot.send_message(
                        chat_id=MODERATOR_CHAT_ID, 
                        text=moderator_message,
                        parse_mode='Markdown'
                    )
                    logger.info(f"✓ Moderator notification sent for unanswered question from user {user.id}")
                    
                except Exception as e:
                    logger.error(f"✗ Failed to send message to moderator chat {MODERATOR_CHAT_ID}: {e}")
            else:
                logger.debug("No moderator chat configured - skipping notification")
            
            logger.debug(f"Cannot answer response sent to user {user.id}")
            
        else:
            logger.info(f"✅ Successfully answered question from user {user.id}: '{user_message[:50]}{'...' if len(user_message) > 50 else ''}' ({processing_time:.2f}s)")
            log_user_info(update, "message_answered", f"Processing time: {processing_time:.2f}s, Response length: {len(llm_answer)}")
            
            await update.message.reply_text(llm_answer, parse_mode='Markdown')
            logger.debug(f"Answer sent to user {user.id}, response length: {len(llm_answer)} characters")
            
    except Exception as e:
        processing_time = time.time() - message_start_time
        logger.error(f"✗ Error handling message from user {user.id if user else 'unknown'} after {processing_time:.2f}s: '{user_message[:50]}{'...' if len(user_message) > 50 else ''}': {e}")
        log_user_info(update, "message_error", f"Error: {str(e)}, Processing time: {processing_time:.2f}s")
        
        try:
            await update.message.reply_text("Sorry, I encountered an error processing your message. Please try again later.")
            logger.debug("Error message sent to user")
        except Exception as send_error:
            logger.error(f"✗ Failed to send error message to user: {send_error}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by updates."""
    error_info = {
        'error': str(context.error),
        'error_type': type(context.error).__name__,
        'update': str(update) if update else 'None',
        'timestamp': datetime.now().isoformat()
    }
    
    logger.error(f"✗ Exception while handling an update: {context.error}")
    logger.debug(f"Error details: {json.dumps(error_info, ensure_ascii=False)}")
    
    # Try to extract user info if possible
    if hasattr(update, 'effective_user') and update.effective_user:
        logger.error(f"Error occurred for user {update.effective_user.id} (@{update.effective_user.username})")

# Webhook handler
async def webhook_handler(request):
    """Handle incoming webhook requests."""
    request_start_time = time.time()
    client_ip = request.remote
    
    logger.debug(f"Webhook request received from {client_ip}")
    
    try:
        # Get the JSON data from the request
        data = await request.json()
        logger.debug(f"Webhook data received: {json.dumps(data, ensure_ascii=False)[:500]}{'...' if len(str(data)) > 500 else ''}")
        
        # Create Update object from the webhook data
        update = Update.de_json(data, application.bot)
        
        if update:
            logger.debug(f"Processing webhook update: {update}")
            # Process the update through the application
            await application.process_update(update)
            processing_time = time.time() - request_start_time
            logger.info(f"✓ Webhook processed successfully in {processing_time:.2f}s from {client_ip}")
        else:
            logger.warning(f"✗ Failed to create Update object from webhook data from {client_ip}")
        
        return web.Response(status=200)
        
    except Exception as e:
        processing_time = time.time() - request_start_time
        logger.error(f"✗ Error processing webhook from {client_ip} after {processing_time:.2f}s: {e}")
        return web.Response(status=500)

async def health_check(request):
    """Health check endpoint."""
    client_ip = request.remote
    logger.debug(f"Health check request from {client_ip}")
    
    health_status = {
        'status': 'healthy',
        'bot_active': BOT_IS_ACTIVE,
        'faq_loaded': bool(FAQ_CONTENT),
        'openai_connected': bool(client),
        'timestamp': datetime.now().isoformat()
    }
    
    logger.debug(f"Health check response: {health_status}")
    return web.Response(text="OK", status=200)

async def setup_webhook():
    """Set up the webhook with Telegram."""
    if not WEBHOOK_DOMAIN:
        logger.info("No webhook domain configured - webhook setup skipped")
        return
        
    webhook_url = f"https://{WEBHOOK_DOMAIN.rstrip('/')}/{WEBHOOK_URL_PATH.lstrip('/')}"
    logger.info(f"Setting up webhook: {webhook_url}")
    
    try:
        await application.bot.set_webhook(
            url=webhook_url,
            allowed_updates=Update.ALL_TYPES
        )
        logger.info(f"✓ Webhook set successfully: {webhook_url}")
        
        # Get webhook info for logging
        webhook_info = await application.bot.get_webhook_info()
        logger.debug(f"Webhook info: URL={webhook_info.url}, pending_updates={webhook_info.pending_update_count}")
        
    except Exception as e:
        logger.error(f"✗ Failed to set webhook: {e}")

async def main():
    """Main function to start the bot."""
    global application
    
    logger.info("=== Bot Initialization Starting ===")
    
    # Validate required environment variables
    validation_errors = []
    
    if not TELEGRAM_TOKEN:
        validation_errors.append("TELEGRAM_BOT_TOKEN not set")
    if not OPENAI_API_KEY:
        validation_errors.append("OPENAI_API_KEY not set")
    if not FAQ_CONTENT:
        validation_errors.append("FAQ content is missing (check faq.md)")
    if not ADVISOR_USER_IDS:
        validation_errors.append("No advisor user IDs configured (bot commands will not work)")
    
    if validation_errors:
        for error in validation_errors:
            logger.error(f"✗ {error}")
        if not TELEGRAM_TOKEN or not OPENAI_API_KEY or not FAQ_CONTENT:
            logger.critical("Critical configuration missing. Bot cannot start.")
            return
        else:
            logger.warning("Non-critical configuration issues detected. Bot starting with limited functionality.")

    logger.info("✓ Configuration validation passed")

    # Create application
    logger.debug("Creating Telegram application...")
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    logger.info("✓ Telegram application created")

    # Add handlers
    logger.debug("Adding command and message handlers...")
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    logger.info("✓ All handlers added successfully")

    # Initialize application
    logger.debug("Initializing Telegram application...")
    await application.initialize()
    await application.start()
    logger.info("✓ Telegram application initialized and started")

    # Send restart notification to advisors
    logger.info("Attempting to send restart notification to advisors...")
    restart_message = "✅ Bot has restarted and is now active by default."

    if WEBHOOK_DOMAIN:
        restart_message += " (Mode: Webhook)"
    else:
        restart_message += " (Mode: Polling)"

    notification_delivered = False

    # Try MODERATOR_CHAT_ID first if available
    if MODERATOR_CHAT_ID:
        try:
            logger.debug(f"Sending restart notification to MODERATOR_CHAT_ID: {MODERATOR_CHAT_ID}")
            await application.bot.send_message(
                chat_id=MODERATOR_CHAT_ID,
                text=restart_message,
                parse_mode='Markdown'
            )
            logger.info(f"✓ Restart notification successfully sent to MODERATOR_CHAT_ID: {MODERATOR_CHAT_ID}")
            notification_delivered = True
        except Exception as e:
            logger.error(f"✗ Failed to send restart notification to MODERATOR_CHAT_ID ({MODERATOR_CHAT_ID}): {e}. Will attempt individual advisors if configured.")

    # If not sent via MODERATOR_CHAT_ID (either not configured or failed) AND individual advisors are configured
    if not notification_delivered and ADVISOR_USER_IDS:
        logger.info(f"Attempting to send restart notification to {len(ADVISOR_USER_IDS)} individual advisor(s) as MODERATOR_CHAT_ID was not used or failed.")
        success_ids = []
        failure_details = {} 
        for advisor_id in ADVISOR_USER_IDS:
            try:
                logger.debug(f"Sending restart notification to individual advisor: {advisor_id}")
                await application.bot.send_message(
                    chat_id=advisor_id,
                    text=restart_message,
                    parse_mode='Markdown'
                )
                success_ids.append(str(advisor_id))
            except Exception as e:
                logger.error(f"✗ Failed to send restart notification to advisor {advisor_id}: {e}")
                failure_details[str(advisor_id)] = str(e)
        
        if success_ids:
            logger.info(f"✓ Restart notification sent to {len(success_ids)} individual advisor(s): {', '.join(success_ids)}")
            notification_delivered = True 
        if failure_details:
            logger.warning(f"✗ Failed to send restart notification to some individual advisors: {failure_details}")

    if notification_delivered:
        logger.info("Restart notification process completed.")
    else:
        logger.warning("✗ Restart notification could not be delivered to any configured advisor channel or individual.")

    if WEBHOOK_DOMAIN:
        # Webhook mode
        logger.info("=== Starting Bot in Webhook Mode ===")
        logger.info(f"Webhook URL: https://{WEBHOOK_DOMAIN}/{WEBHOOK_URL_PATH}")
        logger.info(f"Listening on {WEBHOOK_LISTEN_IP}:{WEBHOOK_PORT}")
        
        # Set up webhook
        await setup_webhook()
        
        # Create web application
        logger.debug("Creating web application for webhook...")
        app = web.Application()
        app.router.add_post(f"/{WEBHOOK_URL_PATH}", webhook_handler)
        app.router.add_get("/health", health_check)
        
        # Start web server
        logger.debug("Starting web server...")
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, WEBHOOK_LISTEN_IP, WEBHOOK_PORT)
        await site.start()
        
        logger.info("✅ Webhook server started successfully")
        logger.info("Bot is running in webhook mode.")
        
        # Keep the server running
        try:
            while True:
                await asyncio.sleep(3600)  # Sleep for 1 hour, then check again
                logger.debug("Webhook server heartbeat - still running")
        except KeyboardInterrupt:
            logger.info("Received shutdown signal...")
        finally:
            logger.info("Cleaning up webhook server...")
            await runner.cleanup()
            await application.stop()
    else:
        # Polling mode
        logger.info("=== Starting Bot in Polling Mode ===")
        logger.info("Bot is running in polling mode.")
        await application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    asyncio.run(main())