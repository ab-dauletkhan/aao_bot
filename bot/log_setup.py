import sys
from loguru import logger
from logtail import LogtailHandler

from bot.config import LOGTAIL_SOURCE_TOKEN, LOGTAIL_HOST

def setup_logging() -> None:
    """Set up loguru with rotation and JSON serialization."""

    logtail_handler = LogtailHandler(
        source_token=LOGTAIL_SOURCE_TOKEN,
        host=LOGTAIL_HOST
    )

    logger.remove()

    logger.add(
        sys.stdout,
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
        colorize=True,
    )

    logger.add(
        logtail_handler,
        level="INFO",
        format="{message}",
    )

    logger.add(
        "logs/bot_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="7 days",
        level="DEBUG",
        compression="zip",
        serialize=False,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
    )

    logger.add(
        "logs/bot_structured_{time:YYYY-MM-DD}.json",
        rotation="1 day",
        retention="7 days",
        level="INFO",
        serialize=True,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
    )
