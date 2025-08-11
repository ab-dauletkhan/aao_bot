from telegram.ext import ContextTypes
from telegram import Update, ReactionTypeEmoji
from loguru import logger
from bot.config import ADVISOR_USER_IDS, MODERATOR_CHAT_ID
from bot.utils import log_user_info, log_with_context


async def _process_downvote(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE, 
    reaction_context: dict, 
    source: str
):
    """Process downvote reaction and delete message if valid."""
    reaction = update.message_reaction
    chat = reaction.chat
    message_id = reaction.message_id

    # Check if it's a downvote reaction
    downvote_emoji = "👎"
    is_new_downvote = any(
        isinstance(rtype, ReactionTypeEmoji) and rtype.emoji == downvote_emoji
        for rtype in reaction.new_reaction
    )

    if not is_new_downvote:
        logger.debug(
            f"Not a new thumbs down reaction ({source})",
            extra={
                **reaction_context,
                "reaction_types": [str(r) for r in reaction.new_reaction],
            },
        )
        return

    if MODERATOR_CHAT_ID and str(chat.id) == MODERATOR_CHAT_ID:
        logger.info(
            f"Skipping deletion in moderator chat ({source})",
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
            f"Message deleted successfully ({source})",
            extra={
                **reaction_context,
                "deletion_successful": True,
            },
        )
        log_user_info(
            update, "message_deleted", {"message_id": message_id, "source": source}
        )
    except Exception as e:
        logger.error(
            f"Failed to delete message ({source})",
            extra={
                **reaction_context,
                "error": str(e),
                "error_type": type(e).__name__,
                "deletion_successful": False,
            },
        )
        log_user_info(update, "delete_failed", {"error": str(e), "source": source})


async def handle_reaction_downvote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles downvote reactions to delete messages with enhanced logging."""
    log_with_context(
        update,
        "debug",
        "Reaction handler triggered",
        {"update_type": str(type(update))},
    )

    if not update.message_reaction:
        logger.debug("No message reaction found")
        return

    reaction = update.message_reaction
    chat = reaction.chat
    message_id = reaction.message_id
    user = reaction.user

    # Handle case where user is None (chat downvote)
    if user is None:
        reaction_context = {
            "user_id": None,
            "username": None,
            "first_name": None,
            "last_name": None,
            "chat_id": chat.id,
            "chat_type": chat.type,
            "chat_title": getattr(chat, "title", "private"),
            "message_id": message_id,
            "reaction_type": "message_reaction",
            "is_chat_downvote": True,
        }

        logger.info("Chat downvote reaction received", extra=reaction_context)
        await _process_downvote(update, context, reaction_context, "chat_downvote")
        return

    # Handle regular user reactions
    user_id = user.id
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
        "is_chat_downvote": False,
    }

    logger.info("User reaction received", extra=reaction_context)

    if user_id not in ADVISOR_USER_IDS:
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

    await _process_downvote(update, context, reaction_context, "user_downvote")
