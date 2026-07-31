"""Telegram bot command and conversation handlers."""

import logging
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from cleanup import cleanup_session
from download import download_video
from ffmpeg_utils import FFmpegError, merge_videos, split_video
from upload import upload_clips
from utils import is_supported_format
from states import BotState

logger = logging.getLogger(__name__)

OWNER_FILTER = filters.User(user_id=config.OWNER_ID)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Video Tool Bot Ready\n\n"
        "Commands:\n"
        "/split\n"
        "/merge\n"
        "/cancel\n"
        "/help"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "/split - Split a video into clips\n"
        "/merge - Merge multiple clips\n"
        "/cancel - Cancel current operation\n"
        "/help - Show this message"
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cleanup_session(update, context)
    await update.effective_message.reply_text("Cancelled. All files cleaned.")
    return ConversationHandler.END


async def unauthorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text("Access Denied.")


# SPLIT FLOW

async def split_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cleanup_session(update, context)
    await update.effective_message.reply_text(
        "Send duration in seconds.\nExample: 10"
    )
    return BotState.SPLIT_ENTER_DURATION


async def split_duration_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    try:
        duration = int(text)
        if duration < 1:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text(
            "Invalid duration. Send a positive integer.\nExample: 10"
        )
        return BotState.SPLIT_ENTER_DURATION

    context.user_data["split_duration"] = duration
    await update.effective_message.reply_text(
        f"Duration set to {duration}s. Now upload your video."
    )
    return BotState.SPLIT_WAIT_VIDEO


async def split_process_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message
    video = message.video or message.document

    if not video:
        await message.reply_text("Please upload a video file.")
        return BotState.SPLIT_WAIT_VIDEO

    file_name = getattr(video, "file_name", None) or f"video_{video.file_id}.mp4"
    if not is_supported_format(file_name):
        fmts = ", ".join(sorted(config.SUPPORTED_FORMATS))
        await message.reply_text(f"Unsupported format. Supported: {fmts}")
        return BotState.SPLIT_WAIT_VIDEO

    duration = context.user_data.get("split_duration")
    if not duration:
        await message.reply_text("Duration not set. Use /split again.")
        return ConversationHandler.END

    user_id = update.effective_user.id
    temp_dir = config.TEMP_BASE / str(user_id) / "split"
    temp_dir.mkdir(parents=True, exist_ok=True)
    input_path = temp_dir / file_name

    status_msg = await message.reply_text("Starting...")
    pyro_client = context.bot_data["pyro_client"]

    try:
        await download_video(pyro_client, message, input_path, status_msg)
        clips = await split_video(input_path, temp_dir, duration, status_msg.edit_text)
        await upload_clips(pyro_client, message.chat_id, clips, status_msg)
        await status_msg.edit_text("Split Finished.")
    except FFmpegError as exc:
        logger.error("Split FFmpeg error: %s", exc)
        await status_msg.edit_text(f"FFmpeg Error: {exc}")
    except Exception as exc:
        logger.exception("Split unexpected error")
        await status_msg.edit_text(f"Unexpected error: {exc}")
    finally:
        cleanup_session(update, context)

    return ConversationHandler.END


# MERGE FLOW

async def merge_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cleanup_session(update, context)
    context.user_data["merge_clips"] = []
    await update.effective_message.reply_text(
        "Send clips in the order you want them merged.\n"
        "When finished, send /done"
    )
    return BotState.MERGE_COLLECT


async def merge_receive_clip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message
    video = message.video or message.document

    if not video:
        await message.reply_text("Please upload a video clip.")
        return BotState.MERGE_COLLECT

    file_name = getattr(video, "file_name", None) or f"clip_{video.file_id}.mp4"
    if not is_supported_format(file_name):
        fmts = ", ".join(sorted(config.SUPPORTED_FORMATS))
        await message.reply_text(f"Unsupported format. Supported: {fmts}")
        return BotState.MERGE_COLLECT

    user_id = update.effective_user.id
    temp_dir = config.TEMP_BASE / str(user_id) / "merge"
    temp_dir.mkdir(parents=True, exist_ok=True)

    clips = context.user_data.setdefault("merge_clips", [])
    count = len(clips) + 1
    ext = Path(file_name).suffix or ".mp4"
    clip_path = temp_dir / f"{count:04d}{ext}"

    try:
        pyro_client = context.bot_data["pyro_client"]
        status_msg = await message.reply_text(f"Downloading clip {count}...")
        await download_video(pyro_client, message, clip_path, status_msg)
        clips.append(clip_path)
        await status_msg.edit_text(f"Clip {count} received. Send next or /done")
    except Exception as exc:
        logger.exception("Merge receive error")
        await message.reply_text(f"Failed to download clip: {exc}")

    return BotState.MERGE_COLLECT


async def merge_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message
    clips = context.user_data.get("merge_clips", [])

    if not clips:
        await message.reply_text("No clips received. Merge cancelled.")
        cleanup_session(update, context)
        return ConversationHandler.END

    user_id = update.effective_user.id
    temp_dir = config.TEMP_BASE / str(user_id)
    output_path = temp_dir / "merged_output.mp4"
    status_msg = await message.reply_text("Starting merge...")
    pyro_client = context.bot_data["pyro_client"]

    try:
        await merge_videos(clips, output_path, status_msg.edit_text)
        await upload_clips(
            pyro_client,
            message.chat_id,
            [output_path],
            status_msg,
            caption_prefix="Merged",
        )
        await status_msg.edit_text("Merge Finished.")
    except FFmpegError as exc:
        logger.error("Merge FFmpeg error: %s", exc)
        await status_msg.edit_text(f"FFmpeg Error: {exc}")
    except Exception as exc:
        logger.exception("Merge unexpected error")
        await status_msg.edit_text(f"Unexpected error: {exc}")
    finally:
        cleanup_session(update, context)

    return ConversationHandler.END


# HANDLER REGISTRATION

def setup_handlers(application: Application) -> None:
    split_conv = ConversationHandler(
        entry_points=[
            CommandHandler("split", split_command, filters=OWNER_FILTER)
        ],
        states={
            BotState.SPLIT_ENTER_DURATION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & OWNER_FILTER,
                    split_duration_input,
                ),
            ],
            BotState.SPLIT_WAIT_VIDEO: [
                MessageHandler(
                    (filters.VIDEO | filters.Document.VIDEO) & OWNER_FILTER,
                    split_process_video,
                ),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command, filters=OWNER_FILTER)],
        allow_reentry=True,
    )

    merge_conv = ConversationHandler(
        entry_points=[
            CommandHandler("merge", merge_command, filters=OWNER_FILTER)
        ],
        states={
            BotState.MERGE_COLLECT: [
                MessageHandler(
                    (filters.VIDEO | filters.Document.VIDEO) & OWNER_FILTER,
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
    application.add_handler(MessageHandler(~OWNER_FILTER, unauthorized))
