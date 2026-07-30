# 🎬 Telegram Video Splitter Bot

A production-ready Telegram bot that automatically splits videos into configurable clips using FFmpeg stream copy (zero quality loss). Built with Python 3.12+, Pyrogram, asyncio, and SQLAlchemy.

---

## ✨ Features

| Feature | Detail |
|---|---|
| **Stream copy splitting** | No re-encoding — original quality, blazing speed |
| **Flexible clip length** | 5 / 10 / 15 / 30 / 60 seconds (per user) |
| **Multiple inputs** | Telegram files, forwarded videos, direct URLs, YouTube |
| **Watermark** | Text or PNG logo, adjustable position & opacity |
| **Thumbnails** | Auto-generated, embedded in Telegram upload |
| **ZIP output** | All clips bundled into one archive |
| **Job queue** | Async queue with configurable concurrency |
| **Admin panel** | Stats, broadcast, ban/unban, sysinfo |
| **Auto cleanup** | Temp files removed after each job |
| **FloodWait handling** | Automatic retry with backoff |
| **Per-user settings** | Saved to database, persist across sessions |

---

## 📁 Project Structure

```
tg-video-splitter/
├── main.py                   # Entry point
├── config/
│   └── settings.py           # Environment config
├── bot/
│   ├── core/
│   │   ├── database.py       # SQLAlchemy models + repos
│   │   ├── queue.py          # Async job queue
│   │   ├── processor.py      # Full pipeline orchestrator
│   │   └── cleanup.py        # Background temp-file sweeper
│   ├── handlers/
│   │   ├── commands.py       # /start /help /status /cancel
│   │   ├── settings.py       # /settings + inline keyboards
│   │   ├── video.py          # Video & URL message handler
│   │   └── admin.py          # Admin-only commands
│   └── utils/
│       ├── ffmpeg.py         # FFmpeg probe / split / thumbnail
│       ├── downloader.py     # HTTP + YouTube downloader
│       ├── uploader.py       # Telegram upload + ZIP
│       ├── ui.py             # Keyboards, progress bars
│       └── logger.py         # Loguru multi-sink setup
├── scripts/
│   └── setup_vps.sh          # Ubuntu VPS bootstrap
├── Dockerfile
├── docker-compose.yml
├── Procfile                  # Railway / Heroku
├── render.yaml               # Render.com
├── railway.toml
├── requirements.txt
└── .env.example
```

---

## 🚀 Quick Start

### 1. Get credentials

1. Visit [my.telegram.org](https://my.telegram.org) → API development tools → get `API_ID` and `API_HASH`
2. Message [@BotFather](https://t.me/BotFather) → `/newbot` → get `BOT_TOKEN`
3. Get your Telegram user ID from [@userinfobot](https://t.me/userinfobot) → set as `OWNER_ID`

### 2. Configure

```bash
cp .env.example .env
nano .env    # Fill in your values
```

### 3. Deploy

---

## 🐳 Docker (Recommended)

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f bot

# Stop
docker-compose down
```

---

## 🖥 VPS (Ubuntu 22.04+)

```bash
git clone <repo> && cd tg-video-splitter
sudo bash scripts/setup_vps.sh

# Edit credentials
sudo nano /opt/video-splitter-bot/.env

# Start
sudo systemctl start video-splitter-bot
sudo journalctl -u video-splitter-bot -f
```

---

## 🚄 Railway

1. Fork / push this repo to GitHub
2. New Railway project → Deploy from GitHub repo
3. Add environment variables from `.env.example`
4. Railway auto-detects `railway.toml` and builds the Dockerfile

---

## 🟣 Render

1. New Render Web Service → Docker → point to your repo
2. Render auto-detects `render.yaml`
3. Set environment variables in the Render dashboard

---

## ⚙️ Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `API_ID` | ✅ | — | Telegram API ID |
| `API_HASH` | ✅ | — | Telegram API hash |
| `BOT_TOKEN` | ✅ | — | Bot token from @BotFather |
| `OWNER_ID` | ✅ | — | Your Telegram user ID |
| `ADMIN_IDS` | ❌ | — | Comma-separated extra admin IDs |
| `DATABASE_URL` | ❌ | `sqlite+aiosqlite:///data/bot.db` | SQLAlchemy URL |
| `LOG_CHANNEL` | ❌ | — | Telegram channel ID for startup logs |
| `TEMP_DIRECTORY` | ❌ | `/tmp/video_splitter` | Working directory for downloads |
| `MAX_FILE_SIZE` | ❌ | `2000` | Max file size in MB |
| `MAX_CONCURRENT_JOBS` | ❌ | `5` | Parallel processing slots |
| `CLEANUP_INTERVAL` | ❌ | `3600` | Temp sweep interval (seconds) |
| `WATERMARK_IMAGE` | ❌ | — | Path to PNG watermark logo |
| `ENABLE_YOUTUBE` | ❌ | `true` | Enable YouTube downloads |

---

## 📖 User Commands

| Command | Description |
|---|---|
| `/start` | Welcome message |
| `/help` | Full help menu |
| `/settings` | Configure clip length, format, watermark, etc. |
| `/status` | Check your current job status |
| `/cancel` | Cancel active job |

## 🛠 Admin Commands

| Command | Description |
|---|---|
| `/admin` | Admin panel overview |
| `/stats` | Global bot statistics |
| `/sysinfo` | CPU / RAM / disk usage |
| `/jobs` | Active and queued jobs |
| `/ban <user_id>` | Ban a user |
| `/unban <user_id>` | Unban a user |
| `/broadcast <text>` | Send message to all users |

---

## 🏗 Architecture

```
User Message
     │
     ▼
video.py handler          ← validates input, checks file size
     │
     ▼
JobQueue.enqueue()        ← asyncio.Queue + Semaphore (max N workers)
     │
     ▼
processor.process_job()   ← full pipeline
     ├── downloader        ← Pyrogram / aiohttp / yt-dlp
     ├── ffmpeg.probe()    ← duration, resolution, codecs
     ├── ffmpeg.split_video() ← stream-copy segments
     ├── ffmpeg.generate_thumbnail()
     └── uploader.upload_clips() ← individual or ZIP
```

### FFmpeg strategy

- **No watermark** → `-c copy` (stream copy). Splits in seconds, zero quality loss.
- **With watermark** → `-c:v libx264 -preset fast -crf 18`. Re-encodes only when necessary.

---

## 🔒 Security

- Rate limiting via Telegram's own FloodWait (handled automatically)
- File size validation before download
- Ban system for abusive users
- Non-root Docker user
- Temp files auto-deleted after every job (and swept by background cleaner)
- Input validation on all URL inputs

---

## 📦 Dependencies

- **pyrogram** — Telegram MTProto client
- **TgCrypto** — Fast cryptography for Pyrogram
- **loguru** — Structured multi-sink logging
- **sqlalchemy + aiosqlite** — Async ORM
- **aiohttp + aiofiles** — Async HTTP downloads
- **yt-dlp** — YouTube support
- **Pillow** — Image processing for watermarks
- **psutil** — System info for admin panel
- **humanize** — Human-readable sizes/times

---

## 📝 License

MIT
