"""Video Tool Bot - Main entry point.

Initializes the Telegram bot application, configures logging,
starts a health server for Render compatibility, and runs polling.
"""

import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import Application

import config
from handlers import setup_handlers


def setup_logging() -> None:
    """Configure application logging to file and stdout."""
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # File handler
    file_handler = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(config.LOG_LEVEL)

    # Stream handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(config.LOG_LEVEL)

    root_logger = logging.getLogger()
    root_logger.setLevel(config.LOG_LEVEL)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)


class _HealthHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for Render health checks."""

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, fmt: str, *args) -> None:
        # Suppress default HTTP server logging
        pass


def _start_health_server(port: int) -> HTTPServer:
    """Start a background HTTP server for health checks."""
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def main() -> None:
    """Run the bot."""
    setup_logging()
    logger = logging.getLogger(__name__)

    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN is not set. Exiting.")
        sys.exit(1)
    if config.OWNER_ID == 0:
        logger.error("OWNER_ID is not set. Exiting.")
        sys.exit(1)

    logger.info("Starting Video Tool Bot...")

    # Start health server if PORT is set (Render deployment)
    port = os.getenv("PORT")
    if port:
        try:
            health_port = int(port)
            _start_health_server(health_port)
            logger.info("Health server started on port %d", health_port)
        except ValueError:
            logger.warning("Invalid PORT value: %s", port)

    application = Application.builder().token(config.BOT_TOKEN).build()
    setup_handlers(application)

    logger.info("Bot is polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
