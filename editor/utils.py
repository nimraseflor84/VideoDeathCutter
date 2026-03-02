import json
import subprocess
import shutil
from typing import Optional


def find_ffmpeg() -> tuple[str, str]:
    """Return (ffmpeg_path, ffprobe_path). Raises RuntimeError if not found."""
    import sys
    import os

    candidates = []

    # 1. PyInstaller bundle: ffmpeg is next to the executable
    if getattr(sys, "frozen", False):
        bundle_dir = os.path.dirname(sys.executable)
        candidates.append(bundle_dir)

    # 2. Common install locations (Homebrew Intel + Apple Silicon, MacPorts)
    candidates += [
        "/usr/local/bin",
        "/opt/homebrew/bin",
        "/opt/local/bin",
    ]

    for folder in candidates:
        ff = os.path.join(folder, "ffmpeg")
        fp = os.path.join(folder, "ffprobe")
        if os.path.isfile(ff) and os.path.isfile(fp):
            return ff, fp

    # 3. Fall back to system PATH
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        return ffmpeg, ffprobe

    raise RuntimeError(
        "FFmpeg nicht gefunden. Installieren mit: brew install ffmpeg"
    )


def probe_media(path: str) -> Optional[dict]:
    """Run ffprobe and return parsed JSON, or None on error."""
    _, ffprobe = find_ffmpeg()
    cmd = [
        ffprobe, "-v", "quiet",
        "-analyzeduration", "5000000",
        "-probesize", "5000000",
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
    # Video
    ".mp4", ".mov", ".mkv", ".avi", ".wmv", ".flv",
    ".m4v", ".webm", ".ts", ".mts", ".m2ts",
    ".mpg", ".mpeg", ".m2v", ".vob", ".3gp", ".3g2",
    ".divx", ".f4v", ".rm", ".rmvb", ".ogv", ".hevc",
    # Audio
    ".mp3", ".aac", ".wav", ".flac", ".m4a", ".ogg",
    ".wma", ".opus", ".mp2", ".ac3", ".dts", ".ra",
    ".amr", ".aiff", ".aif", ".ape", ".mka",
}


def is_supported_media(path: str) -> bool:
    import os
    ext = os.path.splitext(path)[1].lower()
    return ext in SUPPORTED_EXTENSIONS
