from loguru import logger
import os
import sys
import asyncio
import json
import time
from datetime import datetime
from aiohttp import web
from telegram import Update, ReactionTypeEmoji
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
    MessageReactionHandler,
)
from telegram.constants import ChatAction
from openai import OpenAI
from openai.types.chat import (
    ChatCompletionUserMessageParam,
    ChatCompletionSystemMessageParam,
)
from dotenv import load_dotenv
from typing import List, Union, Dict, Any


def setup_logging() -> None:
    """Set up loguru with rotation and JSON serialization."""
    # Remove default handler
    logger.remove()

    # Add console handler with colorized output
    logger.add(
        sys.stdout,
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
        colorize=True,
    )

    # Add file handler with rotation
    logger.add(
        "logs/bot_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="7 days",
        level="DEBUG",
        compression="zip",
        serialize=False,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
    )

    # Add JSON handler for structured logging
    logger.add(
        "logs/bot_structured_{time:YYYY-MM-DD}.json",
        rotation="1 day",
        retention="7 days",
        level="INFO",
        serialize=True,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
    )


# Initialize logging
setup_logging()

load_dotenv()
logger.info("=== Bot Starting Up ===", extra={"phase": "startup"})
logger.debug("Loading environment variables...")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODERATOR_CHAT_ID = os.getenv("MODERATOR_CHAT_ID")
ADVISOR_USER_IDS_STR = os.getenv("ADVISOR_USER_IDS", "")
ADVISOR_USER_IDS = set()

# Log environment variable status
logger.debug(
    "Environment variables status",
    extra={
        "TELEGRAM_TOKEN": "✓ Set" if TELEGRAM_TOKEN else "✗ Missing",
        "OPENAI_API_KEY": "✓ Set" if OPENAI_API_KEY else "✗ Missing",
        "MODERATOR_CHAT_ID": "✓ Set" if MODERATOR_CHAT_ID else "✗ Missing",
        "ADVISOR_USER_IDS_STR": ADVISOR_USER_IDS_STR,
    },
)

if ADVISOR_USER_IDS_STR:
    try:
        ADVISOR_USER_IDS = set(map(int, ADVISOR_USER_IDS_STR.split(",")))
        logger.info(
            "Loaded advisor user IDs",
            extra={"count": len(ADVISOR_USER_IDS), "ids": list(ADVISOR_USER_IDS)},
        )
    except ValueError as e:
        logger.error(
            f"Invalid format for ADVISOR_USER_IDS: {e}", extra={"error": str(e)}
        )
        ADVISOR_USER_IDS = set()

# Webhook settings
WEBHOOK_LISTEN_IP = os.getenv("WEBHOOK_LISTEN_IP", "0.0.0.0")
WEBHOOK_PORT = int(os.getenv("PORT", os.getenv("WEBHOOK_PORT", "8443")))
WEBHOOK_URL_PATH = os.getenv("WEBHOOK_URL_PATH", TELEGRAM_TOKEN or "")
WEBHOOK_DOMAIN = os.getenv("WEBHOOK_DOMAIN")

logger.debug(
    "Webhook configuration",
    extra={"ip": WEBHOOK_LISTEN_IP, "port": WEBHOOK_PORT, "domain": WEBHOOK_DOMAIN},
)

# Initialize OpenAI client
try:
    client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
    logger.info("OpenAI client status", extra={"initialized": bool(client)})
except Exception as e:
    logger.exception("Failed to initialize OpenAI client", extra={"error": str(e)})
    client = None

# Load FAQ content
FAQ_CONTENT = ""
try:
    logger.debug("Loading FAQ content...")
    with open("faq.md", "r", encoding="utf-8") as f:
        FAQ_CONTENT = f.read()
    logger.info("FAQ content loaded", extra={"length": len(FAQ_CONTENT)})
except FileNotFoundError:
    logger.error("FAQ file not found")
except Exception as e:
    logger.exception("Error reading FAQ file", extra={"error": str(e)})

# Special markers
NOT_A_QUESTION_MARKER = "[NOT_A_QUESTION]"
CANNOT_ANSWER_MARKER = "[CANNOT_ANSWER]"

logger.debug(
    "Special markers configured",
    extra={
        "not_a_question": NOT_A_QUESTION_MARKER,
        "cannot_answer": CANNOT_ANSWER_MARKER,
    },
)

# State variables
BOT_IS_ACTIVE = True
application = None


def log_user_info(
    update: Update, action: str, additional_info: Dict[str, Any] = {}
) -> Dict[str, Any]:
    """Log user information with structured data."""
    user = update.effective_user
    chat = update.effective_chat

    user_info = {
        "user_id": user.id if user else "unknown",
        "username": user.username if user else "unknown",
        "first_name": user.first_name if user else "unknown",
        "last_name": user.last_name if user else "unknown",
        "chat_id": chat.id if chat else "unknown",
        "chat_type": chat.type if chat else "unknown",
        "chat_title": getattr(chat, "title", "private") if chat else "unknown",
        "action": action,
        "timestamp": datetime.now().isoformat(),
    }
    user_info.update(additional_info)

    logger.info("USER_ACTION", extra=user_info)
    return user_info


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command for advisors only."""
    logger.debug("Processing /start command...")

    if not update.message or not update.effective_user:
        logger.warning(
            "Invalid /start command", extra={"error": "Missing message or user"}
        )
        return

    user_id = update.effective_user.id

    if user_id not in ADVISOR_USER_IDS:
        logger.warning("Non-advisor attempted /start", extra={"user_id": user_id})
        log_user_info(update, "start_command_denied", {"reason": "Not in advisor list"})
        await update.message.reply_text(
            "Sorry, this command is only available to advisors."
        )
        return

    global BOT_IS_ACTIVE
    old_status = BOT_IS_ACTIVE
    BOT_IS_ACTIVE = True

    logger.info(
        "/start command executed",
        extra={
            "user_id": user_id,
            "old_status": old_status,
            "new_status": BOT_IS_ACTIVE,
        },
    )
    log_user_info(update, "start_command_success", {"previous_status": old_status})

    await update.message.reply_text(
        "✅ Bot is now active and will respond to student questions."
    )


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /stop command for advisors only."""
    logger.debug("Processing /stop command...")

    if not update.message or not update.effective_user:
        logger.warning(
            "Invalid /stop command", extra={"error": "Missing message or user"}
        )
        return

    user_id = update.effective_user.id

    if user_id not in ADVISOR_USER_IDS:
        logger.warning("Non-advisor attempted /stop", extra={"user_id": user_id})
        log_user_info(update, "stop_command_denied", {"reason": "Not in advisor list"})
        await update.message.reply_text(
            "Sorry, this command is only available to advisors."
        )
        return

    global BOT_IS_ACTIVE
    old_status = BOT_IS_ACTIVE
    BOT_IS_ACTIVE = False

    logger.info(
        "/stop command executed",
        extra={
            "user_id": user_id,
            "old_status": old_status,
            "new_status": BOT_IS_ACTIVE,
        },
    )
    log_user_info(update, "stop_command_success", {"previous_status": old_status})

    await update.message.reply_text(
        "⏹️ Bot is now inactive and will not respond to student questions."
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the current bot status for advisors."""
    logger.debug("Processing /status command...")

    if not update.message or not update.effective_user:
        logger.warning(
            "Invalid /status command", extra={"error": "Missing message or user"}
        )
        return

    user_id = update.effective_user.id

    if user_id not in ADVISOR_USER_IDS:
        logger.warning("Non-advisor attempted /status", extra={"user_id": user_id})
        log_user_info(
            update, "status_command_denied", {"reason": "Not in advisor list"}
        )
        await update.message.reply_text(
            "Sorry, this command is only available to advisors."
        )
        return

    status_info = {
        "bot_active": BOT_IS_ACTIVE,
        "faq_loaded": bool(FAQ_CONTENT),
        "openai_connected": bool(client),
        "advisors_count": len(ADVISOR_USER_IDS),
    }

    logger.info("Status command executed", extra={"user_id": user_id, **status_info})
    log_user_info(update, "status_command_success", status_info)

    status_message = f"""
📊 **Bot Status**
Status: {"🟢 Active" if BOT_IS_ACTIVE else "🔴 Inactive"}
FAQ: {"✅ Loaded" if FAQ_CONTENT else "❌ Not loaded"}
OpenAI: {"✅ Connected" if client else "❌ Not connected"}
Advisors: {len(ADVISOR_USER_IDS)} configured
    """

    await update.message.reply_text(status_message, parse_mode="Markdown")


def sanitize_markdown(text: str) -> str:
    """Sanitize markdown text to prevent Telegram parsing errors."""
    if not text:
        return text

    logger.debug(
        "Sanitizing markdown text",
        extra={"text_preview": text[:200] + ("..." if len(text) > 200 else "")},
    )

    # Fix unmatched markdown characters
    for char in ["*", "_", "`"]:
        count = text.count(char)
        if count % 2 != 0:
            last_pos = text.rfind(char)
            if last_pos >= 0:
                text = text[:last_pos] + "\\" + char + text[last_pos + 1 :]
                logger.debug(f"Fixed unmatched {char}")

    # Fix unmatched square brackets
    if text.count("[") != text.count("]"):
        text = text.replace("[", "\\[").replace("]", "\\]")
        logger.debug("Fixed unmatched square brackets")

    # Escape other problematic characters
    for char in [">", "<", "&"]:
        text = text.replace(char, f"\\{char}")

    logger.debug(
        "Sanitized text",
        extra={"text_preview": text[:200] + ("..." if len(text) > 200 else "")},
    )
    return text


def get_llm_response(user_message: str, user_id: int = 0, chat_id: int = 0) -> str:
    """Get response from OpenAI using FAQ content."""
    start_time = time.time()
    logger.debug(
        "Processing LLM request",
        extra={
            "user_id": user_id,
            "message_preview": user_message[:100]
            + ("..." if len(user_message) > 100 else ""),
        },
    )

    if not client:
        logger.error("OpenAI client not initialized")
        return CANNOT_ANSWER_MARKER

    if not FAQ_CONTENT:
        logger.warning("FAQ content not available")
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
        logger.debug("Sending request to OpenAI API", extra={"user_id": user_id})

        messages: List[
            Union[ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam]
        ] = [
            ChatCompletionSystemMessageParam(role="system", content=system_prompt),
            ChatCompletionUserMessageParam(role="user", content=user_message),
        ]

        completion = client.chat.completions.create(
            model="gpt-4o-mini", messages=messages, temperature=0.2, max_tokens=1000
        )

        response_text = completion.choices[0].message.content or CANNOT_ANSWER_MARKER
        response_text = response_text.strip()
        processing_time = time.time() - start_time

        response_type = (
            "not_question"
            if response_text == NOT_A_QUESTION_MARKER
            else "cannot_answer"
            if response_text == CANNOT_ANSWER_MARKER
            else "answered"
        )

        logger.info(
            "LLM response",
            extra={
                "response_type": response_type,
                "processing_time": round(processing_time, 2),
                "response_preview": response_text[:200]
                + ("..." if len(response_text) > 200 else ""),
            },
        )

        if hasattr(completion, "usage") and completion.usage:
            logger.debug(
                "Token usage",
                extra={
                    "prompt_tokens": completion.usage.prompt_tokens,
                    "completion_tokens": completion.usage.completion_tokens,
                },
            )

        return response_text

    except Exception as e:
        logger.exception("Error calling OpenAI", extra={"error": str(e)})
        return CANNOT_ANSWER_MARKER


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming text messages with enhanced typing status."""
    if (
        not update.message
        or not update.message.text
        or not update.effective_user
        or not update.effective_chat
    ):
        logger.debug("Message ignored", extra={"reason": "Missing required attributes"})
        return

    message_text = update.message.text.strip()
    user = update.effective_user
    chat = update.effective_chat
    chat_id = chat.id

    logger.debug(
        "Processing message",
        extra={
            "user_id": user.id,
            "chat_id": chat_id,
            "message_preview": message_text[:100]
            + ("..." if len(message_text) > 100 else ""),
        },
    )

    # Skip advisors
    if user.id in ADVISOR_USER_IDS:
        logger.info("Message from advisor ignored", extra={"user_id": user.id})
        log_user_info(update, "message_ignored", {"reason": "User is advisor"})
        return

    # Check bot status
    if not BOT_IS_ACTIVE:
        logger.info("Bot inactive", extra={"reason": "Ignoring message"})
        log_user_info(update, "message_ignored", {"reason": "Bot inactive"})
        return

    # Skip commands and empty messages
    if message_text.startswith("/") or not message_text:
        logger.debug("Ignoring message", extra={"reason": "Command or empty message"})
        return

    # Send typing status
    try:
        logger.debug("Sending typing status", extra={"chat_id": chat_id})
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        logger.info("Typing status sent", extra={"chat_id": chat_id})
    except Exception as e:
        logger.exception("Failed to send typing status", extra={"error": str(e)})

    log_user_info(
        update,
        "message_processing",
        {"message": message_text[:200] + ("..." if len(message_text) > 200 else "")},
    )

    try:
        llm_answer = get_llm_response(message_text, user_id=user.id, chat_id=chat_id)
        if llm_answer == NOT_A_QUESTION_MARKER:
            logger.info("Message not a question", extra={"user_id": user.id})
            return

        elif llm_answer == CANNOT_ANSWER_MARKER or not llm_answer:
            logger.info("Cannot answer question", extra={"user_id": user.id})
            log_user_info(update, "message_cannot_answer")

            # Notify moderator
            if MODERATOR_CHAT_ID:
                try:
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
                        parse_mode="Markdown",
                    )
                    logger.info(
                        "Moderator notification sent",
                        extra={"chat_id": MODERATOR_CHAT_ID},
                    )

                except Exception as e:
                    logger.exception(
                        "Failed to notify moderator", extra={"error": str(e)}
                    )

        else:
            logger.info(
                "Question answered",
                extra={"user_id": user.id, "response_length": len(llm_answer)},
            )
            log_user_info(
                update, "message_answered", {"response_length": len(llm_answer)}
            )

            # Send response with markdown sanitization
            try:
                await update.message.reply_text(llm_answer, parse_mode="Markdown")
                logger.debug("Response sent with Markdown", extra={"chat_id": chat_id})
            except Exception as markdown_error:
                logger.warning("Markdown error", extra={"error": str(markdown_error)})
                try:
                    sanitized = sanitize_markdown(llm_answer)
                    await update.message.reply_text(sanitized, parse_mode="Markdown")
                    logger.info(
                        "Response sent with sanitized Markdown",
                        extra={"chat_id": chat_id},
                    )
                except Exception as e:
                    logger.exception(
                        "Failed to send sanitized response", extra={"error": str(e)}
                    )
                    if MODERATOR_CHAT_ID:
                        try:
                            moderator_message = (
                                f"Failed to send answer to user {user.id} "
                                f"(username: {user.username}, name: {user.first_name} {user.last_name or ''}). "
                                f"Please review and forward if appropriate.\n\n"
                                f"Original query: {message_text}\n\nLLM Answer:\n{llm_answer}"
                            )
                            await context.bot.send_message(
                                chat_id=MODERATOR_CHAT_ID, text=moderator_message
                            )
                            logger.info(
                                "Sent to moderator",
                                extra={"chat_id": MODERATOR_CHAT_ID},
                            )
                        except Exception as final_error:
                            logger.exception(
                                "Failed to notify moderator",
                                extra={"error": str(final_error)},
                            )

    except Exception as e:
        logger.exception("Error handling message", extra={"error": str(e)})
        log_user_info(update, "message_error", {"error": str(e)})


async def handle_reaction_downvote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles downvote reactions to delete messages."""
    logger.debug("Reaction handler triggered", extra={"update_type": str(type(update))})

    if not update.message_reaction or not update.message_reaction.user:
        logger.debug("No message reaction or user found")
        return

    reaction = update.message_reaction
    chat = reaction.chat
    message_id = reaction.message_id
    user = reaction.user
    assert user is not None
    user_id = user.id

    logger.info(
        "Reaction received",
        extra={"user_id": user_id, "chat_id": chat.id, "message_id": message_id},
    )

    # Only advisors can trigger deletion
    if user_id not in ADVISOR_USER_IDS:
        logger.debug("Non-advisor reaction ignored", extra={"user_id": user_id})
        log_user_info(update, "reaction_ignored", {"reason": "Non-advisor user"})
        return

    # Check for new thumbs down reaction
    downvote_emoji = "👎"
    is_new_downvote = any(
        isinstance(rtype, ReactionTypeEmoji) and rtype.emoji == downvote_emoji
        for rtype in reaction.new_reaction
    )

    if not is_new_downvote:
        logger.debug("Not a new thumbs down reaction")
        return

    # Skip deletion in moderator chat
    if MODERATOR_CHAT_ID and str(chat.id) == MODERATOR_CHAT_ID:
        logger.info("Skipping deletion in moderator chat", extra={"chat_id": chat.id})
        log_user_info(update, "downvote_skipped", {"reason": "Moderator chat"})
        return

    # Delete message
    try:
        await context.bot.delete_message(chat_id=chat.id, message_id=message_id)
        logger.info(
            "Message deleted",
            extra={"chat_id": chat.id, "message_id": message_id, "advisor_id": user_id},
        )
        log_user_info(
            update, "message_deleted", {"message_id": message_id, "advisor_id": user_id}
        )
    except Exception as e:
        logger.exception("Failed to delete message", extra={"error": str(e)})
        log_user_info(update, "delete_failed", {"error": str(e)})


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enhanced error logging."""
    error_info = {
        "error": str(context.error),
        "error_type": type(context.error).__name__,
        "update": str(update) if update else "None",
        "timestamp": datetime.now().isoformat(),
    }

    logger.exception("Exception occurred", extra=error_info)
    if isinstance(update, Update) and update.effective_user:
        logger.error("Error for user", extra={"user_id": update.effective_user.id})


async def webhook_handler(request):
    """Handle incoming webhook requests."""
    request_start_time = time.time()
    client_ip = request.remote

    logger.debug("Webhook request received", extra={"client_ip": client_ip})

    if not application:
        logger.error("Application not initialized")
        return web.Response(status=500)

    try:
        data = await request.json()
        logger.debug(
            "Webhook data",
            extra={
                "data_preview": json.dumps(data, ensure_ascii=False)[:500]
                + ("..." if len(str(data)) > 500 else "")
            },
        )

        update = Update.de_json(data, application.bot)
        if update:
            await application.process_update(update)
            processing_time = time.time() - request_start_time
            logger.info(
                "Webhook processed",
                extra={"processing_time": round(processing_time, 2)},
            )
        else:
            logger.warning("Failed to create Update object")

        return web.Response(status=200)

    except Exception as e:
        logger.exception("Webhook error", extra={"error": str(e)})
        return web.Response(status=500)


async def health_check(request):
    """Health check endpoint."""
    logger.debug("Health check request")
    health_status = {
        "status": "healthy",
        "bot_active": BOT_IS_ACTIVE,
        "faq_loaded": bool(FAQ_CONTENT),
        "openai_connected": bool(client),
        "timestamp": datetime.now().isoformat(),
    }
    logger.debug("Health status", extra=health_status)
    return web.Response(text="OK", status=200)


async def main():
    """Main function to start the bot."""
    logger.info("=== Bot Initialization ===", extra={"phase": "init"})

    # Validate configuration
    if not TELEGRAM_TOKEN:
        logger.critical("Missing TELEGRAM_BOT_TOKEN", extra={"error": "Cannot start"})
        return
    if not OPENAI_API_KEY:
        logger.warning(
            "Missing OPENAI_API_KEY", extra={"warning": "Limited functionality"}
        )

    logger.info("Creating Telegram application...")
    global application
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()  # type: ignore
    logger.info("Application created")

    logger.debug("Registering handlers")
    application.add_handler(MessageReactionHandler(handle_reaction_downvote))
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    application.add_error_handler(error_handler)
    logger.info("All handlers registered")

    logger.debug("Initializing application...")
    await application.initialize()
    await application.start()
    logger.info("Application started")

    # Send restart notification
    if ADVISOR_USER_IDS:
        restart_msg = "✅ Bot restarted and active" + (
            " (Webhook)" if WEBHOOK_DOMAIN else " (Polling)"
        )
        success_count = 0

        for advisor_id in ADVISOR_USER_IDS:
            try:
                await application.bot.send_message(chat_id=advisor_id, text=restart_msg)
                success_count += 1
                logger.debug(
                    "Restart notification sent", extra={"advisor_id": advisor_id}
                )
            except Exception as e:
                logger.exception(
                    "Failed to notify advisor",
                    extra={"advisor_id": advisor_id, "error": str(e)},
                )

        logger.info(
            "Restart notifications",
            extra={"successful": success_count, "total": len(ADVISOR_USER_IDS)},
        )

    # Start in webhook or polling mode
    if WEBHOOK_DOMAIN and WEBHOOK_URL_PATH:
        logger.info("Starting in Webhook Mode", extra={"phase": "webhook"})
        webhook_url = (
            f"https://{WEBHOOK_DOMAIN.rstrip('/')}/{WEBHOOK_URL_PATH.lstrip('/')}"
        )
        logger.info("Webhook URL set", extra={"url": webhook_url})

        try:
            await application.bot.set_webhook(
                webhook_url, allowed_updates=["message", "message_reaction"]
            )
            logger.info("Webhook set", extra={"url": webhook_url})
        except Exception as e:
            logger.exception("Webhook setup failed", extra={"error": str(e)})
            return

        app = web.Application()
        app.router.add_post(f"/{WEBHOOK_URL_PATH}", webhook_handler)
        app.router.add_get("/health", health_check)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, WEBHOOK_LISTEN_IP, WEBHOOK_PORT)
        await site.start()
        logger.info(
            "Web server started", extra={"ip": WEBHOOK_LISTEN_IP, "port": WEBHOOK_PORT}
        )

        while True:
            await asyncio.sleep(3600)
    else:
        logger.info("Starting in Polling Mode", extra={"phase": "polling"})
        application.run_polling(allowed_updates=["message", "message_reaction"])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown signal received", extra={"phase": "shutdown"})
    except Exception as e:
        logger.exception("Fatal error", extra={"error": str(e)})
    finally:
        logger.info("=== Bot Shutdown Complete ===", extra={"phase": "shutdown"})
