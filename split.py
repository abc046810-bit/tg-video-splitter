# File 5 : split.py

import os
import math
import subprocess

from telegram import Update
from telegram.ext import ContextTypes

from config import SPLIT_DIR


def get_duration(video_path: str) -> float:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    return float(result.stdout.strip())


def split_video(video_path: str, seconds: int, output_dir: str):

    os.makedirs(output_dir, exist_ok=True)

    total = get_duration(video_path)

    clips = math.ceil(total / seconds)

    output_files = []

    for i in range(clips):

        start = i * seconds

        out = os.path.join(
            output_dir,
            f"clip_{i+1:04d}.mp4",
        )

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            str(start),
            "-i",
            video_path,
            "-t",
            str(seconds),
            "-c",
            "copy",
            "-y",
            out,
        ]

        subprocess.run(cmd)

        if os.path.exists(out):
            output_files.append(out)

    return output_files


async def process_split(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    video_path: str,
    duration: int,
):

    msg = await update.message.reply_text(
        "Processing..."
    )

    folder = os.path.join(
        SPLIT_DIR,
        os.path.basename(video_path).split(".")[0],
    )

    clips = split_video(
        video_path,
        duration,
        folder,
    )

    total = len(clips)

    for index, clip in enumerate(clips, start=1):

        await context.bot.send_video(
            chat_id=update.effective_chat.id,
            video=open(clip, "rb"),
            supports_streaming=True,
            caption=f"Clip {index}/{total}",
        )

        await msg.edit_text(
            f"Sent {index}/{total}"
        )

    await msg.edit_text(
        "✅ Split Finished."
    )
