"""
bot/core/processor.py
Orchestrates the full pipeline for a single video job:
  download → probe → split → generate thumbnails → upload → cleanup
"""
from __future__ import annotations

import asyncio
import shutil
import time
from pathlib import Path
from typing import Optional

from pyrogram import Client
from pyrogram.types import Message

from bot.core.database import AsyncSessionLocal, JobRepo, UserRepo
from bot.utils.downloader import download_url, download_youtube, classify_input
from bot.utils.ffmpeg import (
    WatermarkOptions, generate_thumbnail, probe, split_video
)
from bot.utils.logger import logger
from bot.utils.ui import format_progress, format_size
from bot.utils.uploader import upload_clips
from config import settings


async def _edit_safe(msg: Message, text: str) -> None:
    """Edit message silently – ignore errors (e.g. message not modified)."""
    try:
        await msg.edit_text(text, parse_mode="markdown")
    except Exception:
        pass


async def process_job(
    client: Client,
    source_msg: Message,       # original message with video / text
    status_msg: Message,       # bot's status message to edit
    job_id: int,
    cancel_event: asyncio.Event,
    user_id: int,
) -> None:
    """Full processing pipeline."""
    start_time = time.time()
    work_dir: Optional[Path] = None

    async with AsyncSessionLocal() as session:
        job_repo = JobRepo(session)
        user_repo = UserRepo(session)
        user = await user_repo.get_settings(user_id)
        clip_length = user.clip_length if user else 10
        output_format = user.output_format if user else "mp4"
        watermark_enabled = user.watermark_enabled if user else False
        thumbnail_enabled = user.thumbnail_enabled if user else True
        zip_output = user.zip_output if user else False
        watermark_text = user.watermark_text if user else None

        await job_repo.update(job_id, status="processing")
        await session.commit()

    try:
        # ── 1. Download ───────────────────────────────────────────────────
        await _edit_safe(status_msg, "⬇️ **Downloading…**\nPlease wait.")
        if cancel_event.is_set():
            raise asyncio.CancelledError()

        source_path: Path

        if source_msg.video or source_msg.document:
            media = source_msg.video or source_msg.document
            # Validate size
            if media.file_size > settings.max_file_size_bytes:
                raise ValueError(
                    f"File too large: {format_size(media.file_size)} "
                    f"(max {settings.max_file_size_mb} MB)"
                )
            work_dir = settings.temp_directory / str(job_id)
            work_dir.mkdir(parents=True, exist_ok=True)
            dest = work_dir / (media.file_name or f"video_{job_id}.mp4")

            last_edit = [0.0]

            async def tg_progress(current: int, total: int) -> None:
                now = time.time()
                if now - last_edit[0] > 2:
                    last_edit[0] = now
                    txt = format_progress("⬇️ Downloading", current, total,
                                         f"{format_size(current)} / {format_size(total)}")
                    await _edit_safe(status_msg, txt)

            source_path = Path(
                await client.download_media(media, file_name=str(dest), progress=tg_progress)
            )

        elif source_msg.text:
            url = source_msg.text.strip()
            kind = classify_input(url)
            if kind == "youtube":
                await _edit_safe(status_msg, "🎬 **Downloading from YouTube…**")
                source_path = await download_youtube(url)
            elif kind == "url":
                last_edit = [0.0]

                def url_progress(done: int, total: int) -> None:
                    pass  # async edit not available in sync cb; status shown once

                source_path = await download_url(url, url_progress)
            else:
                raise ValueError("Please send a video file, forward a video, or paste a direct MP4/YouTube URL.")
            work_dir = source_path.parent
        else:
            raise ValueError("Unsupported input. Send a video or a URL.")

        if cancel_event.is_set():
            raise asyncio.CancelledError()

        # ── 2. Probe ──────────────────────────────────────────────────────
        await _edit_safe(status_msg, "🔍 **Analysing video…**")
        info = await probe(source_path)
        logger.bind(processing=True).info(
            f"Job {job_id} | {info.duration:.1f}s | "
            f"{info.width}x{info.height} | {info.video_codec}/{info.audio_codec}"
        )

        async with AsyncSessionLocal() as session:
            job_repo = JobRepo(session)
            await job_repo.update(
                job_id,
                duration=info.duration,
                file_size=info.file_size,
            )
            await session.commit()

        # ── 3. Split ──────────────────────────────────────────────────────
        clips_dir = work_dir / "clips"
        clips_dir.mkdir(exist_ok=True)

        wm: Optional[WatermarkOptions] = None
        if watermark_enabled:
            wm = WatermarkOptions(
                text=watermark_text or f"@{source_msg.from_user.username or 'clip'}",
                image_path=settings.watermark_image,
                position="bottomright",
                opacity=0.7,
            )

        last_split_edit = [0.0]

        def split_progress(done: int, total: int) -> None:
            pass  # called from sync context inside asyncio thread

        await _edit_safe(
            status_msg,
            f"✂️ **Splitting into clips…**\n"
            f"Duration: `{info.duration:.0f}s` | Clip length: `{clip_length}s`"
        )

        clips = await split_video(
            source=source_path,
            output_dir=clips_dir,
            clip_length=clip_length,
            output_format=output_format,
            watermark=wm,
        )

        if not clips:
            raise RuntimeError("No clips were produced.")

        if cancel_event.is_set():
            raise asyncio.CancelledError()

        # ── 4. Thumbnail ──────────────────────────────────────────────────
        thumb_path: Optional[Path] = None
        if thumbnail_enabled:
            try:
                thumb_path = work_dir / "thumb.jpg"
                await generate_thumbnail(source_path, thumb_path)
            except Exception as e:
                logger.warning(f"Thumbnail failed: {e}")
                thumb_path = None

        # ── 5. Upload ─────────────────────────────────────────────────────
        upload_total = [len(clips)]
        last_up_edit = [0.0]

        async def upload_progress(done: int, total: int) -> None:
            now = time.time()
            if now - last_up_edit[0] > 3:
                last_up_edit[0] = now
                txt = format_progress("📤 Uploading", done, total,
                                      f"Clip {done}/{total}")
                await _edit_safe(status_msg, txt)

        await _edit_safe(status_msg, f"📤 **Uploading {len(clips)} clips…**")
        await upload_clips(
            client=client,
            chat_id=source_msg.chat.id,
            clips=clips,
            thumb=thumb_path,
            as_zip=zip_output,
            progress_cb=lambda d, t: asyncio.ensure_future(upload_progress(d, t)),
        )

        # ── 6. Complete ───────────────────────────────────────────────────
        elapsed = time.time() - start_time
        async with AsyncSessionLocal() as session:
            job_repo = JobRepo(session)
            await job_repo.record_completion(job_id, len(clips), elapsed)
            await session.commit()

        summary = (
            f"✅ **Done!**\n\n"
            f"📹 Video: `{info.duration:.0f}s` | `{info.width}×{info.height}`\n"
            f"✂️ Clips: `{len(clips)}` × `{clip_length}s`\n"
            f"⏱ Time: `{elapsed:.1f}s`"
        )
        await _edit_safe(status_msg, summary)

    except asyncio.CancelledError:
        await _edit_safe(status_msg, "🛑 **Job cancelled.**")
        async with AsyncSessionLocal() as session:
            await JobRepo(session).update(job_id, status="cancelled")
            await session.commit()

    except ValueError as e:
        await _edit_safe(status_msg, f"⚠️ **Error:** {e}")
        async with AsyncSessionLocal() as session:
            await JobRepo(session).update(job_id, status="failed", error_message=str(e))
            await session.commit()

    except Exception as e:
        logger.exception(f"Job {job_id} failed: {e}")
        await _edit_safe(status_msg, f"❌ **Processing failed.**\n`{type(e).__name__}: {str(e)[:200]}`")
        async with AsyncSessionLocal() as session:
            await JobRepo(session).update(job_id, status="failed", error_message=str(e))
            await session.commit()

    finally:
        # ── 7. Cleanup ────────────────────────────────────────────────────
        if work_dir and work_dir.exists():
            try:
                shutil.rmtree(work_dir)
                logger.debug(f"Cleaned up {work_dir}")
            except Exception as e:
                logger.warning(f"Cleanup failed for {work_dir}: {e}")
