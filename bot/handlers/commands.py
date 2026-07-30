"""
bot/handlers/commands.py
/start, /help, /status, /cancel command handlers.
"""
from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import Message

from bot.core.database import AsyncSessionLocal, JobRepo, UserRepo
from bot.core.queue import job_queue
from bot.utils.logger import logger
from config import settings

# ── /start ─────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("start") & filters.private)
async def cmd_start(client: Client, message: Message) -> None:
    user = message.from_user
    async with AsyncSessionLocal() as session:
        repo = UserRepo(session)
        await repo.get_or_create(user.id, user.username, user.first_name)
        await session.commit()

    text = (
        f"👋 **Welcome, {user.first_name}!**\n\n"
        "I can **split any video into short clips** automatically.\n\n"
        "📥 **Just send me:**\n"
        "• A video file\n"
        "• A forwarded video\n"
        "• A direct `.mp4` URL\n"
        "• A YouTube link\n\n"
        "⚙️ Use /settings to configure clip length, format, watermarks and more.\n"
        "❓ Use /help for full documentation.\n\n"
        "🚀 Ready — send a video to get started!"
    )
    await message.reply_text(text)
    logger.info(f"New user: {user.id} (@{user.username})")


# ── /help ──────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("help") & filters.private)
async def cmd_help(client: Client, message: Message) -> None:
    text = (
        "📖 **Help Menu**\n\n"
        "**Commands:**\n"
        "• /start — Welcome message\n"
        "• /help — This menu\n"
        "• /settings — Configure split options\n"
        "• /status — Your current job status\n"
        "• /cancel — Cancel the active job\n\n"
        "**Supported Inputs:**\n"
        "• Telegram video files (up to "
        f"{settings.max_file_size_mb} MB)\n"
        "• Direct `.mp4`/`.mkv` URLs\n"
        "• YouTube links (via yt-dlp)\n"
        "• Forwarded videos\n\n"
        "**Default Settings:**\n"
        "• Clip length: 10 seconds\n"
        "• Format: MP4 (stream copy — no quality loss)\n"
        "• Watermark: OFF\n"
        "• Thumbnail: ON\n"
        "• ZIP output: OFF\n\n"
        "⚙️ Change everything with /settings."
    )
    await message.reply_text(text)


# ── /status ────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("status") & filters.private)
async def cmd_status(client: Client, message: Message) -> None:
    user_id = message.from_user.id
    active = job_queue.active_count
    pending = job_queue.queue_size

    # Try to find the user's most recent job
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select, desc
        from bot.core.database import Job

        result = await session.execute(
            select(Job)
            .where(Job.user_id == user_id)
            .order_by(desc(Job.created_at))
            .limit(1)
        )
        job = result.scalar_one_or_none()

    if job:
        status_emoji = {
            "queued": "⏳", "processing": "⚙️",
            "done": "✅", "failed": "❌", "cancelled": "🛑",
        }.get(job.status, "❓")

        text = (
            f"📊 **Your Job Status**\n\n"
            f"Job ID: `{job.id}`\n"
            f"Status: {status_emoji} `{job.status}`\n"
        )
        if job.duration:
            text += f"Video: `{job.duration:.0f}s` → `{job.clips_count}` clips\n"
        if job.processing_time:
            text += f"Processed in: `{job.processing_time:.1f}s`\n"
    else:
        text = "📊 **Status**\n\nNo jobs found. Send a video to begin!"

    text += f"\n🌐 Queue: `{pending}` waiting | `{active}` processing"
    await message.reply_text(text)


# ── /cancel ────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("cancel") & filters.private)
async def cmd_cancel(client: Client, message: Message) -> None:
    user_id = message.from_user.id

    # Find the user's active job
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select, desc
        from bot.core.database import Job

        result = await session.execute(
            select(Job)
            .where(Job.user_id == user_id, Job.status.in_(["queued", "processing"]))
            .order_by(desc(Job.created_at))
            .limit(1)
        )
        job = result.scalar_one_or_none()

    if job:
        cancelled = job_queue.cancel(job.id)
        if cancelled:
            await message.reply_text(f"🛑 **Cancellation requested** for job `{job.id}`.")
        else:
            await message.reply_text("⚠️ Could not find an active job to cancel.")
    else:
        await message.reply_text("ℹ️ You have no active jobs to cancel.")
