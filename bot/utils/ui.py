"""
bot/utils/ui.py
Reusable Telegram UI components: inline keyboards, progress formatters.
"""
from __future__ import annotations

import math
from typing import Optional

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ── Progress bar ───────────────────────────────────────────────────────────────

BAR_LEN = 10

def progress_bar(current: int, total: int) -> str:
    if total <= 0:
        return "░" * BAR_LEN
    filled = math.floor((current / total) * BAR_LEN)
    return "█" * filled + "░" * (BAR_LEN - filled)


def format_progress(stage: str, current: int, total: int, extra: str = "") -> str:
    pct = int((current / total) * 100) if total > 0 else 0
    bar = progress_bar(current, total)
    line = f"**{stage}**\n`[{bar}]` {pct}% ({current}/{total})"
    if extra:
        line += f"\n{extra}"
    return line


def format_size(bytes_: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if bytes_ < 1024:
            return f"{bytes_:.1f} {unit}"
        bytes_ //= 1024  # type: ignore[assignment]
    return f"{bytes_:.1f} TB"


# ── Settings keyboards ─────────────────────────────────────────────────────────

CLIP_LENGTHS = [5, 10, 15, 30, 60]
FORMATS = ["mp4", "mkv"]
WM_POSITIONS = ["topleft", "topright", "bottomleft", "bottomright", "center"]


def settings_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏱ Clip Length", callback_data="set_clip_length")],
        [InlineKeyboardButton("📁 Output Format", callback_data="set_format")],
        [InlineKeyboardButton("💧 Watermark", callback_data="set_watermark")],
        [InlineKeyboardButton("🖼 Thumbnail", callback_data="set_thumbnail")],
        [InlineKeyboardButton("📦 ZIP Output", callback_data="set_zip")],
        [InlineKeyboardButton("🔍 Keep Resolution", callback_data="set_resolution")],
        [InlineKeyboardButton("❌ Close", callback_data="close_settings")],
    ])


def clip_length_kb(current: int) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            f"{'✅ ' if v == current else ''}{v}s",
            callback_data=f"clip_len_{v}",
        )
        for v in CLIP_LENGTHS
    ]
    rows = [buttons[i:i+3] for i in range(0, len(buttons), 3)]
    rows.append([InlineKeyboardButton("⬅ Back", callback_data="back_settings")])
    return InlineKeyboardMarkup(rows)


def format_kb(current: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"{'✅ ' if fmt == current else ''}{fmt.upper()}",
                callback_data=f"fmt_{fmt}",
            )
            for fmt in FORMATS
        ],
        [InlineKeyboardButton("⬅ Back", callback_data="back_settings")],
    ])


def toggle_kb(feature: str, enabled: bool) -> InlineKeyboardMarkup:
    label = "✅ ON" if enabled else "❌ OFF"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"toggle_{feature}")],
        [InlineKeyboardButton("⬅ Back", callback_data="back_settings")],
    ])


def cancel_kb(job_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛑 Cancel", callback_data=f"cancel_job_{job_id}")]
    ])
