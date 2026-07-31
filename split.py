"""Video split handler and logic."""

import logging
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

import config
from ffmpeg_utils import FFmpegError, split_video
from helpers import cleanup_path, cleanup_session, ensure_user_dir, is_supported_format
from states import BotState

logger = logging.getLogger(__name__)

DURATION_OPTIONS = {
    "5": 5,
    "10": 10,
    "20": 20,
    "30": 30,
    "60": 60,
    "custom": None,
}


def build_duration_keyboard() -> InlineKeyboardMarkup:
    """Build inline keyboard for duration selection."""
    buttons = [
        [
            InlineKeyboardButton("5 sec", callback_data="5"),
            InlineKeyboardButton("10 sec", callback_data="10"),
            InlineKeyboardButton("20 sec", callback_data="20"),
        ],
        [
            InlineKeyboardButton("30 sec", callback_data="30"),
            InlineKeyboardButton("60 sec", callback_data="60"),
            InlineKeyboardButton("Custom", callback_data="custom"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


async def split_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /split command."""
    cleanup_session(update, context)
    await update.effective_message.reply_text(
        "Select clip duration:",
        reply_markup=build_duration_keyboard(),
    )
    return BotState.SPLIT_SELECT_DURATION


async def split_duration_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle duration selection from inline keyboard."""
    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == "custom":
        await query.edit_message_text("Enter duration in seconds.\nExample: 17")
        return BotState.SPLIT_ENTER_CUSTOM

    duration = DURATION_OPTIONS.get(choice)
    if duration is None:
        await query.edit_message_text("Invalid selection. Please try /split again.")
        return ConversationHandler.END

    context.user_data["split_duration"] = duration
    await query.edit_message_text(
        f"Duration set to {duration} seconds.\nNow upload your video."
    )
    return BotState.SPLIT_WAIT_VIDEO


async def split_custom_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle custom duration input."""
    text = update.effective_message.text.strip()
    try:
        duration = int(text)
        if duration < 1:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text(
            "Invalid duration. Please enter a positive integer (e.g., 17)."
        )
        return BotState.SPLIT_ENTER_CUSTOM

    context.user_data["split_duration"] = duration
    await update.effective_message.reply_text(
        f"Duration set to {duration} seconds.\nNow upload your video."
    )
    return BotState.SPLIT_WAIT_VIDEO


def _get_video_from_message(message):
    """Extract video or document object from message."""
    if message.video:
        return message.video
    if message.document:
        return message.document
    return None


async def split_receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle video upload for splitting."""
    message = update.effective_message
    video = _get_video_from_message(message)

    if video is None:
        await message.reply_text("Please upload a video file.")
        return BotState.SPLIT_WAIT_VIDEO

    file_name = video.file_name or f"video_{video.file_id}.mp4"

    if not is_supported_format(file_name):
        await message.reply_text(
            f"Unsupported format. Supported: {', '.join(sorted(config.SUPPORTED_FORMATS))}"
        )
        return BotState.SPLIT_WAIT_VIDEO

    duration = context.user_data.get("split_duration")
    if not duration:
        await message.reply_text("Duration not set. Please restart with /split.")
        return ConversationHandler.END

    user_id = update.effective_user.id
    user_download_dir = ensure_user_dir(config.DOWNLOADS_DIR, user_id)
    user_split_dir = ensure_user_dir(config.SPLIT_DIR, user_id)

    input_path = user_download_dir / file_name

    try:
        await message.reply_text("Downloading...")
        file = await context.bot.get_file(video.file_id)
        await file.download_to_drive(str(input_path))

        if not input_path.exists():
            raise FFmpegError("Download failed: file not found after download.")

        await message.reply_text("Splitting...")

        async def on_clip_ready(clip_path: Path, current: int, total: int) -> None:
            """Send each clip immediately after it is created."""
            try:
                with open(clip_path, "rb") as f:
                    await message.reply_video(
                        video=f,
                        caption=f"Clip {current}/{total}",
                        supports_streaming=True,
                    )
            except Exception as exc:
                logger.error("Failed to send clip %s: %s", clip_path, exc)
                await message.reply_text(f"Failed to send clip {current}/{total}.")

        await split_video(input_path, user_split_dir, duration, on_clip_ready)

        await message.reply_text("Split Finished.")

    except FFmpegError as exc:
        logger.error("Split error: %s", exc)
        await message.reply_text(f"Error: {exc}")
    except Exception as exc:
        logger.exception("Unexpected split error")
        await message.reply_text(f"Unexpected error: {exc}")
    finally:
        cleanup_path(input_path)
        cleanup_path(user_split_dir)

    return ConversationHandler.END
