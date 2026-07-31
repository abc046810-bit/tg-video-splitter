"""Download media using Pyrogram MTProto client."""

import asyncio
import logging
from pathlib import Path

from pyrogram import Client
from telegram import Message

from progress import ProgressTracker

logger = logging.getLogger(__name__)


async def download_video(
    client: Client,
    message: Message,
    dest_path: Path,
    status_msg,
) -> Path:
    """Download a video/document via Pyrogram with progress updates.

    Supports files up to 2 GB via MTProto.
    """
    video = message.video or message.document
    if not video:
        raise ValueError("Message contains no downloadable media")

    file_id = video.file_id
    file_size = getattr(video, "file_size", 0) or 0

    logger.info("Download started: %s (%s bytes)", file_id[:20], file_size)

    tracker = ProgressTracker(file_size, "Downloading...")
    state = {"current": 0}

    def sync_progress(current: int, total: int):
        state["current"] = current

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    task = asyncio.create_task(
        client.download_media(
            file_id,
            file_name=str(dest_path),
            progress=sync_progress,
        )
    )

    last_text = ""
    while not task.done():
        await asyncio.sleep(3)
        text = tracker.update(state["current"])
        if text != last_text:
            try:
                await status_msg.edit_text(text)
                last_text = text
            except Exception:
                pass

    result = await task
    if not result:
        raise RuntimeError("Download failed: Pyrogram returned None")

    final_path = Path(result)
    logger.info("Download finished: %s", final_path)
    return final_path
  
