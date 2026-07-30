"""
bot/core/queue.py
Async job queue with configurable concurrency.
Jobs are processed in order; each worker slot handles one job at a time.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, Optional

from bot.utils.logger import logger
from config import settings


@dataclass
class QueuedJob:
    job_id: int
    user_id: int
    coro_factory: Callable[[], Coroutine[Any, Any, None]]
    enqueued_at: float = field(default_factory=time.time)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)


class JobQueue:
    """
    Wraps asyncio.Queue and maintains a semaphore to cap concurrent workers.
    """

    def __init__(self, max_workers: int = 5):
        self._queue: asyncio.Queue[QueuedJob] = asyncio.Queue()
        self._sem = asyncio.Semaphore(max_workers)
        self._active: Dict[int, QueuedJob] = {}  # job_id → job
        self._worker_task: Optional[asyncio.Task] = None

    def start(self) -> None:
        self._worker_task = asyncio.create_task(self._dispatcher(), name="job_dispatcher")
        logger.info(f"JobQueue started (max_workers={settings.max_concurrent_jobs})")

    async def stop(self) -> None:
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def enqueue(self, job: QueuedJob) -> int:
        """Add job to queue; returns queue position (1-based)."""
        await self._queue.put(job)
        pos = self._queue.qsize()
        logger.debug(f"Job {job.job_id} enqueued (position ~{pos})")
        return pos

    def cancel(self, job_id: int) -> bool:
        """Signal a job to cancel. Returns True if found."""
        if job_id in self._active:
            self._active[job_id].cancel_event.set()
            logger.info(f"Cancel signal sent to active job {job_id}")
            return True
        # Mark pending jobs by temporarily iterating (they'll check on pickup)
        logger.info(f"Job {job_id} not found in active jobs")
        return False

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def active_count(self) -> int:
        return len(self._active)

    async def _dispatcher(self) -> None:
        while True:
            job = await self._queue.get()
            asyncio.create_task(self._run_job(job))

    async def _run_job(self, job: QueuedJob) -> None:
        async with self._sem:
            self._active[job.job_id] = job
            try:
                if job.cancel_event.is_set():
                    logger.info(f"Job {job.job_id} was cancelled before execution")
                    return
                await job.coro_factory()
            except asyncio.CancelledError:
                logger.warning(f"Job {job.job_id} task cancelled")
            except Exception as exc:
                logger.exception(f"Unhandled error in job {job.job_id}: {exc}")
            finally:
                self._active.pop(job.job_id, None)
                self._queue.task_done()


# Singleton
job_queue = JobQueue(max_workers=settings.max_concurrent_jobs)
