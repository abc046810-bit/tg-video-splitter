"""Common utilities."""

from pathlib import Path
from telegram import Update

import config


def is_owner(update: Update) -> bool:
    user = update.effective_user
    return user.id == config.OWNER_ID if user else False


async def send_access_denied(update: Update) -> None:
    if update.effective_message:
        await update.effective_message.reply_text("Access Denied.")


def is_supported_format(filename: str) -> bool:
    ext = Path(filename).suffix.lstrip(".").lower()
    return ext in config.SUPPORTED_FORMATS
  
