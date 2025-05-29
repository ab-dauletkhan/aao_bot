from telegram.ext import ContextTypes
from telegram import Update
from telegram.constants import ChatAction
from bot.config import (
    MODERATOR_CHAT_ID,
    ADVISOR_USER_IDS,
    NOT_A_QUESTION_MARKER,
    CANNOT_ANSWER_MARKER,
    GROUP_CHAT_IDS,
)
from bot.openai_client import get_llm_response
from bot.utils import log_user_info, sanitize_markdown, log_with_context, get_user_context
from loguru import logger
from typing import Optional


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming text messages with enhanced typing status and logging."""
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

    _log_message_processing(update, message_text)

    if _should_ignore_message(update, context, message_text, chat_id):
        return

    await _send_typing_indicator(context.bot, chat_id, update)

    log_user_info(
        update,
        "message_processing",
        {"message": message_text[:200] + ("..." if len(message_text) > 200 else "")},
    )

    try:
        await _process_llm_response(update, context, message_text, user, chat)
    except Exception as e:
        log_with_context(
            update,
            "error",
            "Error handling message",
            {"error": str(e), "error_type": type(e).__name__},
        )
        # Ensure moderator is notified about processing errors
        await _handle_processing_error(update, context, message_text, e)


def _is_valid_message(update: Update) -> bool:
    """Check if the message has all required attributes."""
    if (
        not update.message
        or not update.message.text
        or not update.effective_user
        or not update.effective_chat
    ):
        if update.effective_user and update.effective_chat:
            log_with_context(
                update, "debug", "Message ignored - missing required attributes"
            )
        else:
            logger.debug(
                "Message ignored", extra={"reason": "Missing required attributes"}
            )
        return False
    return True


def _log_message_processing(update: Update, message_text: str):
    """Log message processing details with enhanced context."""
    log_with_context(
        update,
        "debug",
        "Processing message",
        {
            "message_length": len(message_text),
            "message_preview": message_text[:100]
            + ("..." if len(message_text) > 100 else ""),
        },
    )


def _should_ignore_message(
    update: Update, context, message_text: str, chat_id: int
) -> bool:
    """Determine if message should be ignored."""
    user = update.effective_user

    if GROUP_CHAT_IDS and chat_id not in GROUP_CHAT_IDS:
        log_with_context(
            update,
            "info",
            "Message from unauthorized group chat ignored",
            {"authorized_groups": len(GROUP_CHAT_IDS)},
        )
        return True

    if user and user.id in ADVISOR_USER_IDS:
        log_with_context(update, "info", "Message from advisor ignored")
        return True

    if not context.bot_data.get("BOT_IS_ACTIVE", True):
        log_with_context(update, "info", "Bot inactive - message ignored")
        return True

    if message_text.startswith("/") or not message_text:
        log_with_context(
            update,
            "debug",
            "Command or empty message ignored",
            {"is_command": message_text.startswith("/")},
        )
        return True

    return False


async def _send_typing_indicator(bot, chat_id: int, update: Update):
    """Send typing indicator to chat with enhanced logging."""
    try:
        log_with_context(update, "debug", "Sending typing indicator")
        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        log_with_context(update, "debug", "Typing indicator sent successfully")
    except Exception as e:
        log_with_context(
            update, "warning", "Failed to send typing indicator", {"error": str(e)}
        )


async def _process_llm_response(update: Update, context, message_text: str, user, chat):
    """Process the LLM response and handle different response types with enhanced error handling."""
    try:
        log_with_context(update, "debug", "Requesting LLM response")
        llm_answer = get_llm_response(message_text, user_id=user.id, chat_id=chat.id)

        # Enhanced response validation
        if not llm_answer or llm_answer.strip() == "":
            log_with_context(update, "warning", "LLM returned empty response")
            llm_answer = CANNOT_ANSWER_MARKER

        if llm_answer == NOT_A_QUESTION_MARKER:
            log_with_context(update, "info", "Message identified as not a question")
            return

        if llm_answer == CANNOT_ANSWER_MARKER:
            log_with_context(update, "info", "LLM cannot answer question")
            await _handle_unanswerable_question(
                update, context, message_text, user, chat
            )
            return

        await _handle_successful_answer(
            update, context, llm_answer, user, chat, message_text
        )

    except Exception as e:
        log_with_context(
            update,
            "error",
            "Error in LLM processing",
            {"error": str(e), "error_type": type(e).__name__},
        )
        # Treat LLM processing errors as unanswerable questions
        await _handle_unanswerable_question(
            update, context, message_text, user, chat, processing_error=str(e)
        )


async def _handle_unanswerable_question(
    update: Update,
    context,
    message_text: str,
    user,
    chat,
    processing_error: Optional[str] = None,
):
    """Handle questions that cannot be answered with enhanced error context."""
    error_context = {"processing_error": processing_error} if processing_error else {}
    log_with_context(update, "info", "Cannot answer question", error_context)
    log_user_info(update, "message_cannot_answer", error_context)

    if MODERATOR_CHAT_ID:
        await _notify_moderator_about_question(
            context.bot, update, message_text, user, chat, processing_error
        )


async def _notify_moderator_about_question(
    bot,
    update: Update,
    message_text: str,
    user,
    chat,
    processing_error: Optional[str] = None,
):
    """Notify moderator about unanswerable question with enhanced context."""
    try:
        user_context = get_user_context(update)
        chat_title = chat.title if chat.title else f"Chat {chat.id}"

        if not update.message:
            return

        message_link = _build_message_link(chat.id, update.message.message_id)

        error_info = f"\n**Error:** {processing_error}" if processing_error else ""

        moderator_message = (
            f"❓ **Student Question Alert**\n"
            f"**Chat:** {chat_title} (ID: {chat.id})\n"
            f"**User:** {user.first_name} {user.last_name or ''} (@{user.username or 'no_username'}) (ID: {user.id})\n"
            f"**Question:** {message_text[:500]}{'...' if len(message_text) > 500 else ''}\n"
            f"**Link:** {message_link}{error_info}"
        )

        await bot.send_message(
            chat_id=MODERATOR_CHAT_ID,
            text=moderator_message,
            parse_mode="Markdown",
        )

        log_with_context(
            update,
            "info",
            "Moderator notification sent",
            {
                "moderator_chat_id": MODERATOR_CHAT_ID,
                "notification_type": "unanswerable_question",
                "has_processing_error": bool(processing_error),
                "user_context": user_context,
            },
        )

    except Exception as e:
        log_with_context(
            update,
            "error",
            "Failed to notify moderator",
            {
                "error": str(e),
                "error_type": type(e).__name__,
                "moderator_chat_id": MODERATOR_CHAT_ID,
            },
        )


async def _handle_successful_answer(
    update: Update, context, llm_answer: str, user, chat, message_text: str
):
    """Handle successful LLM answers with enhanced delivery guarantee."""
    log_with_context(
        update,
        "info",
        "Question answered successfully",
        {
            "response_length": len(llm_answer),
            "response_preview": llm_answer[:100]
            + ("..." if len(llm_answer) > 100 else ""),
        },
    )

    log_user_info(update, "message_answered", {"response_length": len(llm_answer)})

    # Multiple delivery attempts with different strategies
    delivery_success = False
    delivery_attempts = []

    # Attempt 1: Original markdown
    success, error = await _try_send_response_with_error(update, llm_answer, "markdown")
    delivery_attempts.append({"method": "markdown", "success": success, "error": error})
    if success:
        delivery_success = True

    # Attempt 2: Sanitized markdown
    if not delivery_success:
        sanitized = sanitize_markdown(llm_answer)
        success, error = await _try_send_response_with_error(
            update, sanitized, "sanitized_markdown"
        )
        delivery_attempts.append(
            {"method": "sanitized_markdown", "success": success, "error": error}
        )
        if success:
            delivery_success = True

    # Attempt 3: Plain text (no markdown)
    if not delivery_success:
        success, error = await _try_send_response_with_error(
            update, llm_answer, "plain_text"
        )
        delivery_attempts.append(
            {"method": "plain_text", "success": success, "error": error}
        )
        if success:
            delivery_success = True

    # Log delivery attempts
    log_with_context(
        update,
        "info" if delivery_success else "warning",
        "Response delivery completed",
        {
            "delivery_success": delivery_success,
            "attempts": delivery_attempts,
            "total_attempts": len(delivery_attempts),
        },
    )

    # If all delivery attempts failed, notify moderator
    if not delivery_success:
        await _handle_failed_response(
            context.bot, llm_answer, user, message_text, update, delivery_attempts
        )


async def _try_send_response_with_error(
    update: Update, response_text: str, method: str
) -> tuple[bool, str]:
    """Try to send response and return success status with error details."""
    if not update.message or not update.effective_chat:
        return False, "Missing message or chat"

    try:
        if method == "plain_text":
            await update.message.reply_text(response_text)
        else:
            await update.message.reply_text(response_text, parse_mode="Markdown")

        log_with_context(
            update, "debug", "Response sent successfully", {"method": method}
        )
        return True, ""

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        log_with_context(
            update,
            "debug",
            "Response send failed",
            {"method": method, "error": error_msg},
        )
        return False, error_msg


async def _handle_failed_response(
    bot,
    llm_answer: str,
    user,
    message_text: str,
    update: Update,
    delivery_attempts: list,
):
    """Handle cases where response couldn't be sent to user with comprehensive error reporting."""
    if not MODERATOR_CHAT_ID:
        log_with_context(
            update, "error", "Response delivery failed and no moderator configured"
        )
        return

    try:
        user_context = get_user_context(update)

        # Format delivery attempts for moderator
        attempts_summary = "\n".join(
            [
                f"- {attempt['method']}: {'✅' if attempt['success'] else '❌'} {attempt.get('error', '')}"
                for attempt in delivery_attempts
            ]
        )

        moderator_message = (
            f"🚨 **Failed to deliver answer**\n"
            f"**User:** {user.first_name} {user.last_name or ''} (@{user.username or 'no_username'}) (ID: {user.id})\n"
            f"**Chat:** {user_context.get('chat_title', 'Unknown')} (ID: {user_context.get('chat_id', 'Unknown')})\n"
            f"**Query:** {message_text[:300]}{'...' if len(message_text) > 300 else ''}\n\n"
            f"**Delivery Attempts:**\n{attempts_summary}\n\n"
            f"**LLM Answer:**\n{llm_answer[:1000]}{'...' if len(llm_answer) > 1000 else ''}"
        )

        await bot.send_message(chat_id=MODERATOR_CHAT_ID, text=moderator_message)

        log_with_context(
            update,
            "info",
            "Failed delivery reported to moderator",
            {
                "moderator_chat_id": MODERATOR_CHAT_ID,
                "delivery_attempts_count": len(delivery_attempts),
            },
        )

    except Exception as final_error:
        log_with_context(
            update,
            "error",
            "Failed to notify moderator about delivery failure",
            {
                "error": str(final_error),
                "error_type": type(final_error).__name__,
                "moderator_chat_id": MODERATOR_CHAT_ID,
            },
        )


async def _handle_processing_error(
    update: Update, context, message_text: str, error: Exception
):
    """Handle processing errors by treating them as unanswerable questions."""
    user = update.effective_user
    chat = update.effective_chat

    if user and chat:
        await _handle_unanswerable_question(
            update,
            context,
            message_text,
            user,
            chat,
            processing_error=f"{type(error).__name__}: {str(error)}",
        )


def _build_message_link(chat_id: int, message_id: int) -> str:
    """Build Telegram message link."""
    chat_id_str = str(chat_id)
    if chat_id_str.startswith("-100"):
        return f"https://t.me/c/{chat_id_str[4:]}/{message_id}"
    return f"https://t.me/c/{chat_id}/{message_id}"
