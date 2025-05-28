import asyncio
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    filters,
    MessageReactionHandler,
)
from config import (
    TELEGRAM_TOKEN,
    WEBHOOK_DOMAIN,
    WEBHOOK_URL_PATH,
    WEBHOOK_LISTEN_IP,
    WEBHOOK_PORT,
    ADVISOR_USER_IDS,
)
from log_setup import setup_logging
from handlers.commands import start_command, stop_command, status_command
from handlers.messages import handle_message
from handlers.reactions import handle_reaction_downvote
from handlers.errors import error_handler
from webhook import create_webhook_handler, health_check
from loguru import logger
from aiohttp import web


async def send_restart_notifications(application):
    """Send restart notifications to advisors."""
    if not ADVISOR_USER_IDS:
        return

    restart_msg = "✅ Bot restarted and active"
    success_count = 0

    for advisor_id in ADVISOR_USER_IDS:
        try:
            await application.bot.send_message(chat_id=advisor_id, text=restart_msg)
            success_count += 1
            logger.debug(
                "Restart notification sent", extra={"advisor_id": advisor_id}
            )
        except Exception as e:
            logger.exception(
                "Failed to notify advisor",
                extra={"advisor_id": advisor_id, "error": str(e)},
            )

    logger.info(
        "Restart notifications",
        extra={"successful": success_count, "total": len(ADVISOR_USER_IDS)},
    )


async def setup_webhook_mode(application):
    """Setup webhook mode."""
    logger.info("Starting in Webhook Mode", extra={"phase": "webhook"})
    webhook_url = (
        f"https://{WEBHOOK_DOMAIN.rstrip('/')}/{WEBHOOK_URL_PATH.lstrip('/')}"
    )
    logger.info("Webhook URL set", extra={"url": webhook_url})

    try:
        await application.bot.set_webhook(
            webhook_url, allowed_updates=["message", "message_reaction"]
        )
        logger.info("Webhook set", extra={"url": webhook_url})
    except Exception as e:
        logger.exception("Webhook setup failed", extra={"error": str(e)})
        return

    app = web.Application()
    app["application"] = application
    app.router.add_post(f"/{WEBHOOK_URL_PATH}", create_webhook_handler(application))
    app.router.add_get("/health", health_check)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEBHOOK_LISTEN_IP, WEBHOOK_PORT)
    await site.start()
    logger.info(
        "Web server started", extra={"ip": WEBHOOK_LISTEN_IP, "port": WEBHOOK_PORT}
    )

    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Shutdown signal received", extra={"phase": "shutdown"})
    finally:
        await runner.cleanup()


async def post_init(application):
    """Post-initialization tasks."""
    await send_restart_notifications(application)


def main():
    """Main function to start the bot."""
    setup_logging()
    logger.info("=== Bot Initialization ===", extra={"phase": "init"})

    if not TELEGRAM_TOKEN:
        logger.critical("Missing TELEGRAM_BOT_TOKEN", extra={"error": "Cannot start"})
        return
    if not __import__("config").OPENAI_API_KEY:
        logger.warning(
            "Missing OPENAI_API_KEY", extra={"warning": "Limited functionality"}
        )

    logger.info("Creating Telegram application...")
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    application.bot_data["BOT_IS_ACTIVE"] = True

    logger.debug("Registering handlers")
    application.add_handler(MessageReactionHandler(handle_reaction_downvote))
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    application.add_error_handler(error_handler)
    logger.info("All handlers registered")

    if WEBHOOK_DOMAIN and WEBHOOK_URL_PATH:
        logger.info("Starting in Webhook Mode", extra={"phase": "webhook"})
        asyncio.run(setup_webhook_mode(application))
    else:
        logger.info("Starting in Polling Mode", extra={"phase": "polling"})
        application.run_polling(allowed_updates=["message", "message_reaction"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Shutdown signal received", extra={"phase": "shutdown"})
    except Exception as e:
        logger.exception("Fatal error", extra={"error": str(e)})
    finally:
        logger.info("=== Bot Shutdown Complete ===", extra={"phase": "shutdown"})
