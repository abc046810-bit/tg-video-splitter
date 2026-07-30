"""
bot/handlers/video.py
Handles incoming video messages, document videos, and URL text messages.
Enqueues jobs into the JobQueue.
"""
from __future__ import annotations

import asyncio

from pyrogram import Client, filters
from pyrogram.types import Message

from bot.core.database import AsyncSessionLocal, JobRepo, UserRepo
from bot.core.processor import process_job
from bot.core.queue import QueuedJob, job_queue
from bot.utils.logger import logger
from bot.utils.ui import cancel_kb, format_size
from config import settings


def _is_video_message(message: Message) -> bool:
    """True if message contains processable video content."""
    if message.video:
        return True
    if message.document and message.document.mime_type and \
            message.document.mime_type.startswith("video/"):
        return True
    return False


def _is_url_message(message: Message) -> bool:
    if not message.text:
        return False
    text = message.text.strip()
    return text.startswith("http") and (
        "youtube.com" in text or "youtu.be" in text or
        any(text.lower().endswith(ext) for ext in (".mp4", ".mkv", ".mov", ".webm", ".avi"))
    )


async def _enqueue(client: Client, message: Message) -> None:
    user = message.from_user
    if not user:
        return

    # Check ban
    async with AsyncSessionLocal() as session:
        db_user = await UserRepo(session).get_or_create(
            user.id, user.username, user.first_name
        )
        await session.commit()
        if db_user.is_banned:
            await message.reply_text("🚫 You are banned from using this bot.")
            return

    # Validate file size for direct uploads
    if message.video and message.video.file_size > settings.max_file_size_bytes:
        await message.reply_text(
            f"❌ File too large: **{format_size(message.video.file_size)}**\n"
            f"Maximum allowed: **{settings.max_file_size_mb} MB**"
        )
        return

    # Create DB job record
    source_type = "telegram"
    source_info = None
    if message.text:
        source_type = "youtube" if ("youtube" in message.text or "youtu.be" in message.text) else "url"
        source_info = message.text.strip()

    async with AsyncSessionLocal() as session:
        job_repo = JobRepo(session)
        job = await job_repo.create(
            user_id=user.id,
            source_type=source_type,
            source_info=source_info,
        )
        await session.commit()
        job_id = job.id

    # Send status message
    queue_pos = job_queue.queue_size + 1
    status_msg = await message.reply_text(
        f"⏳ **Job queued** (position `{queue_pos}`)\n"
        f"Job ID: `{job_id}`\n\n"
        "Processing will begin shortly…",
        reply_markup=cancel_kb(job_id),
    )

    cancel_event = asyncio.Event()

    async def job_coro() -> None:
        await process_job(
            client=client,
            source_msg=message,
            status_msg=status_msg,
            job_id=job_id,
            cancel_event=cancel_event,
            user_id=user.id,
        )

    queued_job = QueuedJob(
        job_id=job_id,
        user_id=user.id,
        coro_factory=job_coro,
        cancel_event=cancel_event,
    )
    await job_queue.enqueue(queued_job)
    logger.info(f"Job {job_id} queued for user {user.id}")


# ── Register handlers ──────────────────────────────────────────────────────────

@Client.on_message(filters.private & filters.video)
async def handle_video(client: Client, message: Message) -> None:
    await _enqueue(client, message)


@Client.on_message(filters.private & filters.document)
async def handle_document(client: Client, message: Message) -> None:
    if _is_video_message(message):
        await _enqueue(client, message)


@Client.on_message(filters.private & filters.text)
async def handle_text_url(client: Client, message: Message) -> None:
    if message.text and not message.text.startswith("/"):
        if _is_url_message(message):
            await _enqueue(client, message)
