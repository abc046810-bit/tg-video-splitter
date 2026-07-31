import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

# Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
SPLIT_DIR = os.path.join(BASE_DIR, "split_videos")
MERGE_DIR = os.path.join(BASE_DIR, "merge_videos")
TEMP_DIR = os.path.join(BASE_DIR, "temp")

# Telegram upload chunk size
CHUNK_SIZE = 1024 * 1024

# Supported extensions
VIDEO_EXTENSIONS = (
    ".mp4",
    ".mkv",
    ".mov",
    ".avi",
    ".webm",
    ".m4v",
)

# Create folders automatically
for folder in (
    DOWNLOAD_DIR,
    SPLIT_DIR,
    MERGE_DIR,
    TEMP_DIR,
):
    os.makedirs(folder, exist_ok=True)
