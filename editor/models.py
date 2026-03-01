from dataclasses import dataclass


@dataclass
class MediaFile:
    path: str
    name: str
    duration: float      # seconds
    width: int = 0
    height: int = 0
    fps: float = 0.0
    has_audio: bool = True

    def duration_str(self) -> str:
        total = int(self.duration)
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"


@dataclass
class TimelineClip:
    media: MediaFile
    track: int           # 0=Video1, 1=Video2, 2=Audio1
    start_time: float    # position on timeline (seconds)
    in_point: float = 0.0
    out_point: float = 0.0
    color: str = "#2a6496"
    loop_count: int = 1  # 1=once, N=N times, -1=infinite (fill to longest track)
    speed: float = 1.0   # 0.25–4.0
    muted: bool = False

    def __post_init__(self):
        if self.out_point == 0.0:
            self.out_point = self.media.duration

    # --- durations ---

    @property
    def source_duration(self) -> float:
        """Duration of one play-through after trim + speed."""
        return (self.out_point - self.in_point) / self.speed

    @property
    def duration(self) -> float:
        """Total clip duration on the timeline."""
        sd = self.source_duration
        if self.loop_count <= 0:   # -1 = infinite: show as 1 loop on canvas
            return sd
        return sd * self.loop_count

    @property
    def end_time(self) -> float:
        return self.start_time + self.duration

    # --- helpers ---

    def display_name(self) -> str:
        tags = []
        if self.loop_count > 1:
            tags.append(f"×{self.loop_count}")
        elif self.loop_count == -1:
            tags.append("∞")
        if abs(self.speed - 1.0) > 0.01:
            tags.append(f"{self.speed:.2g}×")
        if self.muted:
            tags.append("[M]")
        return self.media.name + ("  " + " ".join(tags) if tags else "")

    def copy(self) -> "TimelineClip":
        return TimelineClip(
            media=self.media,
            track=self.track,
            start_time=self.start_time,
            in_point=self.in_point,
            out_point=self.out_point,
            color=self.color,
            loop_count=self.loop_count,
            speed=self.speed,
            muted=self.muted,
        )
