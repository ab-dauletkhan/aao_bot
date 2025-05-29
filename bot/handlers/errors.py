from telegram.ext import ContextTypes
from telegram import Update
from loguru import logger
from datetime import datetime


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
