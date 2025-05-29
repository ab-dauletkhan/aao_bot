from telegram.ext import ContextTypes
from telegram import Update
from bot.config import ADVISOR_USER_IDS
from bot.utils import log_user_info, log_with_context
from loguru import logger


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command for advisors only with enhanced logging."""
    log_with_context(update, "debug", "Processing /start command")

    if not update.message or not update.effective_user:
        logger.warning(
            "Invalid /start command", extra={"error": "Missing message or user"}
        )
        return

    user_id = update.effective_user.id

    if user_id not in ADVISOR_USER_IDS:
        log_with_context(
            update,
            "warning",
            "Non-advisor attempted /start command",
            {"advisor_list_size": len(ADVISOR_USER_IDS), "is_authorized": False},
        )
        log_user_info(update, "start_command_denied", {"reason": "Not in advisor list"})
        await update.message.reply_text(
            "Sorry, this command is only available to advisors."
        )
        return

    old_status = context.bot_data.get("BOT_IS_ACTIVE", True)
    context.bot_data["BOT_IS_ACTIVE"] = True

    log_with_context(
        update,
        "info",
        "/start command executed successfully",
        {"old_status": old_status, "new_status": True, "is_authorized": True},
    )
    log_user_info(update, "start_command_success", {"previous_status": old_status})

    await update.message.reply_text(
        "✅ Bot is now active and will respond to student questions."
    )


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /stop command for advisors only with enhanced logging."""
    log_with_context(update, "debug", "Processing /stop command")

    if not update.message or not update.effective_user:
        logger.warning(
            "Invalid /stop command", extra={"error": "Missing message or user"}
        )
        return

    user_id = update.effective_user.id

    if user_id not in ADVISOR_USER_IDS:
        log_with_context(
            update,
            "warning",
            "Non-advisor attempted /stop command",
            {"advisor_list_size": len(ADVISOR_USER_IDS), "is_authorized": False},
        )
        log_user_info(update, "stop_command_denied", {"reason": "Not in advisor list"})
        await update.message.reply_text(
            "Sorry, this command is only available to advisors."
        )
        return

    old_status = context.bot_data.get("BOT_IS_ACTIVE", True)
    context.bot_data["BOT_IS_ACTIVE"] = False

    log_with_context(
        update,
        "info",
        "/stop command executed successfully",
        {"old_status": old_status, "new_status": False, "is_authorized": True},
    )
    log_user_info(update, "stop_command_success", {"previous_status": old_status})

    await update.message.reply_text(
        "⏹️ Bot is now inactive and will not respond to student questions."
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the current bot status for advisors with enhanced logging."""
    log_with_context(update, "debug", "Processing /status command")

    if not update.message or not update.effective_user:
        logger.warning(
            "Invalid /status command", extra={"error": "Missing message or user"}
        )
        return

    user_id = update.effective_user.id

    if user_id not in ADVISOR_USER_IDS:
        log_with_context(
            update,
            "warning",
            "Non-advisor attempted /status command",
            {"advisor_list_size": len(ADVISOR_USER_IDS), "is_authorized": False},
        )
        log_user_info(
            update, "status_command_denied", {"reason": "Not in advisor list"}
        )
        await update.message.reply_text(
            "Sorry, this command is only available to advisors."
        )
        return

    # Enhanced status collection
    status_info = {
        "bot_active": context.bot_data.get("BOT_IS_ACTIVE", True),
        "faq_loaded": bool(__import__("bot.config").FAQ_CONTENT),
        "faq_length": len(__import__("bot.config").FAQ_CONTENT)
        if __import__("bot.config").FAQ_CONTENT
        else 0,
        "openai_connected": bool(__import__("bot.openai_client").client),
        "advisors_count": len(ADVISOR_USER_IDS),
        "moderator_configured": bool(__import__("bot.config").MODERATOR_CHAT_ID),
        "group_chats_configured": len(__import__("bot.config").GROUP_CHAT_IDS)
        if __import__("bot.config").GROUP_CHAT_IDS
        else 0,
    }

    log_with_context(
        update,
        "info",
        "Status command executed successfully",
        {**status_info, "is_authorized": True},
    )
    log_user_info(update, "status_command_success", status_info)

    status_message = f"""
📊 **Bot Status Report**

🤖 **Core Status:**
• Bot: {"🟢 Active" if status_info["bot_active"] else "🔴 Inactive"}
• FAQ: {"✅ Loaded" if status_info["faq_loaded"] else "❌ Not loaded"} ({status_info["faq_length"]} chars)
• OpenAI: {"✅ Connected" if status_info["openai_connected"] else "❌ Not connected"}

👥 **Configuration:**
• Advisors: {status_info["advisors_count"]} configured
• Moderator: {"✅ Configured" if status_info["moderator_configured"] else "❌ Not configured"}
• Group Chats: {status_info["group_chats_configured"]} configured
    """

    await update.message.reply_text(status_message, parse_mode="Markdown")
