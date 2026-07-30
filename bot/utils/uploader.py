"""
bot/utils/uploader.py
Upload clips to Telegram with progress, optional ZIP packing,
and Telegram FloodWait handling.
"""
from __future__ import annotations

import asyncio
import time
import zipfile
from pathlib import Path
from typing import Callable, List, Optional

from pyrogram import Client
from pyrogram.errors import FloodWait

from bot.utils.logger import logger


async def _safe_send_video(
    client: Client,
    chat_id: int,
    path: Path,
    caption: str = "",
    thumb: Optional[Path] = None,
    retries: int = 5,
) -> None:
    """Send a video file, retrying on FloodWait."""
    for attempt in range(retries):
        try:
            kwargs: dict = {
                "chat_id": chat_id,
                "video": str(path),
                "caption": caption,
                "supports_streaming": True,
            }
            if thumb and thumb.exists():
                kwargs["thumb"] = str(thumb)
            await client.send_video(**kwargs)
            return
        except FloodWait as e:
            wait = e.value + 2
            logger.warning(f"FloodWait {wait}s (attempt {attempt + 1}/{retries})")
            await asyncio.sleep(wait)
        except Exception as exc:
            if attempt == retries - 1:
                raise
            logger.warning(f"Upload error (retry {attempt + 1}): {exc}")
            await asyncio.sleep(3 * (attempt + 1))


async def upload_clips(
    client: Client,
    chat_id: int,
    clips: List[Path],
    thumb: Optional[Path] = None,
    as_zip: bool = False,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> None:
    """Upload clips either individually or as a single ZIP."""
    if as_zip:
        zip_path = clips[0].parent / "clips.zip"
        _build_zip(clips, zip_path)
        logger.bind(processing=True).info(f"Uploading ZIP → {chat_id}")
        await _safe_send_document(client, chat_id, zip_path, caption="📦 All clips")
        if progress_cb:
            progress_cb(len(clips), len(clips))
    else:
        total = len(clips)
        for i, clip in enumerate(clips, 1):
            caption = f"📹 Clip {i}/{total} — {clip.name}"
            await _safe_send_video(client, chat_id, clip, caption=caption, thumb=thumb)
            if progress_cb:
                progress_cb(i, total)
            # Small delay to avoid hammering the API
            await asyncio.sleep(0.4)


async def _safe_send_document(
    client: Client,
    chat_id: int,
    path: Path,
    caption: str = "",
    retries: int = 5,
) -> None:
    for attempt in range(retries):
        try:
            await client.send_document(chat_id=chat_id, document=str(path), caption=caption)
            return
        except FloodWait as e:
            await asyncio.sleep(e.value + 2)
        except Exception as exc:
            if attempt == retries - 1:
                raise
            await asyncio.sleep(3 * (attempt + 1))


def _build_zip(clips: List[Path], dest: Path) -> None:
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
        for clip in clips:
            zf.write(clip, clip.name)
    logger.debug(f"ZIP created: {dest} ({dest.stat().st_size / 1e6:.1f} MB)")
