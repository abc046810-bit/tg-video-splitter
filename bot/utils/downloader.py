"""
bot/utils/downloader.py
Unified downloader: Telegram media, direct HTTP URLs, YouTube via yt-dlp.
"""
from __future__ import annotations

import asyncio
import re
import uuid
from pathlib import Path
from typing import Callable, Optional

import aiohttp

from bot.utils.logger import logger
from config import settings

ProgressCallback = Callable[[int, int], None]  # (bytes_done, total_bytes)

YOUTUBE_PATTERN = re.compile(
    r"(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[\w-]+"
)
DIRECT_URL_PATTERN = re.compile(r"https?://\S+\.(mp4|mkv|mov|avi|webm)", re.IGNORECASE)


def _work_dir() -> Path:
    """Return a unique temp subdirectory."""
    d = settings.temp_directory / str(uuid.uuid4())
    d.mkdir(parents=True, exist_ok=True)
    return d


async def download_url(url: str, progress_cb: Optional[ProgressCallback] = None) -> Path:
    """Download a direct HTTP(S) URL to a temp file."""
    dest_dir = _work_dir()
    # Derive filename from URL
    filename = url.split("?")[0].rsplit("/", 1)[-1] or "video.mp4"
    dest = dest_dir / filename

    timeout = aiohttp.ClientTimeout(total=3600, connect=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status} for URL: {url}")

            total = int(resp.headers.get("Content-Length", 0))
            if total and total > settings.max_file_size_bytes:
                raise ValueError(
                    f"File too large ({total / 1024 / 1024:.1f} MB > "
                    f"{settings.max_file_size_mb} MB limit)"
                )

            done = 0
            with dest.open("wb") as fh:
                async for chunk in resp.content.iter_chunked(1 << 20):  # 1 MB chunks
                    fh.write(chunk)
                    done += len(chunk)
                    if progress_cb:
                        progress_cb(done, total)

    logger.bind(processing=True).info(f"Downloaded URL → {dest} ({dest.stat().st_size / 1e6:.1f} MB)")
    return dest


async def download_youtube(url: str, progress_cb: Optional[ProgressCallback] = None) -> Path:
    """Download YouTube video via yt-dlp subprocess."""
    if not settings.enable_youtube:
        raise RuntimeError("YouTube support is disabled in settings.")

    dest_dir = _work_dir()
    out_template = str(dest_dir / "%(title)s.%(ext)s")

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--merge-output-format", "mp4",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "-o", out_template,
        "--newline",
        url,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Parse yt-dlp progress output
    while True:
        line = await proc.stdout.readline()  # type: ignore[union-attr]
        if not line:
            break
        decoded = line.decode(errors="replace").strip()
        if "[download]" in decoded and "%" in decoded:
            try:
                pct = float(decoded.split("%")[0].split()[-1])
                if progress_cb:
                    progress_cb(int(pct), 100)
            except (ValueError, IndexError):
                pass

    await proc.wait()
    if proc.returncode != 0:
        stderr = (await proc.stderr.read()).decode(errors="replace")  # type: ignore[union-attr]
        raise RuntimeError(f"yt-dlp failed: {stderr[-400:]}")

    # Find the downloaded file
    files = list(dest_dir.glob("*.mp4"))
    if not files:
        files = list(dest_dir.iterdir())
    if not files:
        raise RuntimeError("yt-dlp produced no output file.")

    result = max(files, key=lambda f: f.stat().st_size)
    logger.bind(processing=True).info(f"YouTube download → {result}")
    return result


def classify_input(text: str) -> str:
    """Return 'youtube', 'url', or 'unknown'."""
    if YOUTUBE_PATTERN.search(text):
        return "youtube"
    if DIRECT_URL_PATTERN.search(text):
        return "url"
    return "unknown"
