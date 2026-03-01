import math
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QSpinBox, QComboBox,
    QCheckBox, QDialogButtonBox, QGroupBox,
)
from PyQt6.QtCore import Qt

from .models import TimelineClip


class ClipPropertiesDialog(QDialog):
    """Edit loop, speed and mute settings of a clip."""

    def __init__(self, clip: TimelineClip, audio_duration: float = 0.0,
                 video_duration: float = 0.0, parent=None):
        super().__init__(parent)
        self._clip = clip
        self._audio_duration = audio_duration   # longest audio track
        self._video_duration = video_duration   # longest video track
        self.setWindowTitle(f"Clip-Eigenschaften: {clip.media.name}")
        self.setModal(True)
        self.resize(420, 340)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Info box
        info = QLabel(
            f"<b>{self._clip.media.name}</b><br>"
            f"Quelle: {self._clip.media.duration:.2f} s  ·  "
            f"{self._clip.media.width}×{self._clip.media.height}  ·  "
            f"{self._clip.media.fps:.2f} fps"
        )
        info.setStyleSheet("color: #aaa; font-size: 11px; padding: 4px;")
        layout.addWidget(info)

        # ── Loop ──────────────────────────────────────────────────────
        loop_group = QGroupBox("Loop / Wiederholen")
        loop_form = QFormLayout(loop_group)

        self._loop_spin = QSpinBox()
        self._loop_spin.setRange(-1, 9999)
        self._loop_spin.setValue(self._clip.loop_count)
        self._loop_spin.setSpecialValueText("∞  (unendlich)")
        self._loop_spin.setToolTip(
            "-1 = unendlich loopen  ·  1 = einmal abspielen  ·  N = N-mal"
        )
        self._loop_spin.valueChanged.connect(self._refresh_duration_label)

        loop_row = QHBoxLayout()
        loop_row.addWidget(self._loop_spin)

        if self._audio_duration > 0:
            btn_match_audio = QPushButton("= Audio-Länge")
            btn_match_audio.setToolTip(
                f"Loop-Anzahl berechnen, um Audio-Spur ({self._audio_duration:.1f} s) zu füllen"
            )
            btn_match_audio.clicked.connect(self._match_audio)
            loop_row.addWidget(btn_match_audio)

        if self._video_duration > 0:
            btn_match_video = QPushButton("= Video-Länge")
            btn_match_video.setToolTip(
                f"Loop-Anzahl berechnen, um Video-Spur ({self._video_duration:.1f} s) zu füllen"
            )
            btn_match_video.clicked.connect(self._match_video)
            loop_row.addWidget(btn_match_video)

        loop_form.addRow("Wiederholungen:", loop_row)

        self._dur_label = QLabel()
        loop_form.addRow("Gesamtdauer:", self._dur_label)

        layout.addWidget(loop_group)

        # ── Geschwindigkeit ───────────────────────────────────────────
        speed_group = QGroupBox("Geschwindigkeit")
        speed_form = QFormLayout(speed_group)

        self._speed_combo = QComboBox()
        speeds = [
            ("0.25×  (Zeitlupe)", 0.25),
            ("0.5×", 0.5),
            ("0.75×", 0.75),
            ("1×  (normal)", 1.0),
            ("1.5×", 1.5),
            ("2×  (Zeitraffer)", 2.0),
            ("4×", 4.0),
        ]
        current_idx = 3
        for i, (label, val) in enumerate(speeds):
            self._speed_combo.addItem(label, val)
            if abs(val - self._clip.speed) < 0.01:
                current_idx = i
        self._speed_combo.setCurrentIndex(current_idx)
        self._speed_combo.currentIndexChanged.connect(self._refresh_duration_label)
        speed_form.addRow("Wiedergabe:", self._speed_combo)
        layout.addWidget(speed_group)
        self._refresh_duration_label()  # call after both _loop_spin and _speed_combo exist

        # ── Audio ─────────────────────────────────────────────────────
        audio_group = QGroupBox("Audio")
        audio_layout = QVBoxLayout(audio_group)
        self._mute_check = QCheckBox("Clip stummschalten (Mute)")
        self._mute_check.setChecked(self._clip.muted)
        audio_layout.addWidget(self._mute_check)
        layout.addWidget(audio_group)

        layout.addStretch()

        # Buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._apply)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    # ------------------------------------------------------------------ helpers

    def _current_speed(self) -> float:
        return self._speed_combo.currentData() or 1.0

    def _refresh_duration_label(self):
        n = self._loop_spin.value()
        spd = self._current_speed()
        raw_src = (self._clip.out_point - self._clip.in_point)
        src_dur = raw_src / spd
        if n == -1:
            self._dur_label.setText("∞  (bis Ende der anderen Spur beim Export)")
        else:
            total = src_dur * max(1, n)
            h = int(total) // 3600
            m = (int(total) % 3600) // 60
            s = int(total) % 60
            frac = int((total % 1) * 10)
            t = f"{h:02d}:{m:02d}:{s:02d}.{frac}" if h else f"{m:02d}:{s:02d}.{frac}"
            self._dur_label.setText(f"{t}  ({total:.2f} s)")

    def _match_audio(self):
        src = (self._clip.out_point - self._clip.in_point) / self._current_speed()
        if src > 0:
            self._loop_spin.setValue(math.ceil(self._audio_duration / src))

    def _match_video(self):
        src = (self._clip.out_point - self._clip.in_point) / self._current_speed()
        if src > 0:
            self._loop_spin.setValue(math.ceil(self._video_duration / src))

    def _apply(self):
        self._clip.loop_count = self._loop_spin.value()
        self._clip.speed = self._current_speed()
        self._clip.muted = self._mute_check.isChecked()
        self.accept()
