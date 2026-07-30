"""
bot/utils/ffmpeg.py
All FFmpeg interactions: probing, splitting, watermarking, thumbnails.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from bot.utils.logger import logger

# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class VideoInfo:
    duration: float          # seconds
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: str
    file_size: int           # bytes
    bitrate: int             # bps


@dataclass
class WatermarkOptions:
    text: Optional[str] = None
    image_path: Optional[Path] = None
    position: str = "bottomright"   # topleft / topright / bottomleft / bottomright / center
    opacity: float = 0.7
    size: int = 24                  # font size for text watermark
    moving: bool = False


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _run(cmd: list[str], timeout: int = 3600) -> tuple[int, str, str]:
    """Run a subprocess asynchronously, return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"FFmpeg timed out after {timeout}s")
    return proc.returncode, stdout.decode(errors="replace"), stderr.decode(errors="replace")


def _position_filter(pos: str, w_expr: str = "overlay_w", h_expr: str = "overlay_h") -> str:
    """Return FFmpeg x:y overlay position string."""
    margin = 10
    mapping = {
        "topleft":     (margin, margin),
        "topright":    (f"main_w-{w_expr}-{margin}", margin),
        "bottomleft":  (margin, f"main_h-{h_expr}-{margin}"),
        "bottomright": (f"main_w-{w_expr}-{margin}", f"main_h-{h_expr}-{margin}"),
        "center":      (f"(main_w-{w_expr})/2", f"(main_h-{h_expr})/2"),
    }
    x, y = mapping.get(pos, mapping["bottomright"])
    return f"{x}:{y}"


# ── Public API ─────────────────────────────────────────────────────────────────

async def probe(path: Path) -> VideoInfo:
    """Return video metadata via ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams", "-show_format",
        str(path),
    ]
    rc, stdout, stderr = await _run(cmd, timeout=60)
    if rc != 0:
        raise RuntimeError(f"ffprobe failed: {stderr.strip()}")

    data = json.loads(stdout)
    fmt = data.get("format", {})
    streams = data.get("streams", [])

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})

    fps_raw = video_stream.get("r_frame_rate", "24/1")
    num, den = (int(x) for x in fps_raw.split("/"))
    fps = num / den if den else 24.0

    return VideoInfo(
        duration=float(fmt.get("duration", 0)),
        width=int(video_stream.get("width", 0)),
        height=int(video_stream.get("height", 0)),
        fps=fps,
        video_codec=video_stream.get("codec_name", "unknown"),
        audio_codec=audio_stream.get("codec_name", "unknown"),
        file_size=int(fmt.get("size", 0)),
        bitrate=int(fmt.get("bit_rate", 0)),
    )


async def split_video(
    source: Path,
    output_dir: Path,
    clip_length: int = 10,
    output_format: str = "mp4",
    watermark: Optional[WatermarkOptions] = None,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> List[Path]:
    """
    Split *source* into clips of *clip_length* seconds.

    Uses stream-copy when no watermark is requested (fast, lossless).
    Falls back to re-encode only when watermark filtering is needed.

    Returns list of output clip paths in order.
    """
    info = await probe(source)
    total_clips = math.ceil(info.duration / clip_length)
    output_dir.mkdir(parents=True, exist_ok=True)

    clips: List[Path] = []
    use_copy = watermark is None

    logger.bind(processing=True).info(
        f"Splitting '{source.name}' → {total_clips} clips "
        f"({clip_length}s each, copy={use_copy})"
    )

    for i in range(total_clips):
        start = i * clip_length
        out_name = f"clip_{i + 1:03d}.{output_format}"
        out_path = output_dir / out_name

        if use_copy:
            cmd = _copy_cmd(source, out_path, start, clip_length, output_format)
        else:
            cmd = _encode_cmd(source, out_path, start, clip_length, output_format, watermark)

        rc, _, stderr = await _run(cmd)
        if rc != 0:
            raise RuntimeError(f"FFmpeg error on clip {i + 1}: {stderr[-500:]}")

        clips.append(out_path)
        if progress_cb:
            progress_cb(i + 1, total_clips)

    return clips


def _copy_cmd(src: Path, dst: Path, start: float, length: int, fmt: str) -> list[str]:
    """Stream-copy segment (no quality loss, very fast)."""
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", str(src),
        "-t", str(length),
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
    ]
    if fmt == "mp4":
        cmd += ["-movflags", "+faststart"]
    cmd.append(str(dst))
    return cmd


def _encode_cmd(
    src: Path,
    dst: Path,
    start: float,
    length: int,
    fmt: str,
    wm: WatermarkOptions,
) -> list[str]:
    """Re-encode with watermark overlay."""
    vf_parts: list[str] = []

    if wm.image_path and wm.image_path.exists():
        alpha = wm.opacity
        pos = _position_filter(wm.position)
        vf_parts.append(
            f"[1:v]format=rgba,colorchannelmixer=aa={alpha}[wm];"
            f"[0:v][wm]overlay={pos}"
        )
    elif wm.text:
        text = wm.text.replace(":", "\\:").replace("'", "\\'")
        pos = _position_filter(wm.position, str(wm.size * 10), str(wm.size))
        vf_parts.append(
            f"drawtext=text='{text}':fontsize={wm.size}:fontcolor=white@{wm.opacity}:"
            f"x={pos.split(':')[0]}:y={pos.split(':')[1]}"
        )

    vf = ",".join(vf_parts) if vf_parts else "null"

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", str(src),
    ]
    if wm.image_path and wm.image_path.exists():
        cmd += ["-i", str(wm.image_path)]

    cmd += [
        "-t", str(length),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "copy",
        "-avoid_negative_ts", "make_zero",
    ]
    if fmt == "mp4":
        cmd += ["-movflags", "+faststart"]
    cmd.append(str(dst))
    return cmd


async def generate_thumbnail(source: Path, output: Path, timestamp: float = 1.0) -> Path:
    """Extract a single frame as thumbnail JPEG."""
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(timestamp),
        "-i", str(source),
        "-vframes", "1",
        "-q:v", "2",
        "-vf", "scale=320:-1",
        str(output),
    ]
    rc, _, stderr = await _run(cmd, timeout=30)
    if rc != 0:
        raise RuntimeError(f"Thumbnail generation failed: {stderr[-300:]}")
    return output


async def get_video_duration(path: Path) -> float:
    """Quick helper – returns duration in seconds."""
    info = await probe(path)
    return info.duration


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
