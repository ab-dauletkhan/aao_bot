import sys
from loguru import logger
from logtail import LogtailHandler

from bot.config import LOGTAIL_SOURCE_TOKEN, LOGTAIL_HOST

def setup_logging() -> None:
    """Set up loguru with Logtail for all logs."""

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
        level="DEBUG",
        format="{message}",
    )
