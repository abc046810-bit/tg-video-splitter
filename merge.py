"""Video merge handler and logic.

Manages the /merge conversation flow and delegates FFmpeg work.
"""

import logging
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import config
from ffmpeg_utils import FFmpegError, merge_videos
from helpers import cleanup_path, cleanup_session, ensure_user_dir, is_supported_format
from states import BotState

logger = logging.getLogger(__name__)


async def merge_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /merge command."""
    cleanup_session(context)
    context.user_data["merge_clips"] = []
    context.user_data["merge_count"] = 0
    await update.effective_message.reply_text(
        "Send clips in the order you want them merged.\n"
        "When finished, send /done"
    )
    return BotState.MERGE_COLLECT


def _get_video_from_message(message):
    """Extract video or document object from message."""
    if message.video:
        return message.video
    if message.document:
        return message.document
    return None


async def merge_receive_clip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle incoming clip during merge collection phase."""
    message = update.effective_message
    video = _get_video_from_message(message)

    if video is None:
        await message.reply_text("Please upload a video clip.")
        return BotState.MERGE_COLLECT

    file_name = video.file_name or f"clip_{video.file_id}.mp4"

    if not is_supported_format(file_name):
        await message.reply_text(
            f"Unsupported format. Supported: {', '.join(sorted(config.SUPPORTED_FORMATS))}"
        )
        return BotState.MERGE_COLLECT

    user_id = update.effective_user.id
    user_merge_dir = ensure_user_dir(config.MERGE_DIR, user_id)

    count = context.user_data.get("merge_count", 0) + 1
    context.user_data["merge_count"] = count

    # Save with sequential numbering to preserve order regardless of filename
    ext = Path(file_name).suffix or ".mp4"
    clip_path = user_merge_dir / f"{count:04d}{ext}"

    try:
        file = await context.bot.get_file(video.file_id)
        await file.download_to_drive(str(clip_path))

        clips = context.user_data.setdefault("merge_clips", [])
        clips.append(clip_path)

        await message.reply_text(f"Received clip {count}. Send next or /done")
    except Exception as exc:
        logger.error("Failed to receive clip: %s", exc)
        await message.reply_text("Failed to download clip. Please try again.")

    return BotState.MERGE_COLLECT


async def merge_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /done to finalize and merge clips."""
    message = update.effective_message
    clips = context.user_data.get("merge_clips", [])

    if not clips:
        await message.reply_text("No clips received. Merge cancelled.")
        cleanup_session(context)
        return ConversationHandler.END

    user_id = update.effective_user.id
    user_merge_dir = ensure_user_dir(config.MERGE_DIR, user_id)
    user_temp_dir = ensure_user_dir(config.TEMP_DIR, user_id)
    output_path = user_temp_dir / "merged_output.mp4"

    try:
        await message.reply_text("Receiving Clips...")

        async def progress_callback(status: str) -> None:
            await message.reply_text(status)

        await merge_videos(clips, output_path, progress_callback)

        if not output_path.exists():
            raise FFmpegError("Merge failed: output file not created.")

        await message.reply_text("Uploading Final Video...")
        with open(output_path, "rb") as f:
            await message.reply_video(
                video=f,
                caption="Merged video",
                supports_streaming=True,
            )

        await message.reply_text("Completed.")

    except FFmpegError as exc:
        logger.error("Merge error: %s", exc)
        await message.reply_text(f"Merge error: {exc}")
    except Exception as exc:
        logger.exception("Unexpected merge error")
        await message.reply_text(f"Unexpected error: {exc}")
    finally:
        cleanup_path(user_merge_dir)
        cleanup_path(user_temp_dir)
        if "merge_clips" in context.user_data:
            del context.user_data["merge_clips"]
        if "merge_count" in context.user_data:
            del context.user_data["merge_count"]

    return ConversationHandler.END
