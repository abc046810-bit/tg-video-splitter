# File 7 : ffmpeg_utils.py

import os
import json
import shutil
import subprocess


def ffmpeg_exists() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def run(cmd):
    process = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip())

    return process.stdout.strip()


def probe(video_path: str) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        video_path,
    ]

    data = run(cmd)
    return json.loads(data)


def get_duration(video_path: str) -> float:
    info = probe(video_path)
    return float(info["format"]["duration"])


def get_size(video_path: str) -> int:
    return os.path.getsize(video_path)


def get_filename(video_path: str) -> str:
    return os.path.basename(video_path)


def is_video(video_path: str) -> bool:
    try:
        info = probe(video_path)

        for stream in info["streams"]:
            if stream.get("codec_type") == "video":
                return True

        return False

    except Exception:
        return False


def get_resolution(video_path: str):
    info = probe(video_path)

    for stream in info["streams"]:
        if stream.get("codec_type") == "video":
            return (
                stream.get("width"),
                stream.get("height"),
            )

    return None, None


def get_fps(video_path: str):
    info = probe(video_path)

    for stream in info["streams"]:
        if stream.get("codec_type") == "video":

            fps = stream.get("r_frame_rate", "0/1")

            a, b = fps.split("/")

            if int(b) == 0:
                return 0

            return round(float(a) / float(b), 2)

    return 0


def ensure_ffmpeg():
    if not ffmpeg_exists():
        raise RuntimeError(
            "FFmpeg or FFprobe not found."
  )
