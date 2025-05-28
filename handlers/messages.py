from telegram.ext import ContextTypes
from telegram import Update
from telegram.constants import ChatAction
from config import (
    MODERATOR_CHAT_ID,
    ADVISOR_USER_IDS,
    NOT_A_QUESTION_MARKER,
    CANNOT_ANSWER_MARKER,
)
from openai_client import get_llm_response
from utils import log_user_info, sanitize_markdown
from loguru import logger

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming text messages with enhanced typing status."""
    if not _is_valid_message(update):
        return

    if not update.message or not update.message.text:
        return

    message_text = update.message.text.strip()
    user = update.effective_user
    chat = update.effective_chat

    if not chat:
        return

    chat_id = chat.id

    _log_message_processing(user, chat_id, message_text)

    if _should_ignore_message(user, context, message_text):
        return

    await _send_typing_indicator(context.bot, chat_id)

    log_user_info(
        update,
        "message_processing",
        {"message": message_text[:200] + ("..." if len(message_text) > 200 else "")},
    )

    try:
        await _process_llm_response(update, context, message_text, user, chat)
    except Exception as e:
        logger.exception("Error handling message", extra={"error": str(e)})
        log_user_info(update, "message_error", {"error": str(e)})


def _is_valid_message(update: Update) -> bool:
    """Check if the message has all required attributes."""
    if (
        not update.message
        or not update.message.text
        or not update.effective_user
        or not update.effective_chat
    ):
        logger.debug("Message ignored", extra={"reason": "Missing required attributes"})
        return False
    return True


def _log_message_processing(user, chat_id: int, message_text: str):
    """Log message processing details."""
    logger.debug(
        "Processing message",
        extra={
            "user_id": user.id,
            "chat_id": chat_id,
            "message_preview": message_text[:100]
            + ("..." if len(message_text) > 100 else ""),
        },
    )


def _should_ignore_message(user, context, message_text: str) -> bool:
    """Determine if message should be ignored."""
    if user.id in ADVISOR_USER_IDS:
        logger.info("Message from advisor ignored", extra={"user_id": user.id})
        return True

    if not context.bot_data.get("BOT_IS_ACTIVE", True):
        logger.info("Bot inactive", extra={"reason": "Ignoring message"})
        return True

    if message_text.startswith("/") or not message_text:
        logger.debug("Ignoring message", extra={"reason": "Command or empty message"})
        return True

    return False


async def _send_typing_indicator(bot, chat_id: int):
    """Send typing indicator to chat."""
    try:
        logger.debug("Sending typing status", extra={"chat_id": chat_id})
        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        logger.info("Typing status sent", extra={"chat_id": chat_id})
    except Exception as e:
        logger.exception("Failed to send typing status", extra={"error": str(e)})


async def _process_llm_response(update: Update, context, message_text: str, user, chat):
    """Process the LLM response and handle different response types."""
    llm_answer = get_llm_response(message_text, user_id=user.id, chat_id=chat.id)

    if llm_answer == NOT_A_QUESTION_MARKER:
        logger.info("Message not a question", extra={"user_id": user.id})
        return

    if llm_answer == CANNOT_ANSWER_MARKER or not llm_answer:
        await _handle_unanswerable_question(update, context, message_text, user, chat)
        return

    await _handle_successful_answer(update, context, llm_answer, user, chat, message_text)


async def _handle_unanswerable_question(update: Update, context, message_text: str, user, chat):
    """Handle questions that cannot be answered."""
    logger.info("Cannot answer question", extra={"user_id": user.id})
    log_user_info(update, "message_cannot_answer")

    if MODERATOR_CHAT_ID:
        await _notify_moderator_about_question(context.bot, update, message_text, user, chat)


async def _notify_moderator_about_question(bot, update: Update, message_text: str, user, chat):
    """Notify moderator about unanswerable question."""
    try:
        chat_title = chat.title if chat.title else f"Chat {chat.id}"
        if not update.message:
            return
        message_link = _build_message_link(chat.id, update.message.message_id)

        moderator_message = (
            f"❓ **Student Question Alert**\n"
            f"**Chat:** {chat_title}\n"
            f"**User:** {user.first_name} {user.last_name or ''} (@{user.username or 'no_username'})\n"
            f"**Question:** {message_text}\n"
            f"**Link:** {message_link}"
        )

        await bot.send_message(
            chat_id=MODERATOR_CHAT_ID,
            text=moderator_message,
            parse_mode="Markdown",
        )
        logger.info("Moderator notification sent", extra={"chat_id": MODERATOR_CHAT_ID})
    except Exception as e:
        logger.exception("Failed to notify moderator", extra={"error": str(e)})


async def _handle_successful_answer(update: Update, context, llm_answer: str, user, chat, message_text: str):
    """Handle successful LLM answers."""
    logger.info(
        "Question answered",
        extra={"user_id": user.id, "response_length": len(llm_answer)},
    )
    log_user_info(update, "message_answered", {"response_length": len(llm_answer)})

    success = await _try_send_response(update, llm_answer)
    if not success:
        await _handle_failed_response(context.bot, llm_answer, user, message_text)


async def _try_send_response(update: Update, llm_answer: str) -> bool:
    """Try to send response with markdown, fallback to sanitized markdown."""
    if not update.message:
        return False

    if not update.effective_chat:
        return False

    try:
        await update.message.reply_text(llm_answer, parse_mode="Markdown")
        logger.debug("Response sent with Markdown", extra={"chat_id": update.effective_chat.id})
        return True
    except Exception as markdown_error:
        logger.warning("Markdown error", extra={"error": str(markdown_error)})

        try:
            sanitized = sanitize_markdown(llm_answer)
            await update.message.reply_text(sanitized, parse_mode="Markdown")
            logger.info("Response sent with sanitized Markdown", extra={"chat_id": update.effective_chat.id})
            return True
        except Exception as e:
            logger.exception("Failed to send sanitized response", extra={"error": str(e)})
            return False


async def _handle_failed_response(bot, llm_answer: str, user, message_text: str):
    """Handle cases where response couldn't be sent to user."""
    if not MODERATOR_CHAT_ID:
        return

    try:
        moderator_message = (
            f"Failed to send answer to user {user.id} "
            f"(username: {user.username}, name: {user.first_name} {user.last_name or ''}). "
            f"Please review and forward if appropriate.\n\n"
            f"Original query: {message_text}\n\nLLM Answer:\n{llm_answer}"
        )
        await bot.send_message(chat_id=MODERATOR_CHAT_ID, text=moderator_message)
        logger.info("Sent to moderator", extra={"chat_id": MODERATOR_CHAT_ID})
    except Exception as final_error:
        logger.exception("Failed to notify moderator", extra={"error": str(final_error)})


def _build_message_link(chat_id: int, message_id: int) -> str:
    """Build Telegram message link."""
    chat_id_str = str(chat_id)
    if chat_id_str.startswith('-100'):
        return f"https://t.me/c/{chat_id_str[4:]}/{message_id}"
    return f"https://t.me/c/{chat_id}/{message_id}"
