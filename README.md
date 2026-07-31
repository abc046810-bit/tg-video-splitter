# Video Tool Bot

A production-ready Telegram bot for splitting and merging videos, built with Python and FFmpeg. Optimized for deployment on Render Free Plan.

## Features

- **Split**: Divide any video into clips of a chosen duration (5s, 10s, 20s, 30s, 60s, or custom)
- **Merge**: Combine multiple clips into a single video, preserving exact upload order
- **Owner-only access**: Only the configured owner can use the bot
- **Quality preservation**: Uses FFmpeg copy mode when possible; falls back to high-quality re-encode
- **Live progress updates**: Real-time status messages during processing
- **Automatic cleanup**: All temporary files are removed after processing or on cancellation
- **Modular architecture**: Easy to extend with new features

## Supported Formats

- MP4
- MKV
- AVI
- MOV
- WEBM
- M4V

## Project Structure

