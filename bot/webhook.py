from aiohttp import web
from telegram import Update
from loguru import logger
from datetime import datetime
import time
import json


def create_webhook_handler(application):
    """Create a webhook handler using the provided application."""

    async def webhook_handler(request):
        request_start_time = time.time()
        client_ip = request.remote
        # Initialize chat_id for logging context. It will be updated if an Update object is processed.
        current_chat_id_for_log = "unknown_chat_webhook"

        with logger.contextualize(chat_id=current_chat_id_for_log):
            logger.debug("Webhook request received", extra={"client_ip": client_ip})

            if not application:
                logger.error("Application not initialized")
                return web.Response(status=500)

            try:
                data = await request.json()
                logger.debug(
                    "Webhook data",
                    extra={
                        "data_preview": json.dumps(data, ensure_ascii=False)[:500]
                        + ("..." if len(str(data)) > 500 else "")
                    },
                )

                update = Update.de_json(data, application.bot)
                if update:
                    if update.effective_chat:
                        current_chat_id_for_log = update.effective_chat.id
                    # Re-contextualize if chat_id is found in the update
                    with logger.contextualize(chat_id=current_chat_id_for_log):
                        await application.process_update(update)
                        processing_time = time.time() - request_start_time
                        logger.info(
                            "Webhook processed",
                            extra={"processing_time": round(processing_time, 2)},
                        )
                else:
                    logger.warning("Failed to create Update object")

                return web.Response(status=200)

            except Exception as e:
                # Log with the most current chat_id we have (could be from a partially processed update)
                logger.exception("Webhook error", extra={"error": str(e)})
                return web.Response(status=500)

    return webhook_handler


async def health_check(request):
    """Health check endpoint."""
    logger.debug("Health check request")
    from config import FAQ_CONTENT
    from openai_client import client

    health_status = {
        "status": "healthy",
        "bot_active": request.app["application"].bot_data.get("BOT_IS_ACTIVE", True),
        "faq_loaded": bool(FAQ_CONTENT),
        "openai_connected": bool(client),
        "timestamp": datetime.now().isoformat(),
    }
    logger.debug("Health status", extra=health_status)
    return web.Response(text="OK", status=200)
