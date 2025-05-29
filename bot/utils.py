from telegram import Update
from loguru import logger
from typing import Dict, Any


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
            last_pos = text.rfind(char)
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


def log_user_info(
    update: Update, action: str, additional_info: Dict[str, Any] = {}
) -> Dict[str, Any]:
    """Log user information with structured data."""
    user = update.effective_user
    chat = update.effective_chat

    chat_id_to_log = chat.id if chat else "unknown_chat"
    # Bind chat_id for all subsequent logs in this context
    with logger.contextualize(chat_id=chat_id_to_log):
        user_info = {
            "user_id": user.id if user else "unknown",
            "username": user.username if user else "unknown",
            "first_name": user.first_name if user else "unknown",
            "last_name": user.last_name if user else "unknown",
            "chat_id": chat_id_to_log, # Keep it in extra as well for the specific USER_ACTION log
            "chat_type": chat.type if chat else "unknown",
            "chat_title": getattr(chat, "title", "private") if chat else "unknown",
            "action": action,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
        }
        user_info.update(additional_info)

        logger.info("USER_ACTION", extra=user_info)
        return user_info
