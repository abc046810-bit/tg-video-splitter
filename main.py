"""
main.py
Application entry point — creates the Pyrogram client, loads handlers,
starts the job queue and background tasks.
"""
from __future__ import annotations

import asyncio
import importlib

from pyrogram import Client

from bot.core.cleanup import cleanup_loop
from bot.core.database import init_db
from bot.core.queue import job_queue
from bot.utils.ffmpeg import ffmpeg_available
from bot.utils.logger import logger
from config import settings

# ── Handler modules to load ────────────────────────────────────────────────────
HANDLER_MODULES = [
    "bot.handlers.commands",
    "bot.handlers.settings",
    "bot.handlers.video",
    "bot.handlers.admin",
]


def load_handlers() -> None:
    for module in HANDLER_MODULES:
        importlib.import_module(module)
        logger.debug(f"Loaded handler module: {module}")


async def main() -> None:
    # Pre-flight checks
    if not ffmpeg_available():
        logger.error("FFmpeg or ffprobe is not installed / not on PATH. Aborting.")
        return

    logger.info("Initialising database…")
    await init_db()

    logger.info("Loading handler modules…")
    load_handlers()

    # Create Pyrogram client
    app = Client(
        name="video_splitter_bot",
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        bot_token=settings.bot_token,
        workers=8,
    )

    async with app:
        me = await app.get_me()
        logger.info(f"Bot started as @{me.username} (ID: {me.id})")

        # Start job queue
        job_queue.start()

        # Start background cleanup loop
        cleanup_task = asyncio.create_task(cleanup_loop(), name="cleanup_loop")

        # Notify log channel if configured
        if settings.log_channel:
            try:
                await app.send_message(settings.log_channel, f"✅ Bot started: @{me.username}")
            except Exception:
                pass

        logger.info("Bot is running. Press Ctrl+C to stop.")

        try:
            await asyncio.Event().wait()   # Keep running
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        finally:
            cleanup_task.cancel()
            await job_queue.stop()
            if settings.log_channel:
                try:
                    await app.send_message(settings.log_channel, "🔴 Bot stopped.")
                except Exception:
                    pass
            logger.info("Bot shut down gracefully.")


if __name__ == "__main__":
    asyncio.run(main())
