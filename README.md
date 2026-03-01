# VideoDeathCutter

A dark-themed desktop video editor built with Python and PyQt6. Supports multi-track timeline editing, clip looping, speed control, and FFmpeg-powered export — packaged as a standalone `.app` (macOS) or `.exe` (Windows).

![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![PyQt6](https://img.shields.io/badge/PyQt6-6.4%2B-green)
![License](https://img.shields.io/badge/license-MIT-red)

---

## Features

- **3-track timeline** — Video 1, Video 2, Audio 1
- **Clip editing** — drag to move, drag edges to trim, snap to playhead and clip edges
- **Split clips** at playhead (Ctrl+K)
- **Loop & speed control** — set loop count per clip, match to audio/video length, speed 0.25×–4×
- **Mute** individual clips
- **Preview player** with loop markers (I/O), play/pause, volume
- **Undo / Redo** (Ctrl+Z / Ctrl+Y, up to 60 steps)
- **FFmpeg export** — MP4, MOV, MKV · H.264, H.265, ProRes · up to 4K · track sync options
- **Drag & drop** media import
- **Dark crimson theme**

---

## Requirements

- Python 3.9+
- FFmpeg + FFprobe on PATH
- PyQt6

```bash
pip install PyQt6 PyInstaller
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
```bash
winget install ffmpeg
```

---

## Run from source

```bash
python main.py
```

---

## Build standalone app

**macOS** → `dist/VideoDeathCutter.app`
```bash
sh build_mac.sh
```

**Windows** → `dist/VideoDeathCutter.exe`
```bash
build_windows.bat
```

---

## Shortcuts

| Key | Action |
|-----|--------|
| Ctrl+I | Import media |
| Ctrl+E | Export |
| Ctrl+Z / Ctrl+Y | Undo / Redo |
| Ctrl+K | Split clip at playhead |
| Del | Delete selected clip |
| Ctrl+P | Clip properties |
| Space | Play / Pause |
| I / O | Set loop IN / OUT |
| L | Toggle loop |
| Ctrl+= / Ctrl+- | Zoom timeline in / out |

---

## Project structure

```
├── main.py                 # Entry point + theme
├── requirements.txt
├── build_mac.sh
├── build_windows.bat
└── editor/
    ├── models.py           # MediaFile, TimelineClip
    ├── utils.py            # ffprobe wrapper
    ├── media_pool.py       # Import & media list
    ├── preview_player.py   # QMediaPlayer + loop
    ├── timeline_widget.py  # Custom QPainter timeline
    ├── clip_properties.py  # Loop / speed / mute dialog
    ├── export_dialog.py    # FFmpeg export
    └── main_window.py      # Main window
```
