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

    if user.id in ADVISOR_USER_IDS:
        logger.info("Message from advisor ignored", extra={"user_id": user.id})
        log_user_info(update, "message_ignored", {"reason": "User is advisor"})
        return

    if not context.bot_data.get("BOT_IS_ACTIVE", True):
        logger.info("Bot inactive", extra={"reason": "Ignoring message"})
        log_user_info(update, "message_ignored", {"reason": "Bot inactive"})
        return

    if message_text.startswith("/") or not message_text:
        logger.debug("Ignoring message", extra={"reason": "Command or empty message"})
        return

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
