# File 6 : merge.py

import os
import subprocess
from config import MERGE_DIR


def merge_videos(video_list, output_name="merged_video.mp4"):
    """
    Merge videos in the SAME ORDER they are received.
    """

    os.makedirs(MERGE_DIR, exist_ok=True)

    list_file = os.path.join(MERGE_DIR, "merge_list.txt")

    with open(list_file, "w", encoding="utf-8") as f:
        for video in video_list:
            # preserve upload order
            path = os.path.abspath(video).replace("\\", "/")
            f.write(f"file '{path}'\n")

    output_file = os.path.join(MERGE_DIR, output_name)

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        list_file,
        "-c",
        "copy",
        "-y",
        output_file,
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise Exception(result.stderr)

    return output_file


def cleanup_merge():
    if not os.path.exists(MERGE_DIR):
        return

    for root, _, files in os.walk(MERGE_DIR):
        for file in files:
            try:
                os.remove(os.path.join(root, file))
            except:
                pass
