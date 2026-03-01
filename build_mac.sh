#!/usr/bin/env bash
# Build VideoEditor.app for macOS
set -e

FFMPEG_PATH=$(which ffmpeg)
FFPROBE_PATH=$(which ffprobe)

if [ -z "$FFMPEG_PATH" ] || [ -z "$FFPROBE_PATH" ]; then
    echo "ERROR: ffmpeg/ffprobe not found. Install via: brew install ffmpeg"
    exit 1
fi

echo "Using ffmpeg: $FFMPEG_PATH"
echo "Using ffprobe: $FFPROBE_PATH"

python3 -m PyInstaller -y \
    --windowed \
    --name "VideoDeathCutter" \
    --add-binary "$FFMPEG_PATH:." \
    --add-binary "$FFPROBE_PATH:." \
    --hidden-import "PyQt6.QtMultimedia" \
    --hidden-import "PyQt6.QtMultimediaWidgets" \
    --hidden-import "editor" \
    --collect-all PyQt6 \
    main.py

echo ""
echo "Build complete: dist/VideoEditor.app"
