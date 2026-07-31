"""Application configuration."""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
OWNER_ID: int = int(os.getenv("OWNER_ID", "0"))
API_ID: int = int(os.getenv("API_ID", "0"))
API_HASH: str = os.getenv("API_HASH", "")

BASE_DIR = Path(__file__).resolve().parent
TEMP_BASE = Path(os.getenv("TEMP_DIR", "/tmp/video_bot"))
TEMP_BASE.mkdir(parents=True, exist_ok=True)

LOG_FILE = TEMP_BASE / "bot.log"
LOG_LEVEL = logging.INFO

SUPPORTED_FORMATS = {"mp4", "mkv", "avi", "mov", "webm", "m4v"}

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"
