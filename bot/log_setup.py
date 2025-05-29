from loguru import logger
import sys


def setup_logging() -> None:
    """Set up loguru with rotation and JSON serialization."""
    logger.remove()

    logger.add(
        sys.stdout,
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
        colorize=True,
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
