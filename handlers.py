"""Telegram bot handlers.

Registers all command handlers, conversation handlers, and middleware.
"""

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

import config
from helpers import cleanup_session, send_unauthorized
from merge import merge_command, merge_done, merge_receive_clip
from split import (
    split_command,
    split_custom_duration,
    split_duration_callback,
    split_receive_video,
)
from states import BotState

logger = logging.getLogger(__name__)

# Owner-only filter using effective_user
OWNER_FILTER = filters.User(user_id=config.OWNER_ID)


async def start_command(update: Update, _context) -> None:
    """Handle /start command."""
    await update.effective_message.reply_text(
        "Video Tool Bot Ready\n\n"
        "Commands:\n"
        "/split\n"
        "/merge\n"
        "/cancel\n"
        "/help"
    )


async def help_command(update: Update, _context) -> None:
    """Handle /help command."""
    await update.effective_message.reply_text(
        "Available commands:\n\n"
        "/split - Split a video into clips\n"
        "/merge - Merge multiple clips into one video\n"
        "/cancel - Cancel current operation and cleanup\n"
        "/help - Show this help message"
    )


async def cancel_command(update: Update, context) -> int:
    """Handle /cancel command to abort any ongoing operation."""
    cleanup_session(context)
    await update.effective_message.reply_text("Cancelled. All temporary files removed.")
    return ConversationHandler.END


async def unauthorized_handler(update: Update, _context) -> None:
    """Catch-all handler for non-owner messages outside conversations."""
    await send_unauthorized(update)


async def owner_callback_query_handler(update: Update, context) -> int:
    """Enforce owner-only access on callback queries and route to split handler."""
    if update.effective_user and update.effective_user.id == config.OWNER_ID:
        return await split_duration_callback(update, context)
    await send_unauthorized(update)
    return ConversationHandler.END


def setup_handlers(application: Application) -> None:
    """Register all handlers with the application."""

    # Split conversation handler (owner only)
    split_conv = ConversationHandler(
        entry_points=[
            CommandHandler("split", split_command, filters=OWNER_FILTER)
        ],
        states={
            BotState.SPLIT_SELECT_DURATION: [
                CallbackQueryHandler(owner_callback_query_handler),
            ],
            BotState.SPLIT_ENTER_CUSTOM: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & OWNER_FILTER,
                    split_custom_duration,
                ),
            ],
            BotState.SPLIT_WAIT_VIDEO: [
                MessageHandler(
                    filters.VIDEO & OWNER_FILTER,
                    split_receive_video,
                ),
                MessageHandler(
                    filters.Document.VIDEO & OWNER_FILTER,
                    split_receive_video,
                ),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command, filters=OWNER_FILTER)],
        allow_reentry=True,
    )

    # Merge conversation handler (owner only)
    merge_conv = ConversationHandler(
        entry_points=[
            CommandHandler("merge", merge_command, filters=OWNER_FILTER)
        ],
        states={
            BotState.MERGE_COLLECT: [
                MessageHandler(
                    filters.VIDEO & OWNER_FILTER,
                    merge_receive_clip,
                ),
                MessageHandler(
                    filters.Document.VIDEO & OWNER_FILTER,
                    merge_receive_clip,
                ),
                CommandHandler("done", merge_done, filters=OWNER_FILTER),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command, filters=OWNER_FILTER)],
        allow_reentry=True,
    )

    application.add_handler(CommandHandler("start", start_command, filters=OWNER_FILTER))
    application.add_handler(CommandHandler("help", help_command, filters=OWNER_FILTER))
    application.add_handler(split_conv)
    application.add_handler(merge_conv)

    # Catch-all for non-owner users (must be last)
    application.add_handler(
        MessageHandler(~OWNER_FILTER, unauthorized_handler)
    )
