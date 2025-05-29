from aiohttp import web
from telegram import Update
from loguru import logger
from datetime import datetime
import time
import json

from bot.config import FAQ_CONTENT
from bot.openai_client import client


def create_webhook_handler(application):
    """Create a webhook handler using the provided application."""

    async def webhook_handler(request):
        request_start_time = time.time()
        client_ip = request.remote

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
            logger.exception("Webhook error", extra={"error": str(e)})
            return web.Response(status=500)

    return webhook_handler


async def health_check(request):
    """Health check endpoint."""
    logger.debug("Health check request")

    health_status = {
        "status": "healthy",
        "bot_active": request.app["application"].bot_data.get("BOT_IS_ACTIVE", True),
        "faq_loaded": bool(FAQ_CONTENT),
        "openai_connected": bool(client),
        "timestamp": datetime.now().isoformat(),
    }
    logger.debug("Health status", extra=health_status)
    return web.Response(text="OK", status=200)
