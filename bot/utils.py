from telegram import Update
from loguru import logger
from typing import Dict, Any, Optional
import datetime


def sanitize_markdown(text: str) -> str:
    """Sanitize markdown text to prevent Telegram parsing errors."""
    if not text:
        return text

    logger.debug(
        "Sanitizing markdown text",
        extra={"text_preview": text[:200] + ("..." if len(text) > 200 else "")},
    )

    for char in ["*", "_", "`"]:
        count = text.count(char)
        if count % 2 != 0:
            last_pos = text.rfind(char)  # type: ignore
            if last_pos >= 0:
                text = text[:last_pos] + "\\" + char + text[last_pos + 1 :]
                logger.debug(f"Fixed unmatched {char}")

    if text.count("[") != text.count("]"):
        text = text.replace("[", "\\[").replace("]", "\\]")
        logger.debug("Fixed unmatched square brackets")

    for char in [">", "<", "&"]:
        text = text.replace(char, f"\\{char}")

    logger.debug(
        "Sanitized text",
        extra={"text_preview": text[:200] + ("..." if len(text) > 200 else "")},
    )
    return text


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


def log_with_context(
    update: Update,
    level: str,
    message: str,
    extra_data: Optional[Dict[str, Any]] = None,
) -> None:
    """Enhanced logging with consistent user context."""
    context = get_user_context(update)

    if extra_data:
        context.update(extra_data)

    context["timestamp"] = datetime.datetime.now().isoformat()

    log_func = getattr(logger, level.lower(), logger.info)
    log_func(message, extra=context)


def log_user_info(
    update: Update, action: str, additional_info: Dict[str, Any] = {}
) -> Dict[str, Any]:
    """Log user information with structured data - Enhanced version."""
    context = get_user_context(update)

    user_info = {
        **context,
        "action": action,
        "timestamp": datetime.datetime.now().isoformat(),
    }
    user_info.update(additional_info)

    logger.info("USER_ACTION", extra=user_info)
    return user_info
