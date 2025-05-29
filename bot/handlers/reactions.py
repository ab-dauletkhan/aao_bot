from telegram.ext import ContextTypes
from telegram import Update, ReactionTypeEmoji
from config import ADVISOR_USER_IDS, MODERATOR_CHAT_ID
from utils import log_user_info
from loguru import logger


async def handle_reaction_downvote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles downvote reactions to delete messages."""
    early_chat_id = "unknown_chat"
    if update and update.message_reaction and update.message_reaction.chat:
        early_chat_id = update.message_reaction.chat.id
    elif update and update.effective_chat: # Fallback if message_reaction not present initially
        early_chat_id = update.effective_chat.id

    with logger.contextualize(chat_id=early_chat_id):
        logger.debug("Reaction handler triggered", extra={"update_type": str(type(update))})

        if not update.message_reaction or not update.message_reaction.user:
            logger.debug("No message reaction or user found")
            return

        reaction = update.message_reaction
        chat = reaction.chat
        message_id = reaction.message_id
        user = reaction.user
        assert user is not None
        user_id = user.id

        # Ensure chat_id is the definite one from reaction.chat
        with logger.contextualize(chat_id=chat.id):
            logger.info(
                "Reaction received",
                extra={"user_id": user_id, "chat_id": chat.id, "message_id": message_id},
            )

            if user_id not in ADVISOR_USER_IDS:
                logger.debug("Non-advisor reaction ignored", extra={"user_id": user_id})
                log_user_info(update, "reaction_ignored", {"reason": "Non-advisor user"})
                return

            downvote_emoji = "👎"
            is_new_downvote = any(
                isinstance(rtype, ReactionTypeEmoji) and rtype.emoji == downvote_emoji
                for rtype in reaction.new_reaction
            )

            if not is_new_downvote:
                logger.debug("Not a new thumbs down reaction")
                return

            if MODERATOR_CHAT_ID and str(chat.id) == MODERATOR_CHAT_ID:
                logger.info("Skipping deletion in moderator chat", extra={"chat_id": chat.id})
                log_user_info(update, "downvote_skipped", {"reason": "Moderator chat"})
                return

            try:
                await context.bot.delete_message(chat_id=chat.id, message_id=message_id)
                logger.info(
                    "Message deleted",
                    extra={"chat_id": chat.id, "message_id": message_id, "advisor_id": user_id},
                )
                log_user_info(
                    update, "message_deleted", {"message_id": message_id, "advisor_id": user_id}
                )
            except Exception as e:
                logger.exception("Failed to delete message", extra={"error": str(e)})
                log_user_info(update, "delete_failed", {"error": str(e)})
