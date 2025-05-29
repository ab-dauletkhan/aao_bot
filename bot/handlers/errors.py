from telegram.ext import ContextTypes
from telegram import Update
from loguru import logger
from datetime import datetime
from typing import Dict, Any, Optional


def get_user_context(update: Update) -> Dict[str, Any]:
    """Extract user context from update for consistent logging."""
    user = update.effective_user
    chat = update.effective_chat

    return {
        "user_id": user.id if user else None,
        "username": user.username if user else None,
        "first_name": user.first_name if user else None,
        "last_name": user.last_name if user else None,
        "chat_id": chat.id if chat else None,
        "chat_type": chat.type if chat else None,
        "chat_title": getattr(chat, "title", "private") if chat else None,
    }


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enhanced error logging with user context."""
    # Basic error information
    error_info: Dict[str, Any] = {
        "error": str(context.error),
        "error_type": type(context.error).__name__,
        "timestamp": datetime.now().isoformat(),
    }

    # Add user context if available
    if isinstance(update, Update):
        user_context = get_user_context(update)
        error_info.update(user_context)

        # Add update-specific information
        if update.message:
            message_info: Dict[str, Any] = {
                "message_id": update.message.message_id,
                "message_text_preview": (update.message.text[:100] + "...")
                if update.message.text and len(update.message.text) > 100
                else update.message.text,
                "message_date": update.message.date.isoformat()
                if update.message.date
                else None,
            }
            error_info.update(message_info)

        if update.callback_query:
            callback_info: Dict[str, Any] = {
                "callback_query_data": update.callback_query.data,
                "callback_query_id": update.callback_query.id,
            }
            error_info.update(callback_info)

        if update.message_reaction:
            reaction_info: Dict[str, Any] = {
                "reaction_message_id": update.message_reaction.message_id,
                "reaction_user_id": update.message_reaction.user.id
                if update.message_reaction.user
                else None,
            }
            error_info.update(reaction_info)
    else:
        error_info["update"] = str(update) if update else "None"

    # Enhanced error classification
    if context.error:
        error_category = _classify_error(context.error)
        error_info["error_category"] = error_category
    else:
        error_info["error_category"] = "unknown"

    # Log with appropriate level based on error type
    if context.error:
        error_category = error_info.get("error_category", "unknown")
        if error_category in ["network", "timeout", "rate_limit"]:
            logger.warning("Recoverable error occurred", extra=error_info)
        elif error_category in ["permission", "authorization"]:
            logger.warning("Permission error occurred", extra=error_info)
        elif error_category == "user_input":
            logger.info("User input error occurred", extra=error_info)
        else:
            logger.exception("Exception occurred", extra=error_info)
    else:
        logger.error("Unknown error occurred", extra=error_info)

    # Additional context logging for debugging
    if isinstance(update, Update) and update.effective_user:
        logger.error(
            "Error context",
            extra={
                "user_id": update.effective_user.id,
                "error_category": error_info.get("error_category", "unknown"),
                "bot_data_active": context.bot_data.get("BOT_IS_ACTIVE", "unknown"),
            },
        )


def _classify_error(error: Optional[Exception]) -> str:
    """Classify error type for better handling and logging."""
    if error is None:
        return "unknown"

    error_str = str(error).lower()
    error_type = type(error).__name__.lower()

    # Network and connection errors
    if any(
        keyword in error_str
        for keyword in ["network", "connection", "timeout", "unreachable"]
    ):
        return "network"

    if any(keyword in error_type for keyword in ["timeout", "connectionerror"]):
        return "timeout"

    # API and rate limiting errors
    if any(
        keyword in error_str for keyword in ["rate limit", "too many requests", "quota"]
    ):
        return "rate_limit"

    # Permission and authorization errors
    if any(
        keyword in error_str
        for keyword in ["forbidden", "unauthorized", "permission", "access denied"]
    ):
        return "permission"

    # Telegram API specific errors
    if any(
        keyword in error_str for keyword in ["bad request", "invalid", "parse error"]
    ):
        return "user_input"

    # Database or storage errors
    if any(
        keyword in error_str for keyword in ["database", "storage", "file not found"]
    ):
        return "storage"

    # OpenAI specific errors
    if any(keyword in error_str for keyword in ["openai", "completion", "model"]):
        return "openai"

    return "unknown"
