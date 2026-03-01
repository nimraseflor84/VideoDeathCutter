import json
import subprocess
import shutil
from typing import Optional


def find_ffmpeg() -> tuple[str, str]:
    """Return (ffmpeg_path, ffprobe_path). Raises RuntimeError if not found."""
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError(
            "FFmpeg not found. Install via: brew install ffmpeg (macOS) "
            "or winget install ffmpeg (Windows)"
        )
    return ffmpeg, ffprobe


def probe_media(path: str) -> Optional[dict]:
    """Run ffprobe and return parsed JSON, or None on error."""
    _, ffprobe = find_ffmpeg()
    cmd = [
        ffprobe, "-v", "quiet",
        "-print_format", "json",
        "-show_streams", "-show_format",
        path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        return None


def get_media_info(path: str) -> Optional[dict]:
    """
    Returns dict with keys: duration, width, height, fps, has_audio.
    Returns None if file cannot be probed.
    """
    data = probe_media(path)
    if data is None:
        return None

    duration = float(data.get("format", {}).get("duration", 0))
    width = height = 0
    fps = 0.0
    has_audio = False

    for stream in data.get("streams", []):
        codec_type = stream.get("codec_type", "")
        if codec_type == "video" and width == 0:
            width = stream.get("width", 0)
            height = stream.get("height", 0)
            r_frame_rate = stream.get("r_frame_rate", "0/1")
            try:
                num, den = r_frame_rate.split("/")
                fps = float(num) / float(den) if float(den) != 0 else 0.0
            except (ValueError, ZeroDivisionError):
                fps = 0.0
        elif codec_type == "audio":
            has_audio = True

    return {
        "duration": duration,
        "width": width,
        "height": height,
        "fps": fps,
        "has_audio": has_audio,
    }


def format_time(seconds: float, show_frames: bool = False, fps: float = 25.0) -> str:
    """Format seconds as HH:MM:SS or HH:MM:SS:FF."""
    if seconds < 0:
        seconds = 0.0
    total_s = int(seconds)
    h = total_s // 3600
    m = (total_s % 3600) // 60
    s = total_s % 60
    if show_frames:
        f = int((seconds - total_s) * fps)
        return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"
    return f"{h:02d}:{m:02d}:{s:02d}"


SUPPORTED_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".avi", ".wmv", ".flv",
    ".m4v", ".webm", ".ts", ".mts", ".m2ts",
    ".mp3", ".aac", ".wav", ".flac", ".m4a", ".ogg",
}


def is_supported_media(path: str) -> bool:
    import os
    ext = os.path.splitext(path)[1].lower()
    return ext in SUPPORTED_EXTENSIONS
