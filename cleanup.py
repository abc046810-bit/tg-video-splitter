"""Session cleanup utilities."""

import shutil
import logging
from telegram import Update
from telegram.ext import ContextTypes

import config

logger = logging.getLogger(__name__)


def cleanup_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove all temporary files for the current user session."""
    user = update.effective_user
    user_id = user.id if user else "unknown"
    user_dir = config.TEMP_BASE / str(user_id)

    if user_dir.exists():
        try:
            shutil.rmtree(user_dir, ignore_errors=True)
            logger.info("Cleaned up user dir: %s", user_dir)
        except Exception as exc:
            logger.warning("Cleanup failed for %s: %s", user_dir, exc)

    for key in ("split_duration", "merge_clips", "merge_count"):
        context.user_data.pop(key, None)
      
