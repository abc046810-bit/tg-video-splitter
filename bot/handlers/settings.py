"""
bot/handlers/settings.py
/settings command + inline keyboard callbacks for user preferences.
"""
from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from bot.core.database import AsyncSessionLocal, UserRepo
from bot.utils.logger import logger
from bot.utils.ui import (
    clip_length_kb, format_kb, settings_main_kb, toggle_kb
)


async def _get_settings_text(user_id: int) -> str:
    async with AsyncSessionLocal() as session:
        user = await UserRepo(session).get_settings(user_id)
    if not user:
        return "Settings not found."
    return (
        "⚙️ **Your Settings**\n\n"
        f"⏱ Clip length: `{user.clip_length}s`\n"
        f"📁 Format: `{user.output_format.upper()}`\n"
        f"💧 Watermark: `{'ON' if user.watermark_enabled else 'OFF'}`"
        + (f" — `{user.watermark_text}`" if user.watermark_text else "") + "\n"
        f"🖼 Thumbnail: `{'ON' if user.thumbnail_enabled else 'OFF'}`\n"
        f"📦 ZIP output: `{'ON' if user.zip_output else 'OFF'}`\n"
        f"🔍 Keep resolution: `{'ON' if user.keep_resolution else 'OFF'}`"
    )


@Client.on_message(filters.command("settings") & filters.private)
async def cmd_settings(client: Client, message: Message) -> None:
    text = await _get_settings_text(message.from_user.id)
    await message.reply_text(text, reply_markup=settings_main_kb())


# ── Callback handlers ──────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^set_clip_length$"))
async def cb_set_clip_length(client: Client, query: CallbackQuery) -> None:
    async with AsyncSessionLocal() as session:
        user = await UserRepo(session).get_settings(query.from_user.id)
        current = user.clip_length if user else 10
    await query.edit_message_text(
        "⏱ **Choose clip length:**", reply_markup=clip_length_kb(current)
    )


@Client.on_callback_query(filters.regex(r"^clip_len_(\d+)$"))
async def cb_clip_len_choice(client: Client, query: CallbackQuery) -> None:
    length = int(query.matches[0].group(1))
    async with AsyncSessionLocal() as session:
        repo = UserRepo(session)
        await repo.update_settings(query.from_user.id, clip_length=length)
        await session.commit()
    await query.answer(f"Clip length set to {length}s")
    text = await _get_settings_text(query.from_user.id)
    await query.edit_message_text(text, reply_markup=settings_main_kb())


@Client.on_callback_query(filters.regex(r"^set_format$"))
async def cb_set_format(client: Client, query: CallbackQuery) -> None:
    async with AsyncSessionLocal() as session:
        user = await UserRepo(session).get_settings(query.from_user.id)
        current = user.output_format if user else "mp4"
    await query.edit_message_text(
        "📁 **Choose output format:**", reply_markup=format_kb(current)
    )


@Client.on_callback_query(filters.regex(r"^fmt_(\w+)$"))
async def cb_fmt_choice(client: Client, query: CallbackQuery) -> None:
    fmt = query.matches[0].group(1)
    async with AsyncSessionLocal() as session:
        repo = UserRepo(session)
        await repo.update_settings(query.from_user.id, output_format=fmt)
        await session.commit()
    await query.answer(f"Format set to {fmt.upper()}")
    text = await _get_settings_text(query.from_user.id)
    await query.edit_message_text(text, reply_markup=settings_main_kb())


@Client.on_callback_query(filters.regex(r"^set_(watermark|thumbnail|zip|resolution)$"))
async def cb_set_toggle(client: Client, query: CallbackQuery) -> None:
    feature = query.matches[0].group(1)
    field_map = {
        "watermark": "watermark_enabled",
        "thumbnail": "thumbnail_enabled",
        "zip": "zip_output",
        "resolution": "keep_resolution",
    }
    db_field = field_map[feature]
    async with AsyncSessionLocal() as session:
        user = await UserRepo(session).get_settings(query.from_user.id)
        current = getattr(user, db_field, False) if user else False

    label = feature.replace("_", " ").title()
    await query.edit_message_text(
        f"{'💧' if feature == 'watermark' else '🖼' if feature == 'thumbnail' else '📦' if feature == 'zip' else '🔍'} "
        f"**{label}**",
        reply_markup=toggle_kb(feature, current),
    )


@Client.on_callback_query(filters.regex(r"^toggle_(\w+)$"))
async def cb_toggle(client: Client, query: CallbackQuery) -> None:
    feature = query.matches[0].group(1)
    field_map = {
        "watermark": "watermark_enabled",
        "thumbnail": "thumbnail_enabled",
        "zip": "zip_output",
        "resolution": "keep_resolution",
    }
    db_field = field_map.get(feature)
    if not db_field:
        await query.answer("Unknown setting")
        return

    async with AsyncSessionLocal() as session:
        repo = UserRepo(session)
        user = await repo.get_settings(query.from_user.id)
        new_val = not (getattr(user, db_field, False) if user else False)
        await repo.update_settings(query.from_user.id, **{db_field: new_val})
        await session.commit()

    await query.answer(f"{'ON' if new_val else 'OFF'}")
    label = feature.replace("_", " ").title()
    await query.edit_message_text(
        f"Setting updated!",
        reply_markup=toggle_kb(feature, new_val),
    )


@Client.on_callback_query(filters.regex(r"^back_settings$"))
async def cb_back_settings(client: Client, query: CallbackQuery) -> None:
    text = await _get_settings_text(query.from_user.id)
    await query.edit_message_text(text, reply_markup=settings_main_kb())


@Client.on_callback_query(filters.regex(r"^close_settings$"))
async def cb_close_settings(client: Client, query: CallbackQuery) -> None:
    await query.message.delete()


@Client.on_callback_query(filters.regex(r"^cancel_job_(\d+)$"))
async def cb_cancel_job(client: Client, query: CallbackQuery) -> None:
    from bot.core.queue import job_queue
    job_id = int(query.matches[0].group(1))
    cancelled = job_queue.cancel(job_id)
    if cancelled:
        await query.answer("🛑 Cancellation requested")
    else:
        await query.answer("Job not found or already completed")
