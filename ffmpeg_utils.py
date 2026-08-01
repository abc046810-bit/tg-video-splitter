"""FFmpeg utilities for video processing."""

import asyncio
import logging
import math
import re
from pathlib import Path
from typing import List, Optional

import config

logger = logging.getLogger(__name__)


class FFmpegError(Exception):
    """Raised when FFmpeg/FFprobe fails."""
    pass


async def _run(cmd: List[str], timeout: int = 600) -> str:
    """Run an FFmpeg command asynchronously."""
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
        raise FFmpegError(f"Command timed out after {timeout}s")

    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="ignore")[-800:]
        raise FFmpegError(f"FFmpeg error (rc={proc.returncode}): {err}")

    return stdout.decode("utf-8", errors="ignore")


async def get_duration(path: Path) -> float:
    """Return video duration in seconds."""
    cmd = [
        config.FFPROBE, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    out = await _run(cmd, timeout=60)
    try:
        duration = float(out.strip())
    except ValueError as exc:
        raise FFmpegError(f"Invalid duration output: {out!r}") from exc
    if duration <= 0:
        raise FFmpegError("Video duration is zero or negative")
    return duration


async def get_video_bitrate(path: Path) -> Optional[int]:
    """Return video stream bitrate in bits per second."""
    cmd = [
        config.FFPROBE, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=bit_rate",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    out = await _run(cmd, timeout=30)
    out = out.strip()
    if out and out != "N/A":
        try:
            return int(out)
        except ValueError:
            pass
    return None


def _build_reencode_cmd(
    input_path: Path,
    output_path: Path,
    start: float,
    duration: float,
    bitrate: Optional[int],
) -> List[str]:
    """Build re-encode command that preserves original bitrate."""
    cmd = [
        config.FFMPEG, "-y",
        "-ss", str(start),
        "-i", str(input_path),
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "fast",
    ]
    if bitrate:
        cmd += ["-b:v", str(bitrate)]
    else:
        cmd += ["-crf", "23"]
    cmd += [
        "-c:a", "aac",
        "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]
    return cmd


async def split_video(
    input_path: Path,
    output_dir: Path,
    clip_duration: float,
    status_callback,
) -> List[Path]:
    """Split video into clips. Uses copy mode first, falls back to re-encode."""
    total_duration = await get_duration(input_path)
    total_clips = math.ceil(total_duration / clip_duration)
    ext = input_path.suffix or ".mp4"
    clips: List[Path] = []
    bitrate = await get_video_bitrate(input_path)

    for idx in range(total_clips):
        start = idx * clip_duration
        remaining = total_duration - start
        duration = min(clip_duration, remaining)
        output_path = output_dir / f"part_{idx + 1:04d}{ext}"

        await status_callback(f"Splitting... Part {idx + 1}/{total_clips}")

        # Try copy mode first (fast, preserves original size)
        cmd_copy = [
            config.FFMPEG, "-y",
            "-ss", str(start),
            "-i", str(input_path),
            "-t", str(duration),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            "-fflags", "+genpts",
            str(output_path),
        ]

        try:
            await _run(cmd_copy, timeout=300)
        except FFmpegError:
            logger.warning("Copy split failed for part %d, re-encoding with bitrate %s...", idx + 1, bitrate)
            cmd_reencode = _build_reencode_cmd(input_path, output_path, start, duration, bitrate)
            await _run(cmd_reencode, timeout=300)

        clips.append(output_path)

    return clips


async def merge_videos(
    clip_paths: List[Path],
    output_path: Path,
    status_callback,
) -> Path:
    """Merge clips. Uses copy mode first, falls back to re-encode."""
    if not clip_paths:
        raise FFmpegError("No clips provided")

    list_path = output_path.with_suffix(".txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for clip in clip_paths:
            line = "file '" + str(clip) + "'\n"
            f.write(line)

    await status_callback("Merging clips...")

    # Try copy mode first (fast, preserves original size)
    cmd_copy = [
        config.FFMPEG, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_path),
        "-c", "copy",
        "-movflags", "+faststart",
        str(output_path),
    ]

    try:
        await _run(cmd_copy, timeout=600)
    except FFmpegError:
        logger.warning("Copy merge failed, re-encoding...")
        # Use bitrate from first clip to keep size similar
        bitrate = await get_video_bitrate(clip_paths[0])
        cmd_reencode = [
            config.FFMPEG, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_path),
            "-c:v", "libx264",
            "-preset", "fast",
        ]
        if bitrate:
            cmd_reencode += ["-b:v", str(bitrate)]
        else:
            cmd_reencode += ["-crf", "23"]
        cmd_reencode += [
            "-c:a", "aac",
            "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_path),
        ]
        await _run(cmd_reencode, timeout=600)
    finally:
        list_path.unlink(missing_ok=True)

    return output_path
