from telegram.ext import ContextTypes
from telegram import Update
from config import ADVISOR_USER_IDS
from utils import log_user_info
from loguru import logger


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

    old_status = context.bot_data.get("BOT_IS_ACTIVE", True)
    context.bot_data["BOT_IS_ACTIVE"] = True

    logger.info(
        "/start command executed",
        extra={"user_id": user_id, "old_status": old_status, "new_status": True},
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

    old_status = context.bot_data.get("BOT_IS_ACTIVE", True)
    context.bot_data["BOT_IS_ACTIVE"] = False

    logger.info(
        "/stop command executed",
        extra={"user_id": user_id, "old_status": old_status, "new_status": False},
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
        "bot_active": context.bot_data.get("BOT_IS_ACTIVE", True),
        "faq_loaded": bool(__import__("config").FAQ_CONTENT),
        "openai_connected": bool(__import__("openai_client").client),
        "advisors_count": len(ADVISOR_USER_IDS),
    }

    logger.info("Status command executed", extra={"user_id": user_id, **status_info})
    log_user_info(update, "status_command_success", status_info)

    status_message = f"""
📊 **Bot Status**
Status: {"🟢 Active" if status_info["bot_active"] else "🔴 Inactive"}
FAQ: {"✅ Loaded" if status_info["faq_loaded"] else "❌ Not loaded"}
OpenAI: {"✅ Connected" if status_info["openai_connected"] else "❌ Not connected"}
Advisors: {len(ADVISOR_USER_IDS)} configured
    """

    await update.message.reply_text(status_message, parse_mode="Markdown")
