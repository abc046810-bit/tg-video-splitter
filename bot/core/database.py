"""
bot/core/database.py
Async SQLAlchemy setup + ORM models.
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Float, Integer,
    String, Text, func, select
)
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from config import settings
from bot.utils.logger import logger


# ── Engine / Session ──────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


# ── Models ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)        # Telegram user_id
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str] = mapped_column(String(128), default="")
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)

    # Per-user settings (JSON-like columns stored as strings)
    clip_length: Mapped[int] = mapped_column(Integer, default=10)
    output_format: Mapped[str] = mapped_column(String(8), default="mp4")
    watermark_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    thumbnail_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    zip_output: Mapped[bool] = mapped_column(Boolean, default=False)
    keep_resolution: Mapped[bool] = mapped_column(Boolean, default=True)
    watermark_text: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(32), default="queued")  # queued/processing/done/failed/cancelled
    source_type: Mapped[str] = mapped_column(String(16), default="telegram")  # telegram/url/youtube
    source_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    clips_count: Mapped[int] = mapped_column(Integer, default=0)
    clip_length: Mapped[int] = mapped_column(Integer, default=10)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processing_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BotStats(Base):
    """Single-row global statistics table."""
    __tablename__ = "bot_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    total_users: Mapped[int] = mapped_column(Integer, default=0)
    total_videos: Mapped[int] = mapped_column(Integer, default=0)
    total_clips: Mapped[int] = mapped_column(Integer, default=0)
    total_processing_seconds: Mapped[float] = mapped_column(Float, default=0.0)


# ── Repository helpers ─────────────────────────────────────────────────────────

class UserRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, user_id: int, username: str | None, first_name: str) -> User:
        result = await self.session.get(User, user_id)
        if result is None:
            result = User(id=user_id, username=username, first_name=first_name)
            self.session.add(result)
            await self.session.flush()
            # Bump global counter
            await self._bump_users()
        else:
            result.username = username
            result.first_name = first_name
            result.last_seen = datetime.datetime.now(datetime.timezone.utc)
        return result

    async def _bump_users(self) -> None:
        stats = await self.session.get(BotStats, 1)
        if stats is None:
            self.session.add(BotStats(id=1, total_users=1))
        else:
            stats.total_users += 1

    async def get_settings(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def update_settings(self, user_id: int, **kwargs) -> None:
        user = await self.session.get(User, user_id)
        if user:
            for k, v in kwargs.items():
                setattr(user, k, v)

    async def total_count(self) -> int:
        result = await self.session.execute(select(func.count(User.id)))
        return result.scalar_one()


class JobRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, **kwargs) -> Job:
        job = Job(user_id=user_id, **kwargs)
        self.session.add(job)
        await self.session.flush()
        return job

    async def update(self, job_id: int, **kwargs) -> None:
        job = await self.session.get(Job, job_id)
        if job:
            for k, v in kwargs.items():
                setattr(job, k, v)

    async def get(self, job_id: int) -> Job | None:
        return await self.session.get(Job, job_id)

    async def record_completion(self, job_id: int, clips: int, processing_time: float) -> None:
        await self.update(job_id, status="done", clips_count=clips, processing_time=processing_time)
        stats = await self.session.get(BotStats, 1)
        if stats is None:
            self.session.add(BotStats(id=1, total_videos=1, total_clips=clips, total_processing_seconds=processing_time))
        else:
            stats.total_videos += 1
            stats.total_clips += clips
            stats.total_processing_seconds += processing_time

    async def global_stats(self) -> BotStats | None:
        return await self.session.get(BotStats, 1)


# ── Init ───────────────────────────────────────────────────────────────────────

async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialised.")
