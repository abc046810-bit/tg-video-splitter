# Video Tool Bot - Docker Image
# Optimized for Render Free Plan deployment

FROM python:3.12-slim

# Install FFmpeg and FFprobe
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p downloads split merge temp logs

# Run the bot
CMD ["python", "bot.py"]
