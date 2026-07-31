"""FFmpeg and FFprobe utility wrappers.

Provides async-safe subprocess calls for video inspection,
splitting, and merging.
"""

import asyncio
import json
import logging
import math
from pathlib import Path
from typing import Callable, Coroutine, List, Tuple

import config

logger = logging.getLogger(__name__)


class FFmpegError(Exception):
    """Raised when an FFmpeg/FFprobe operation fails."""
    pass


async def _run_cmd(cmd: List[str], timeout: int = 300) -> Tuple[str, str]:
    """Run a subprocess command asynchronously and return stdout, stderr."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise FFmpegError(f"Command timed out after {timeout}s: {' '.join(cmd)}")

    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="ignore")[-500:]
        raise FFmpegError(f"Command failed (rc={proc.returncode}): {err}")

    return stdout.decode("utf-8", errors="ignore"), stderr.decode("utf-8", errors="ignore")


async def get_video_duration(filepath: Path) -> float:
    """Return video duration in seconds using FFprobe."""
    cmd = [
        config.FFPROBE_PATH,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(filepath),
    ]
    stdout, _ = await _run_cmd(cmd, timeout=60)
    try:
        duration = float(stdout.strip())
    except ValueError as exc:
        raise FFmpegError(f"Could not parse duration from ffprobe output: {stdout!r}") from exc
    if duration <= 0:
        raise FFmpegError("Video duration is zero or negative.")
    return duration


async def get_video_info(filepath: Path) -> dict:
    """Return detailed video metadata as a dictionary."""
    cmd = [
        config.FFPROBE_PATH,
        "-v", "error",
        "-show_format",
        "-show_streams",
        "-of", "json",
        str(filepath),
    ]
    stdout, _ = await _run_cmd(cmd, timeout=60)
    try:
        info = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise FFmpegError("Failed to parse ffprobe JSON output.") from exc
    return info


def _build_split_cmd(
    input_path: Path,
    output_path: Path,
    start: float,
    duration: float,
) -> List[str]:
    """Build an FFmpeg command that preserves original quality."""
    cmd = [
        config.FFMPEG_PATH,
        "-y",
        "-ss", str(start),
        "-t", str(duration),
        "-i", str(input_path),
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        "-fflags", "+genpts",
        str(output_path),
    ]
    return cmd


async def split_video(
    input_path: Path,
    output_dir: Path,
    clip_duration: float,
    on_clip_ready: Callable[[Path, int, int], Coroutine],
) -> List[Path]:
    """Split a video into clips of specified duration.

    Args:
        input_path: Path to source video.
        output_dir: Directory to write clips.
        clip_duration: Target duration per clip in seconds.
        on_clip_ready: Async callable(clip_path, current_clip, total_clips)
                       called immediately after each clip is created.

    Returns:
        List of generated clip paths in order.
    """
    total_duration = await get_video_duration(input_path)

    total_clips = math.ceil(total_duration / clip_duration)
    if total_clips < 1:
        total_clips = 1

    clips: List[Path] = []
    ext = input_path.suffix or ".mp4"

    for idx in range(total_clips):
        start = idx * clip_duration
        remaining = total_duration - start
        current_duration = min(clip_duration, remaining)

        output_path = output_dir / f"clip_{idx + 1:04d}{ext}"
        cmd = _build_split_cmd(input_path, output_path, start, current_duration)

        try:
            await _run_cmd(cmd, timeout=300)
        except FFmpegError:
            # Fallback: re-encode if copy fails
            logger.warning("Copy-mode split failed for clip %d, falling back to re-encode.", idx + 1)
            cmd_fallback = [
                config.FFMPEG_PATH,
                "-y",
                "-ss", str(start),
                "-t", str(current_duration),
                "-i", str(input_path),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "18",
                "-c:a", "aac",
                "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                str(output_path),
            ]
            await _run_cmd(cmd_fallback, timeout=300)

        clips.append(output_path)
        await on_clip_ready(output_path, idx + 1, total_clips)

    return clips


async def merge_videos(
    clip_paths: List[Path],
    output_path: Path,
    progress_callback: Callable[[str], Coroutine],
) -> Path:
    """Merge multiple clips into a single video using FFmpeg concat demuxer.

    Args:
        clip_paths: Ordered list of clip paths.
        output_path: Destination path for merged video.
        progress_callback: Async callable(status_message) for progress updates.

    Returns:
        Path to merged video.
    """
    if not clip_paths:
        raise FFmpegError("No clips provided for merge.")

    # Build concat list file
    list_path = output_path.with_suffix(".txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for clip in clip_paths:
            # Our paths are safe (no single quotes), but guard anyway
            escaped = str(clip).replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")

    await progress_callback("Merging...")

    cmd = [
        config.FFMPEG_PATH,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_path),
        "-c", "copy",
        str(output_path),
    ]

    try:
        await _run_cmd(cmd, timeout=600)
    except FFmpegError:
        logger.warning("Copy-mode merge failed, falling back to re-encode.")
        cmd_fallback = [
            config.FFMPEG_PATH,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_path),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            str(output_path),
        ]
        await _run_cmd(cmd_fallback, timeout=600)
    finally:
        list_path.unlink(missing_ok=True)

    await progress_callback("Uploading Final Video...")
    return output_path
