"""
bot/core/cleanup.py
Periodic background task that removes stale temp directories.
"""
from __future__ import annotations

import asyncio
import shutil
import time

from bot.utils.logger import logger
from config import settings

MAX_AGE_SECONDS = 3600 * 2   # Remove temp dirs older than 2 hours


async def cleanup_loop() -> None:
    """Runs forever, sweeping temp directory every CLEANUP_INTERVAL seconds."""
    logger.info(f"Cleanup loop started (interval={settings.cleanup_interval}s)")
    while True:
        await asyncio.sleep(settings.cleanup_interval)
        await _sweep()


async def _sweep() -> None:
    now = time.time()
    removed = 0
    total_freed = 0
    try:
        for entry in settings.temp_directory.iterdir():
            if not entry.is_dir():
                continue
            age = now - entry.stat().st_mtime
            if age > MAX_AGE_SECONDS:
                size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
                shutil.rmtree(entry, ignore_errors=True)
                removed += 1
                total_freed += size
    except Exception as e:
        logger.warning(f"Cleanup sweep error: {e}")
    if removed:
        logger.info(f"Cleanup: removed {removed} dirs, freed {total_freed / 1e6:.1f} MB")
