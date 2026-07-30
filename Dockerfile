FROM python:3.12-slim

# ── System dependencies ────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    yt-dlp \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── App directory ──────────────────────────────────────────────────────────────
WORKDIR /app

# ── Python dependencies ────────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy source ────────────────────────────────────────────────────────────────
COPY . .

# ── Runtime directories ────────────────────────────────────────────────────────
RUN mkdir -p /tmp/video_splitter data logs

# ── Non-root user ──────────────────────────────────────────────────────────────
RUN useradd -m -u 1000 botuser && chown -R botuser /app /tmp/video_splitter
USER botuser

# ── Entrypoint ─────────────────────────────────────────────────────────────────
CMD ["python", "main.py"]
