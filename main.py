"""
main.py
Application entry point — creates the Pyrogram client, loads handlers,
starts the job queue and background tasks.
Also starts a tiny HTTP server so Render Web Service detects a port.
"""
from __future__ import annotations

import asyncio
import importlib
import os
from aiohttp import web, ClientSession

from pyrogram import Client

from bot.core.cleanup import cleanup_loop
from bot.core.database import init_db
from bot.core.queue import job_queue
from bot.utils.ffmpeg import ffmpeg_available
from bot.utils.logger import logger
from config import settings

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


async def health_handler(request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def start_health_server() -> web.AppRunner:
    """Tiny HTTP server so Render / Railway detect an open port."""
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)

    port = int(os.getenv("PORT", "10000"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health server listening on 0.0.0.0:{port}")
    return runner


async def clear_telegram_webhook(bot_token: str) -> None:
    """Clear any old Bot API webhook so updates reach the bot."""
    url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook?drop_pending_updates=true"
    try:
        async with ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                logger.info(f"Webhook clear result: {data}")
    except Exception as e:
        logger.warning(f"Could not clear webhook: {e}")


async def main() -> None:
    if not ffmpeg_available():
        logger.error("FFmpeg or ffprobe is not installed / not on PATH. Aborting.")
        return

    logger.info("Initialising database…")
    await init_db()

    logger.info("Loading handler modules…")
    load_handlers()

    # Health server (for Render Web Service)
    health_runner = await start_health_server()

    # Clear old webhook (Bot API)
    await clear_telegram_webhook(settings.bot_token)

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

        job_queue.start()
        cleanup_task = asyncio.create_task(cleanup_loop(), name="cleanup_loop")

        if settings.log_channel:
            try:
                await app.send_message(settings.log_channel, f"✅ Bot started: @{me.username}")
            except Exception:
                pass

        logger.info("Bot is running. Press Ctrl+C to stop.")

        try:
            await asyncio.Event().wait()
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        finally:
            cleanup_task.cancel()
            await job_queue.stop()
            await health_runner.cleanup()
            if settings.log_channel:
                try:
                    await app.send_message(settings.log_channel, "🔴 Bot stopped.")
                except Exception:
                    pass
            logger.info("Bot shut down gracefully.")


if __name__ == "__main__":
    asyncio.run(main())
