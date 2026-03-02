from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QSlider, QLabel, QSizePolicy,
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QKeyEvent

from .utils import format_time


class PreviewPlayer(QWidget):
    """Video preview with transport controls and loop support."""

    position_updated = pyqtSignal(float)   # current position in seconds
    loop_in_changed = pyqtSignal(float)
    loop_out_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loop_enabled = False
        self._loop_in = 0.0
        self._loop_out = 0.0
        self._duration = 0.0
        self._seeking = False
        self._current_path = ""
        self._pending_seek = 0.0
        self._user_stopped = False
        self._loop_restarting = False

        self._setup_ui()
        self._setup_player()
        self._setup_loop_timer()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        title = QLabel("Preview")
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: #ccc;")
        layout.addWidget(title)

        self._video_widget = QVideoWidget()
        self._video_widget.setMinimumHeight(200)
        self._video_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        # WA_NativeWindow: forces a native NSView on macOS so AVFoundation
        # can render video frames directly into it (without this: black screen)
        self._video_widget.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        layout.addWidget(self._video_widget)

        # Position slider
        self._position_slider = QSlider(Qt.Orientation.Horizontal)
        self._position_slider.setRange(0, 10000)
        self._position_slider.sliderPressed.connect(self._on_slider_pressed)
        self._position_slider.sliderReleased.connect(self._on_slider_released)
        self._position_slider.sliderMoved.connect(self._on_slider_moved)
        layout.addWidget(self._position_slider)

        # Time labels
        time_layout = QHBoxLayout()
        self._time_label = QLabel("00:00:00")
        self._time_label.setStyleSheet("color: #aaa; font-family: monospace;")
        self._duration_label = QLabel("00:00:00")
        self._duration_label.setStyleSheet("color: #aaa; font-family: monospace;")
        time_layout.addWidget(self._time_label)
        time_layout.addStretch()
        time_layout.addWidget(self._duration_label)
        layout.addLayout(time_layout)

        # Transport controls
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(6)

        self._play_btn = QPushButton("▶ Play")
        self._play_btn.setCheckable(True)
        self._play_btn.clicked.connect(self._toggle_play)
        ctrl_layout.addWidget(self._play_btn)

        self._stop_btn = QPushButton("■ Stop")
        self._stop_btn.clicked.connect(self.stop)
        ctrl_layout.addWidget(self._stop_btn)

        self._loop_btn = QPushButton("⟳ Loop")
        self._loop_btn.setCheckable(True)
        self._loop_btn.setToolTip("Toggle loop between IN/OUT markers (L)")
        self._loop_btn.clicked.connect(self._toggle_loop)
        ctrl_layout.addWidget(self._loop_btn)

        ctrl_layout.addStretch()

        # Volume
        vol_label = QLabel("Vol:")
        vol_label.setStyleSheet("color: #aaa;")
        ctrl_layout.addWidget(vol_label)
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(80)
        self._volume_slider.setMaximumWidth(80)
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        ctrl_layout.addWidget(self._volume_slider)

        layout.addLayout(ctrl_layout)

        # Loop marker controls
        marker_layout = QHBoxLayout()
        self._set_in_btn = QPushButton("[ Set IN (I)")
        self._set_in_btn.clicked.connect(self._set_loop_in)
        self._set_out_btn = QPushButton("Set OUT (O) ]")
        self._set_out_btn.clicked.connect(self._set_loop_out)
        self._loop_info_label = QLabel("IN: --  OUT: --")
        self._loop_info_label.setStyleSheet("color: #888; font-size: 11px;")
        marker_layout.addWidget(self._set_in_btn)
        marker_layout.addWidget(self._set_out_btn)
        marker_layout.addStretch()
        marker_layout.addWidget(self._loop_info_label)
        layout.addLayout(marker_layout)

    # ------------------------------------------------------------------
    # Player
    # ------------------------------------------------------------------

    def _setup_player(self):
        self._player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._player.setAudioOutput(self._audio_output)
        self._player.setVideoOutput(self._video_widget)
        self._audio_output.setVolume(0.8)

        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._player.errorOccurred.connect(self._on_error)

    def _setup_loop_timer(self):
        self._loop_timer = QTimer()
        self._loop_timer.setInterval(50)
        self._loop_timer.timeout.connect(self._check_loop)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, path: str, seek_to: float = 0.0):
        """Load a media file. Seek is applied after the media is ready."""
        self._pending_seek = seek_to
        if self._current_path == path:
            # Already loaded — seek directly
            if seek_to > 0:
                self._player.setPosition(int(seek_to * 1000))
            return
        self._current_path = path
        self._player.setSource(QUrl.fromLocalFile(path))
        self._play_btn.setChecked(False)
        self._play_btn.setText("▶ Play")

    def seek(self, seconds: float):
        """Seek to position in seconds."""
        ms = int(seconds * 1000)
        self._player.setPosition(ms)

    def play(self):
        self._player.play()

    def pause(self):
        self._player.pause()

    def stop(self):
        self._user_stopped = True
        self._player.pause()
        self._player.setPosition(0)
        self._play_btn.setChecked(False)
        self._play_btn.setText("▶ Play")

    def set_loop_markers(self, in_pt: float, out_pt: float):
        self._loop_in = in_pt
        self._loop_out = out_pt
        self._update_loop_info()

    def current_position(self) -> float:
        return self._player.position() / 1000.0

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _toggle_play(self):
        state = self._player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
            self._play_btn.setText("▶ Play")
        else:
            self._player.play()
            self._play_btn.setText("⏸ Pause")

    def _toggle_loop(self, checked: bool):
        self._loop_enabled = checked
        if checked:
            self._loop_btn.setStyleSheet("background-color: #1a6b3a; color: #fff;")
            self._apply_loop_mode()
        else:
            self._loop_timer.stop()
            self._loop_btn.setStyleSheet("")

    def _apply_loop_mode(self):
        """Marker-based loop uses QTimer; whole-file loop uses playbackStateChanged."""
        if self._loop_enabled and self._loop_out > self._loop_in:
            self._loop_timer.start()
        else:
            self._loop_timer.stop()

    def _set_loop_in(self):
        self._loop_in = self.current_position()
        self._update_loop_info()
        self.loop_in_changed.emit(self._loop_in)
        if self._loop_enabled:
            self._apply_loop_mode()

    def _set_loop_out(self):
        self._loop_out = self.current_position()
        self._update_loop_info()
        self.loop_out_changed.emit(self._loop_out)
        if self._loop_enabled:
            self._apply_loop_mode()

    def _update_loop_info(self):
        in_str = format_time(self._loop_in) if self._loop_in > 0 else "--"
        out_str = format_time(self._loop_out) if self._loop_out > 0 else "--"
        self._loop_info_label.setText(f"IN: {in_str}  OUT: {out_str}")

    def _check_loop(self):
        """Marker-based loop only — whole-file loop is handled by playbackStateChanged."""
        if not self._loop_enabled or self._loop_out <= self._loop_in:
            return
        if self._player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            return
        if self.current_position() >= self._loop_out:
            self._player.setPosition(int(self._loop_in * 1000))

    def _on_position_changed(self, ms: int):
        if self._seeking:
            return
        seconds = ms / 1000.0
        self._time_label.setText(format_time(seconds))
        if self._duration > 0:
            slider_val = int((seconds / self._duration) * 10000)
            self._position_slider.blockSignals(True)
            self._position_slider.setValue(slider_val)
            self._position_slider.blockSignals(False)
        self.position_updated.emit(seconds)

    def _on_duration_changed(self, ms: int):
        self._duration = ms / 1000.0
        self._duration_label.setText(format_time(self._duration))

    def _on_playback_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._play_btn.setChecked(True)
            self._play_btn.setText("⏸ Pause")
            self._user_stopped = False
            self._loop_restarting = False
        else:
            self._play_btn.setChecked(False)
            self._play_btn.setText("▶ Play")
            # Whole-file loop: guard flag prevents re-entrant restarts
            if (state == QMediaPlayer.PlaybackState.StoppedState
                    and self._loop_enabled
                    and self._loop_out <= self._loop_in
                    and not self._user_stopped
                    and not self._loop_restarting):
                self._loop_restarting = True
                QTimer.singleShot(50, self._restart_whole_file)

    def _restart_whole_file(self):
        """Restart from beginning using setPosition(0) + delayed play (no memory leak)."""
        if not self._loop_enabled or self._user_stopped:
            self._loop_restarting = False
            return
        self._player.setPosition(0)
        QTimer.singleShot(80, self._play_after_seek)

    def _play_after_seek(self):
        if self._loop_enabled and not self._user_stopped:
            self._player.play()
        self._loop_restarting = False

    def _on_media_status_changed(self, status):
        """Apply pending seek once media is loaded."""
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            if self._pending_seek > 0:
                self._player.setPosition(int(self._pending_seek * 1000))
                self._pending_seek = 0.0

    def _on_error(self, error, error_string: str):
        if error != QMediaPlayer.Error.NoError:
            self._current_path = ""
            self._time_label.setText("⚠ Fehler")
            self._duration_label.setText(error_string[:60])

    def _on_slider_pressed(self):
        self._seeking = True

    def _on_slider_released(self):
        val = self._position_slider.value()
        if self._duration > 0:
            seconds = (val / 10000.0) * self._duration
            self._player.setPosition(int(seconds * 1000))
        self._seeking = False

    def _on_slider_moved(self, val: int):
        if self._duration > 0:
            seconds = (val / 10000.0) * self._duration
            self._time_label.setText(format_time(seconds))

    def _on_volume_changed(self, val: int):
        self._audio_output.setVolume(val / 100.0)

    # ------------------------------------------------------------------
    # Keyboard shortcuts (I / O / L)
    # ------------------------------------------------------------------

    def handle_key(self, key: int):
        if key == Qt.Key.Key_I:
            self._set_loop_in()
        elif key == Qt.Key.Key_O:
            self._set_loop_out()
        elif key == Qt.Key.Key_L:
            self._loop_btn.setChecked(not self._loop_btn.isChecked())
            self._toggle_loop(self._loop_btn.isChecked())
        elif key == Qt.Key.Key_Space:
            self._toggle_play()
