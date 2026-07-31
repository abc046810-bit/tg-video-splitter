"""Video Tool Bot - Main entry point.

Runs PTB for command handling and Pyrogram for MTProto file transfers.
"""

import asyncio
import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import Application
from telegram.error import Conflict

from pyrogram import Client

import config
from handlers import setup_handlers


def setup_logging() -> None:
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    file_handler = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(config.LOG_LEVEL)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)


class _HealthHandler(BaseHTTPRequestHandler):
    """Minimal health check responder for Render."""

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, fmt: str, *args) -> None:
        pass


def _start_health_server(port: int) -> None:
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logging.getLogger(__name__).info("Health server on port %d", port)


async def _error_handler(update, context) -> None:
    logger = logging.getLogger(__name__)
    logger.error("Exception:", exc_info=context.error)

    if isinstance(context.error, Conflict):
        logger.critical(
            "Conflict: another bot instance is running. Shutting down."
        )
        os._exit(1)

    if update and isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "An error occurred. Use /cancel to reset."
            )
        except Exception:
            pass


async def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)

    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN missing. Exiting.")
        sys.exit(1)
    if config.OWNER_ID == 0:
        logger.error("OWNER_ID missing. Exiting.")
        sys.exit(1)
    if not config.API_ID or not config.API_HASH:
        logger.error("API_ID or API_HASH missing. Exiting.")
        sys.exit(1)

    # Render health server
    port = os.getenv("PORT")
    if port:
        try:
            _start_health_server(int(port))
        except Exception as exc:
            logger.warning("Health server error: %s", exc)

    # Pyrogram MTProto client (no_updates=True because PTB handles updates)
    pyro_client = Client(
        "bot_session",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        workdir="/tmp",
        no_updates=True,
    )
    await pyro_client.start()
    logger.info("Pyrogram client started")

    # PTB Application
    application = Application.builder().token(config.BOT_TOKEN).build()
    application.bot_data["pyro_client"] = pyro_client

    # Remove any existing webhook and drop pending updates
    await application.bot.delete_webhook(drop_pending_updates=True)
    logger.info("Webhook deleted, pending updates dropped")

    setup_handlers(application)
    application.add_error_handler(_error_handler)

    # Start polling manually so we can control shutdown
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    logger.info("Polling started")

    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Shutdown signal received")
    finally:
        await application.updater.stop()
        await application.stop()
        await pyro_client.stop()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.getLogger(__name__).info("Exited")
