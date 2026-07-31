"""Upload clips using Pyrogram MTProto client."""

import asyncio
import logging
from pathlib import Path
from typing import List

from pyrogram import Client

from progress import ProgressTracker

logger = logging.getLogger(__name__)


async def upload_clips(
    client: Client,
    chat_id: int,
    clips: List[Path],
    status_msg,
    caption_prefix: str = "Part",
) -> None:
    """Upload video clips with progress updates."""
    total = len(clips)

    for idx, clip_path in enumerate(clips, 1):
        file_size = clip_path.stat().st_size
        tracker = ProgressTracker(
            file_size,
            f"Uploading {caption_prefix} {idx}/{total}...",
        )
        state = {"current": 0}

        def sync_progress(current: int, total_bytes: int):
            state["current"] = current

        caption = f"{caption_prefix} {idx}/{total}"

        task = asyncio.create_task(
            client.send_video(
                chat_id=chat_id,
                video=str(clip_path),
                caption=caption,
                supports_streaming=True,
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

        await task
        logger.info("Uploaded %s", clip_path.name)
      
