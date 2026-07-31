"""Configuration module for Video Tool Bot.

Loads environment variables and exposes application settings.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Bot credentials
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
OWNER_ID: int = int(os.getenv("OWNER_ID", "0"))
API_ID: int = int(os.getenv("API_ID", "0"))
API_HASH: str = os.getenv("API_HASH", "")

# Paths
BASE_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
SPLIT_DIR = BASE_DIR / "split"
MERGE_DIR = BASE_DIR / "merge"
TEMP_DIR = BASE_DIR / "temp"
LOGS_DIR = BASE_DIR / "logs"

# Ensure directories exist
for _dir in (DOWNLOADS_DIR, SPLIT_DIR, MERGE_DIR, TEMP_DIR, LOGS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# Logging
LOG_FILE = LOGS_DIR / "bot.log"
LOG_LEVEL = logging.INFO

# Telegram limits (bytes)
MAX_DOWNLOAD_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB
MAX_UPLOAD_SIZE = 2 * 1024 * 1024 * 1024    # 2 GB

# Supported video extensions
SUPPORTED_FORMATS = {"mp4", "mkv", "avi", "mov", "webm", "m4v"}

# FFmpeg path (assumes installed and in PATH)
FFMPEG_PATH = "ffmpeg"
FFPROBE_PATH = "ffprobe"
