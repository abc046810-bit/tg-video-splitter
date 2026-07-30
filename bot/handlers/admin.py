"""
bot/handlers/admin.py
Owner-only admin commands: /admin, /stats, /broadcast, /ban, /unban.
"""
from __future__ import annotations

import asyncio
import datetime
import os
import shutil

import psutil
from pyrogram import Client, filters
from pyrogram.types import Message

from bot.core.database import AsyncSessionLocal, BotStats, JobRepo, UserRepo
from bot.core.queue import job_queue
from bot.utils.logger import logger
from config import settings


def admin_only(func):
    """Decorator: restricts handler to admins."""
    async def wrapper(client: Client, message: Message):
        if not settings.is_admin(message.from_user.id):
            await message.reply_text("🚫 Admin access required.")
            return
        return await func(client, message)
    wrapper.__name__ = func.__name__
    return wrapper


# ── /admin ─────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("admin") & filters.private)
@admin_only
async def cmd_admin(client: Client, message: Message) -> None:
    text = (
        "🛠 **Admin Panel**\n\n"
        "**Commands:**\n"
        "• /stats — Global statistics\n"
        "• /broadcast `<text>` — Broadcast message to all users\n"
        "• /ban `<user_id>` — Ban a user\n"
        "• /unban `<user_id>` — Unban a user\n"
        "• /jobs — Active jobs\n"
        "• /sysinfo — Server resource usage\n"
    )
    await message.reply_text(text)


# ── /stats ─────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("stats") & filters.private)
@admin_only
async def cmd_stats(client: Client, message: Message) -> None:
    async with AsyncSessionLocal() as session:
        stats = await session.get(BotStats, 1)
        user_count = await UserRepo(session).total_count()

    if not stats:
        await message.reply_text("No statistics yet.")
        return

    hours = stats.total_processing_seconds / 3600

    text = (
        "📊 **Global Statistics**\n\n"
        f"👥 Total users: `{user_count:,}`\n"
        f"🎬 Videos processed: `{stats.total_videos:,}`\n"
        f"✂️ Clips generated: `{stats.total_clips:,}`\n"
        f"⏱ Processing time: `{hours:.2f}h`\n\n"
        f"🌐 Queue: `{job_queue.queue_size}` waiting | `{job_queue.active_count}` active"
    )
    await message.reply_text(text)


# ── /sysinfo ───────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("sysinfo") & filters.private)
@admin_only
async def cmd_sysinfo(client: Client, message: Message) -> None:
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(str(settings.temp_directory))

    # Temp dir size
    temp_size = sum(
        f.stat().st_size
        for f in settings.temp_directory.rglob("*")
        if f.is_file()
    )

    text = (
        "🖥 **System Info**\n\n"
        f"CPU: `{cpu:.1f}%`\n"
        f"RAM: `{mem.percent:.1f}%` "
        f"({mem.used // 1024**2} / {mem.total // 1024**2} MB)\n"
        f"Disk: `{disk.percent:.1f}%` "
        f"({disk.used // 1024**3} / {disk.total // 1024**3} GB)\n"
        f"Temp dir: `{temp_size / 1024**2:.1f} MB`"
    )
    await message.reply_text(text)


# ── /jobs ──────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("jobs") & filters.private)
@admin_only
async def cmd_jobs(client: Client, message: Message) -> None:
    active = job_queue.active_count
    pending = job_queue.queue_size
    await message.reply_text(
        f"🔄 **Active Jobs:** `{active}`\n"
        f"⏳ **Pending Jobs:** `{pending}`"
    )


# ── /ban ───────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("ban") & filters.private)
@admin_only
async def cmd_ban(client: Client, message: Message) -> None:
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply_text("Usage: /ban <user_id>")
        return
    target_id = int(parts[1])
    async with AsyncSessionLocal() as session:
        repo = UserRepo(session)
        await repo.update_settings(target_id, is_banned=True)
        await session.commit()
    await message.reply_text(f"✅ User `{target_id}` banned.")
    logger.info(f"Admin {message.from_user.id} banned user {target_id}")


# ── /unban ─────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("unban") & filters.private)
@admin_only
async def cmd_unban(client: Client, message: Message) -> None:
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply_text("Usage: /unban <user_id>")
        return
    target_id = int(parts[1])
    async with AsyncSessionLocal() as session:
        repo = UserRepo(session)
        await repo.update_settings(target_id, is_banned=False)
        await session.commit()
    await message.reply_text(f"✅ User `{target_id}` unbanned.")


# ── /broadcast ─────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("broadcast") & filters.private)
@admin_only
async def cmd_broadcast(client: Client, message: Message) -> None:
    text = message.text.split(None, 1)
    if len(text) < 2:
        await message.reply_text("Usage: /broadcast <message>")
        return

    broadcast_text = text[1]
    status = await message.reply_text("📢 **Broadcasting…**")

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        from bot.core.database import User
        result = await session.execute(
            select(User.id).where(User.is_banned == False)
        )
        user_ids = [row[0] for row in result.fetchall()]

    sent = failed = 0
    for uid in user_ids:
        try:
            await client.send_message(uid, broadcast_text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # Rate limit

    await status.edit_text(
        f"📢 **Broadcast complete**\n"
        f"✅ Sent: `{sent}` | ❌ Failed: `{failed}`"
    )
