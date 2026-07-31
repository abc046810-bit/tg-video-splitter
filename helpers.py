"""Helper utilities for the Video Tool Bot.

Provides common functions for file management, validation,
and Telegram message helpers.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

import config

logger = logging.getLogger(__name__)


def is_owner(update: Update) -> bool:
    """Check if the incoming update is from the configured owner."""
    user = update.effective_user
    if user is None:
        return False
    return user.id == config.OWNER_ID


async def send_unauthorized(update: Update) -> None:
    """Send unauthorized message to non-owner users."""
    if update.effective_message:
        await update.effective_message.reply_text("Unauthorized.")


def get_file_extension(filename: str) -> str:
    """Return lowercase file extension without leading dot."""
    return Path(filename).suffix.lstrip(".").lower()


def is_supported_format(filename: str) -> bool:
    """Check if file extension is in supported formats."""
    return get_file_extension(filename) in config.SUPPORTED_FORMATS


def cleanup_path(path: Optional[Path]) -> None:
    """Safely delete a file or directory tree."""
    if path is None or not path.exists():
        return
    try:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
        logger.info("Cleaned up: %s", path)
    except Exception as exc:
        logger.warning("Failed to cleanup %s: %s", path, exc)


def cleanup_session(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove all temporary files associated with the current user session."""
    user_id = context.effective_user.id if context.effective_user else "unknown"
    session_dirs = [
        config.DOWNLOADS_DIR / str(user_id),
        config.SPLIT_DIR / str(user_id),
        config.MERGE_DIR / str(user_id),
        config.TEMP_DIR / str(user_id),
    ]
    for d in session_dirs:
        cleanup_path(d)
    # Clear merge list if present
    if "merge_clips" in context.user_data:
        del context.user_data["merge_clips"]
    if "merge_count" in context.user_data:
        del context.user_data["merge_count"]
    if "split_duration" in context.user_data:
        del context.user_data["split_duration"]
    logger.info("Session cleaned for user %s", user_id)


def ensure_user_dir(base: Path, user_id: int) -> Path:
    """Create and return a user-specific subdirectory."""
    user_dir = base / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def format_bytes(size: int) -> str:
    """Convert bytes to human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"
