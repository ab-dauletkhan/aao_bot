from telegram.ext import ContextTypes
from telegram import Update, ReactionTypeEmoji
from loguru import logger
from bot.config import ADVISOR_USER_IDS, MODERATOR_CHAT_ID
from bot.utils import log_user_info, log_with_context


async def handle_reaction_downvote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles downvote reactions to delete messages with enhanced logging."""
    log_with_context(
        update,
        "debug",
        "Reaction handler triggered",
        {"update_type": str(type(update))},
    )

    if not update.message_reaction or not update.message_reaction.user:
        logger.debug("No message reaction or user found")
        return

    reaction = update.message_reaction
    chat = reaction.chat
    message_id = reaction.message_id
    user = reaction.user
    assert user is not None
    user_id = user.id

    # Create logging context from reaction data
    reaction_context = {
        "user_id": user_id,
        "username": user.username if user.username else None,
        "first_name": user.first_name if user.first_name else None,
        "last_name": user.last_name if user.last_name else None,
        "chat_id": chat.id,
        "chat_type": chat.type,
        "chat_title": getattr(chat, "title", "private"),
        "message_id": message_id,
        "reaction_type": "message_reaction",
    }

    logger.info("Reaction received", extra=reaction_context)

    if user_id != null and user_id not in ADVISOR_USER_IDS:
        logger.debug(
            "Non-advisor reaction ignored",
            extra={
                **reaction_context,
                "advisor_list_size": len(ADVISOR_USER_IDS),
                "is_authorized": False,
            },
        )
        log_user_info(update, "reaction_ignored", {"reason": "Non-advisor user"})
        return

    downvote_emoji = "👎"
    is_new_downvote = any(
        isinstance(rtype, ReactionTypeEmoji) and rtype.emoji == downvote_emoji
        for rtype in reaction.new_reaction
    )

    if not is_new_downvote:
        logger.debug(
            "Not a new thumbs down reaction",
            extra={
                **reaction_context,
                "reaction_types": [str(r) for r in reaction.new_reaction],
            },
        )
        return

    if MODERATOR_CHAT_ID and str(chat.id) == MODERATOR_CHAT_ID:
        logger.info(
            "Skipping deletion in moderator chat",
            extra={
                **reaction_context,
                "moderator_chat_id": MODERATOR_CHAT_ID,
                "is_moderator_chat": True,
            },
        )
        log_user_info(update, "downvote_skipped", {"reason": "Moderator chat"})
        return

    try:
        await context.bot.delete_message(chat_id=chat.id, message_id=message_id)
        logger.info(
            "Message deleted successfully",
            extra={
                **reaction_context,
                "advisor_id": user_id,
                "deletion_successful": True,
            },
        )
        log_user_info(
            update, "message_deleted", {"message_id": message_id, "advisor_id": user_id}
        )
    except Exception as e:
        logger.error(
            "Failed to delete message",
            extra={
                **reaction_context,
                "advisor_id": user_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "deletion_successful": False,
            },
        )
        log_user_info(update, "delete_failed", {"error": str(e)})
