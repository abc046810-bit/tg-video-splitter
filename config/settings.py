"""
config/settings.py
Central configuration loaded from environment variables.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable '{key}' is not set.")
    return value


def _int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).lower() in ("1", "true", "yes")


def _list(key: str, default: str = "") -> List[int]:
    raw = os.getenv(key, default).strip()
    if not raw:
        return []
    return [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]


@dataclass(frozen=True)
class Settings:
    # ── Telegram ──────────────────────────────────────────────────────────
    api_id: int = field(default_factory=lambda: int(_require("API_ID")))
    api_hash: str = field(default_factory=lambda: _require("API_HASH"))
    bot_token: str = field(default_factory=lambda: _require("BOT_TOKEN"))
    owner_id: int = field(default_factory=lambda: int(_require("OWNER_ID")))
    admin_ids: List[int] = field(default_factory=lambda: _list("ADMIN_IDS"))

    # ── Database ──────────────────────────────────────────────────────────
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/bot.db")
    )

    # ── Logging ───────────────────────────────────────────────────────────
    log_channel: int = field(
        default_factory=lambda: _int("LOG_CHANNEL", 0)
    )

    # ── File handling ─────────────────────────────────────────────────────
    temp_directory: Path = field(
        default_factory=lambda: Path(os.getenv("TEMP_DIRECTORY", "/tmp/video_splitter"))
    )
    max_file_size_mb: int = field(default_factory=lambda: _int("MAX_FILE_SIZE", 2000))
    max_concurrent_jobs: int = field(default_factory=lambda: _int("MAX_CONCURRENT_JOBS", 5))
    cleanup_interval: int = field(default_factory=lambda: _int("CLEANUP_INTERVAL", 3600))

    # ── Features ──────────────────────────────────────────────────────────
    watermark_image: Path | None = field(
        default_factory=lambda: (
            Path(p) if (p := os.getenv("WATERMARK_IMAGE", "")) else None
        )
    )
    enable_youtube: bool = field(default_factory=lambda: _bool("ENABLE_YOUTUBE", True))
    enable_premium: bool = field(default_factory=lambda: _bool("ENABLE_PREMIUM", False))

    # ── Derived helpers ───────────────────────────────────────────────────
    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def all_admins(self) -> List[int]:
        return list({self.owner_id, *self.admin_ids})

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.all_admins


# Singleton
settings = Settings()

# Ensure required directories exist
settings.temp_directory.mkdir(parents=True, exist_ok=True)
Path("data").mkdir(exist_ok=True)
Path("logs").mkdir(exist_ok=True)
