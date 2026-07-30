#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup_vps.sh  —  Bootstrap script for Ubuntu 22.04+ VPS
# Run as root or with sudo:  bash setup_vps.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

echo "==> Updating packages"
apt-get update && apt-get upgrade -y

echo "==> Installing system dependencies"
apt-get install -y \
    python3.12 python3.12-venv python3.12-dev \
    ffmpeg \
    curl wget git \
    build-essential libssl-dev libffi-dev

echo "==> Installing yt-dlp"
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp
chmod +x /usr/local/bin/yt-dlp

echo "==> Creating app user"
useradd -m -s /bin/bash botuser 2>/dev/null || true

echo "==> Setting up project directory"
mkdir -p /opt/video-splitter-bot
cp -r . /opt/video-splitter-bot/
chown -R botuser:botuser /opt/video-splitter-bot

echo "==> Installing Python dependencies"
cd /opt/video-splitter-bot
sudo -u botuser python3.12 -m venv venv
sudo -u botuser ./venv/bin/pip install --upgrade pip
sudo -u botuser ./venv/bin/pip install -r requirements.txt

echo "==> Creating .env from example"
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️  Please edit /opt/video-splitter-bot/.env with your credentials"
fi

echo "==> Installing systemd service"
cat > /etc/systemd/system/video-splitter-bot.service << 'EOF'
[Unit]
Description=Telegram Video Splitter Bot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/opt/video-splitter-bot
EnvironmentFile=/opt/video-splitter-bot/.env
ExecStart=/opt/video-splitter-bot/venv/bin/python main.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable video-splitter-bot

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit /opt/video-splitter-bot/.env with your API credentials"
echo "  2. sudo systemctl start video-splitter-bot"
echo "  3. sudo journalctl -u video-splitter-bot -f   (view logs)"
