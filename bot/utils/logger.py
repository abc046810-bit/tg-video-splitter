"""
bot/utils/logger.py
Centralised logging via loguru with separate error + processing sinks.
"""
import sys
from pathlib import Path

from loguru import logger

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Remove default handler
logger.remove()

# Console – coloured
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True,
)

# General rotating log
logger.add(
    LOG_DIR / "bot.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
    level="DEBUG",
    rotation="50 MB",
    retention="14 days",
    compression="zip",
    encoding="utf-8",
)

# Error-only log
logger.add(
    LOG_DIR / "error.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}\n{exception}",
    level="ERROR",
    rotation="10 MB",
    retention="30 days",
    compression="zip",
    encoding="utf-8",
)

# Processing-only log (filter by extra tag)
logger.add(
    LOG_DIR / "processing.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    level="DEBUG",
    rotation="20 MB",
    retention="7 days",
    filter=lambda record: record["extra"].get("processing", False),
    encoding="utf-8",
)

__all__ = ["logger"]
