from typing import Optional
from enum import Enum, auto

from PyQt6.QtWidgets import (
    QWidget, QScrollArea, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSizePolicy, QMenu,
)
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QFontMetrics,
    QMouseEvent, QWheelEvent, QKeyEvent, QCursor, QPolygon,
)

from .models import TimelineClip

# Layout constants
TRACK_HEIGHT = 52
HEADER_WIDTH = 120
RULER_HEIGHT = 30
TRIM_HANDLE_PX = 8
SNAP_THRESHOLD_PX = 8

MIN_ZOOM = 10.0
MAX_ZOOM = 500.0
DEFAULT_ZOOM = 80.0

TRACK_NAMES = ["Video 1", "Video 2", "Audio 1"]
TRACK_COLORS = [QColor("#2a6496"), QColor("#1a7a4a"), QColor("#7a4a1a")]
CLIP_COLORS = ["#2a6496", "#1a7a4a", "#7a4a1a"]


class DragMode(Enum):
    NONE = auto()
    PLAYHEAD = auto()
    MOVE = auto()
    TRIM_LEFT = auto()
    TRIM_RIGHT = auto()


class TimelineCanvas(QWidget):
    """Custom-painted timeline canvas with full editing capabilities."""

    # Signals
    position_changed = pyqtSignal(float)
    clip_selected = pyqtSignal(object)
    clip_moved = pyqtSignal(object)
    clip_trimmed = pyqtSignal(object)
    clip_delete_requested = pyqtSignal(object)
    clip_split_requested = pyqtSignal(object, float)
    clip_properties_requested = pyqtSignal(object)
    status_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._clips: list[TimelineClip] = []
        self._zoom = DEFAULT_ZOOM
        self._playhead = 0.0
        self._loop_in = 0.0
        self._loop_out = 0.0
        self._loop_enabled = False
        self._selected_clip: Optional[TimelineClip] = None

        # Drag state
        self._drag_mode = DragMode.NONE
        self._drag_clip: Optional[TimelineClip] = None
        self._drag_offset_x = 0
        self._trim_clip: Optional[TimelineClip] = None
        self._trim_orig_in = 0.0
        self._trim_orig_out = 0.0
        self._trim_orig_start = 0.0

        # Hover state (for cursor)
        self._hover_clip: Optional[TimelineClip] = None
        self._hover_edge: Optional[str] = None   # 'left', 'right', None

        fixed_h = RULER_HEIGHT + len(TRACK_NAMES) * TRACK_HEIGHT
        self.setFixedHeight(fixed_h)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    # ------------------------------------------------------------------ public API

    def add_clip(self, clip: TimelineClip):
        self._clips.append(clip)
        self._update_min_width()
        self.update()

    def remove_clip(self, clip: TimelineClip):
        if clip in self._clips:
            if clip is self._selected_clip:
                self._selected_clip = None
            self._clips.remove(clip)
            self.update()

    def clear_clips(self):
        self._clips.clear()
        self._selected_clip = None
        self.update()

    def set_clips(self, clips: list[TimelineClip]):
        self._clips = list(clips)
        self._selected_clip = None
        self._update_min_width()
        self.update()

    def set_playhead(self, seconds: float):
        self._playhead = max(0.0, seconds)
        self.update()

    def set_loop_markers(self, in_pt: float, out_pt: float, enabled: bool):
        self._loop_in = in_pt
        self._loop_out = out_pt
        self._loop_enabled = enabled
        self.update()

    def set_zoom(self, zoom: float):
        self._zoom = max(MIN_ZOOM, min(MAX_ZOOM, zoom))
        self._update_min_width()
        self.update()

    def zoom_level(self) -> float:
        return self._zoom

    def clips(self) -> list[TimelineClip]:
        return list(self._clips)

    def playhead_position(self) -> float:
        return self._playhead

    def selected_clip(self) -> Optional[TimelineClip]:
        return self._selected_clip

    # ------------------------------------------------------------------ coordinates

    def _time_to_x(self, t: float) -> int:
        return HEADER_WIDTH + int(t * self._zoom)

    def _x_to_time(self, x: int) -> float:
        return max(0.0, (x - HEADER_WIDTH) / self._zoom)

    def _track_y(self, track: int) -> int:
        return RULER_HEIGHT + track * TRACK_HEIGHT

    def _clip_rect(self, clip: TimelineClip) -> QRect:
        x = self._time_to_x(clip.start_time)
        y = self._track_y(clip.track) + 4
        w = max(6, int(clip.duration * self._zoom))
        h = TRACK_HEIGHT - 8
        return QRect(x, y, w, h)

    def _update_min_width(self):
        max_end = max((c.end_time for c in self._clips), default=60.0)
        self.setMinimumWidth(HEADER_WIDTH + int((max_end + 10) * self._zoom))

    # ------------------------------------------------------------------ hit test

    def _hit_test(self, pos: QPoint):
        """Returns (clip, 'left'|'right'|'move'|None)."""
        x, y = pos.x(), pos.y()
        if y < RULER_HEIGHT:
            return None, None
        for clip in reversed(self._clips):
            rect = self._clip_rect(clip)
            if not rect.contains(pos):
                continue
            if x - rect.left() <= TRIM_HANDLE_PX:
                return clip, 'left'
            if rect.right() - x <= TRIM_HANDLE_PX:
                return clip, 'right'
            return clip, 'move'
        return None, None

    # ------------------------------------------------------------------ snap

    def _snap_time(self, t: float, exclude: Optional[TimelineClip] = None) -> float:
        threshold = SNAP_THRESHOLD_PX / self._zoom
        # Snap to playhead
        if abs(t - self._playhead) < threshold:
            return self._playhead
        # Snap to clip edges
        for clip in self._clips:
            if clip is exclude:
                continue
            for edge in (clip.start_time, clip.end_time):
                if abs(t - edge) < threshold:
                    return edge
        return t

    # ------------------------------------------------------------------ paint

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w, h = self.width(), self.height()

        painter.fillRect(0, 0, w, h, QColor("#1e1e1e"))
        self._draw_ruler(painter, w)
        self._draw_track_headers(painter)
        self._draw_tracks(painter, w)
        self._draw_loop_region(painter)
        self._draw_clips(painter)
        self._draw_playhead(painter)

    def _draw_ruler(self, painter: QPainter, w: int):
        painter.fillRect(0, 0, w, RULER_HEIGHT, QColor("#2a2a2a"))
        painter.setPen(QPen(QColor("#444"), 1))
        painter.drawLine(0, RULER_HEIGHT - 1, w, RULER_HEIGHT - 1)

        visible = (w - HEADER_WIDTH) / self._zoom
        step = self._ruler_step(visible)
        font = QFont("monospace", 9)
        painter.setFont(font)

        t = 0.0
        while True:
            x = self._time_to_x(t)
            if x > w:
                break
            painter.setPen(QPen(QColor("#555"), 1))
            painter.drawLine(x, RULER_HEIGHT - 8, x, RULER_HEIGHT)
            painter.setPen(QColor("#bbb"))
            painter.drawText(x + 2, RULER_HEIGHT - 10, self._fmt_ruler(t))
            t += step

    def _ruler_step(self, visible: float) -> float:
        for s in (0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600):
            if visible / s < 30:
                return s
        return 600

    def _fmt_ruler(self, t: float) -> str:
        if t < 60:
            return f"{t:.1f}s" if t != int(t) else f"{int(t)}s"
        return f"{int(t)//60}:{int(t)%60:02d}"

    def _draw_track_headers(self, painter: QPainter):
        for i, name in enumerate(TRACK_NAMES):
            y = self._track_y(i)
            painter.fillRect(0, y, HEADER_WIDTH - 1, TRACK_HEIGHT, QColor("#252525"))
            painter.setPen(QPen(QColor("#3a3a3a"), 1))
            painter.drawRect(0, y, HEADER_WIDTH - 1, TRACK_HEIGHT - 1)
            painter.setPen(TRACK_COLORS[i])
            f = QFont("sans-serif", 10)
            f.setBold(True)
            painter.setFont(f)
            painter.drawText(8, y + TRACK_HEIGHT // 2 + 5, name)

    def _draw_tracks(self, painter: QPainter, w: int):
        for i in range(len(TRACK_NAMES)):
            y = self._track_y(i)
            # Alternating subtle shades
            bg = QColor("#1a1a1a") if i % 2 == 0 else QColor("#1d1d1d")
            painter.fillRect(HEADER_WIDTH, y, w - HEADER_WIDTH, TRACK_HEIGHT, bg)
            painter.setPen(QPen(QColor("#2e2e2e"), 1))
            painter.drawLine(HEADER_WIDTH, y + TRACK_HEIGHT - 1, w, y + TRACK_HEIGHT - 1)

    def _draw_loop_region(self, painter: QPainter):
        if not self._loop_enabled or self._loop_out <= self._loop_in:
            return
        x1 = self._time_to_x(self._loop_in)
        x2 = self._time_to_x(self._loop_out)
        total_h = RULER_HEIGHT + len(TRACK_NAMES) * TRACK_HEIGHT
        painter.fillRect(x1, RULER_HEIGHT, x2 - x1, total_h - RULER_HEIGHT,
                         QColor(80, 140, 255, 35))
        painter.setPen(QPen(QColor("#22dd44"), 2))
        painter.drawLine(x1, RULER_HEIGHT, x1, total_h)
        painter.setPen(QPen(QColor("#dd2244"), 2))
        painter.drawLine(x2, RULER_HEIGHT, x2, total_h)

    def _draw_clips(self, painter: QPainter):
        font = QFont("sans-serif", 9)
        painter.setFont(font)
        fm = QFontMetrics(font)

        for clip in self._clips:
            rect = self._clip_rect(clip)
            base_color = QColor(CLIP_COLORS[clip.track % len(CLIP_COLORS)])
            muted_color = base_color.darker(140)
            fill = muted_color if clip.muted else base_color

            # Body
            painter.fillRect(rect, fill)

            # Loop segment dividers
            if clip.loop_count != 1:
                self._draw_loop_segments(painter, clip, rect)

            # Selection / hover outline
            if clip is self._selected_clip:
                painter.setPen(QPen(QColor("#ffffff"), 2))
            elif clip is self._hover_clip:
                painter.setPen(QPen(QColor("#aaaaaa"), 1))
            else:
                painter.setPen(QPen(fill.lighter(55), 1))
            painter.drawRect(rect)

            # Trim handles on selected/hovered clip
            if clip is self._selected_clip or clip is self._hover_clip:
                handle = QColor(255, 255, 255, 180)
                painter.fillRect(rect.left(), rect.top() + 2, 4, rect.height() - 4, handle)
                painter.fillRect(rect.right() - 3, rect.top() + 2, 4, rect.height() - 4, handle)

            # Clip label
            painter.setPen(QColor("#fff"))
            text = clip.display_name()
            elided = fm.elidedText(text, Qt.TextElideMode.ElideRight, rect.width() - 8)
            painter.drawText(rect.left() + 5, rect.top() + 14, elided)

            # Duration + speed badge at bottom
            dur_text = f"{clip.duration:.1f}s"
            if clip.speed != 1.0:
                dur_text += f"  {clip.speed:.2g}×"
            painter.setPen(QColor("#ccc"))
            painter.drawText(rect.left() + 5, rect.bottom() - 4, dur_text)

    def _draw_loop_segments(self, painter: QPainter, clip: TimelineClip, rect: QRect):
        seg_px = int(clip.source_duration * self._zoom)
        if seg_px < 3:
            return
        pen = QPen(QColor(255, 255, 255, 70), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        x = rect.left() + seg_px
        while x < rect.right() - 1:
            painter.drawLine(x, rect.top() + 3, x, rect.bottom() - 3)
            x += seg_px
        # Infinite marker: right-side hatching
        if clip.loop_count == -1:
            inf_pen = QPen(QColor(255, 200, 0, 150), 1)
            painter.setPen(inf_pen)
            step = 6
            for i in range(rect.top(), rect.bottom(), step):
                x0 = max(rect.right() - 16, rect.left())
                painter.drawLine(x0, i, rect.right(), i + step)

    def _draw_playhead(self, painter: QPainter):
        x = self._time_to_x(self._playhead)
        total_h = RULER_HEIGHT + len(TRACK_NAMES) * TRACK_HEIGHT
        painter.setPen(QPen(QColor("#ff3333"), 2))
        painter.drawLine(x, 0, x, total_h)
        painter.setBrush(QBrush(QColor("#ff3333")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygon([QPoint(x-6, 0), QPoint(x+6, 0), QPoint(x, 12)]))

    # ------------------------------------------------------------------ mouse

    def mousePressEvent(self, event: QMouseEvent):
        self.setFocus()
        pos = event.position().toPoint()
        x, y = pos.x(), pos.y()

        if event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(pos, event.globalPosition().toPoint())
            return

        # Ruler or near playhead → move playhead
        if y < RULER_HEIGHT or self._is_near_playhead(x):
            self._drag_mode = DragMode.PLAYHEAD
            t = self._x_to_time(x)
            self._playhead = max(0.0, t)
            self.position_changed.emit(self._playhead)
            self.update()
            return

        clip, edge = self._hit_test(pos)
        if clip:
            self._selected_clip = clip
            self.clip_selected.emit(clip)
            if edge == 'left':
                self._drag_mode = DragMode.TRIM_LEFT
                self._trim_clip = clip
                self._trim_orig_in = clip.in_point
                self._trim_orig_start = clip.start_time
            elif edge == 'right':
                self._drag_mode = DragMode.TRIM_RIGHT
                self._trim_clip = clip
                self._trim_orig_out = clip.out_point
            else:
                self._drag_mode = DragMode.MOVE
                self._drag_clip = clip
                self._drag_offset_x = x - self._time_to_x(clip.start_time)
        else:
            self._selected_clip = None
            self._drag_mode = DragMode.NONE
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.position().toPoint()
        x = pos.x()

        if self._drag_mode == DragMode.PLAYHEAD:
            self._playhead = max(0.0, self._x_to_time(x))
            self.position_changed.emit(self._playhead)
            self.update()
            return

        if self._drag_mode == DragMode.MOVE and self._drag_clip:
            raw = max(0.0, self._x_to_time(x - self._drag_offset_x))
            snapped = self._snap_time(raw, exclude=self._drag_clip)
            self._drag_clip.start_time = snapped
            self._update_min_width()
            self.status_message.emit(
                f"{self._drag_clip.display_name()}  →  {snapped:.2f}s"
            )
            self.update()
            return

        if self._drag_mode == DragMode.TRIM_LEFT and self._trim_clip:
            clip = self._trim_clip
            new_time = max(0.0, self._x_to_time(x))
            delta = new_time - self._trim_orig_start
            new_in = self._trim_orig_in + delta * clip.speed
            new_in = max(0.0, min(clip.out_point - 0.05 * clip.speed, new_in))
            actual_delta = (new_in - self._trim_orig_in) / clip.speed
            clip.in_point = new_in
            clip.start_time = self._trim_orig_start + actual_delta
            self._update_min_width()
            self.update()
            return

        if self._drag_mode == DragMode.TRIM_RIGHT and self._trim_clip:
            clip = self._trim_clip
            new_time = self._x_to_time(x)
            new_out = clip.in_point + (new_time - clip.start_time) * clip.speed
            new_out = max(clip.in_point + 0.05 * clip.speed,
                          min(clip.media.duration, new_out))
            clip.out_point = new_out
            self._update_min_width()
            self.update()
            return

        # Idle: update hover/cursor
        if self._drag_mode == DragMode.NONE:
            clip, edge = self._hit_test(pos)
            if clip != self._hover_clip or edge != self._hover_edge:
                self._hover_clip = clip
                self._hover_edge = edge
                if edge in ('left', 'right'):
                    self.setCursor(Qt.CursorShape.SizeHorCursor)
                elif clip:
                    self.setCursor(Qt.CursorShape.SizeAllCursor)
                else:
                    self.setCursor(Qt.CursorShape.ArrowCursor)
                self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._drag_mode == DragMode.MOVE and self._drag_clip:
            self.clip_moved.emit(self._drag_clip)
            self.status_message.emit(
                f"{self._drag_clip.display_name()} → {self._drag_clip.start_time:.2f}s"
            )
        elif self._drag_mode in (DragMode.TRIM_LEFT, DragMode.TRIM_RIGHT) \
                and self._trim_clip:
            self.clip_trimmed.emit(self._trim_clip)
        self._drag_mode = DragMode.NONE
        self._drag_clip = None
        self._trim_clip = None

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        clip, _ = self._hit_test(event.position().toPoint())
        if clip:
            self.clip_properties_requested.emit(clip)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.set_zoom(self._zoom * factor)
            event.accept()
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
            if self._selected_clip:
                self.clip_delete_requested.emit(self._selected_clip)
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------ context menu

    def _show_context_menu(self, pos: QPoint, global_pos: QPoint):
        clip, _ = self._hit_test(pos)
        menu = QMenu(self)

        if clip:
            header = menu.addAction(f"  {clip.display_name()}")
            header.setEnabled(False)
            menu.addSeparator()

            act_split = menu.addAction("✂  Hier teilen (am Playhead)")
            act_split.triggered.connect(lambda: self.clip_split_requested.emit(clip, self._playhead))
            act_split.setEnabled(clip.start_time < self._playhead < clip.end_time)

            act_props = menu.addAction("⚙  Loop / Eigenschaften…")
            act_props.triggered.connect(lambda: self.clip_properties_requested.emit(clip))

            menu.addSeparator()

            act_mute = menu.addAction("🔇  Stummschalten" if not clip.muted else "🔊  Ton an")
            act_mute.triggered.connect(lambda: self._toggle_mute(clip))

            menu.addSeparator()

            act_del = menu.addAction("🗑  Löschen")
            act_del.triggered.connect(lambda: self.clip_delete_requested.emit(clip))
        else:
            act_add_ph = menu.addAction("Playhead hierher setzen")
            act_add_ph.triggered.connect(
                lambda: (setattr(self, '_playhead', max(0.0, self._x_to_time(pos.x()))),
                         self.position_changed.emit(self._playhead),
                         self.update())
            )

        menu.exec(global_pos)

    def _toggle_mute(self, clip: TimelineClip):
        clip.muted = not clip.muted
        self.clip_trimmed.emit(clip)   # reuse signal to trigger undo save
        self.update()

    def _is_near_playhead(self, x: int) -> bool:
        return abs(x - self._time_to_x(self._playhead)) <= 8


# ──────────────────────────────────────────────────────────────────────────────


class TimelineWidget(QWidget):
    """Timeline widget: toolbar + scroll area + canvas."""

    # Forward canvas signals
    position_changed = pyqtSignal(float)
    clip_selected = pyqtSignal(object)
    clip_moved = pyqtSignal(object)
    clip_trimmed = pyqtSignal(object)
    clip_delete_requested = pyqtSignal(object)
    clip_split_requested = pyqtSignal(object, float)
    clip_properties_requested = pyqtSignal(object)
    status_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Toolbar
        tb = QHBoxLayout()
        tb.setSpacing(6)
        lbl = QLabel("Timeline")
        lbl.setStyleSheet("font-weight:bold; font-size:13px; color:#ccc;")
        tb.addWidget(lbl)
        tb.addStretch()

        zm = QPushButton("−")
        zm.setFixedWidth(28)
        zm.setToolTip("Zoom out (Ctrl+−)")
        zm.clicked.connect(self._zoom_out)
        tb.addWidget(zm)

        self._zoom_label = QLabel("80 px/s")
        self._zoom_label.setStyleSheet("color:#888; font-size:11px; min-width:60px;")
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tb.addWidget(self._zoom_label)

        zp = QPushButton("+")
        zp.setFixedWidth(28)
        zp.setToolTip("Zoom in (Ctrl++)")
        zp.clicked.connect(self._zoom_in)
        tb.addWidget(zp)

        fit_btn = QPushButton("⊡ Einpassen")
        fit_btn.setToolTip("Alle Clips in Sichtbereich einpassen")
        fit_btn.clicked.connect(self._fit_all)
        tb.addWidget(fit_btn)

        layout.addLayout(tb)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea{border:none;}")

        self._canvas = TimelineCanvas()
        # Forward all canvas signals
        self._canvas.position_changed.connect(self.position_changed)
        self._canvas.clip_selected.connect(self.clip_selected)
        self._canvas.clip_moved.connect(self.clip_moved)
        self._canvas.clip_trimmed.connect(self.clip_trimmed)
        self._canvas.clip_delete_requested.connect(self.clip_delete_requested)
        self._canvas.clip_split_requested.connect(self.clip_split_requested)
        self._canvas.clip_properties_requested.connect(self.clip_properties_requested)
        self._canvas.status_message.connect(self.status_message)

        self._scroll.setWidget(self._canvas)
        layout.addWidget(self._scroll)

    # ------------------------------------------------------------------ public API

    def add_clip(self, clip: TimelineClip):
        self._canvas.add_clip(clip)

    def remove_clip(self, clip: TimelineClip):
        self._canvas.remove_clip(clip)

    def set_clips(self, clips: list[TimelineClip]):
        self._canvas.set_clips(clips)

    def set_playhead(self, seconds: float):
        self._canvas.set_playhead(seconds)
        self._scroll_to_playhead(seconds)

    def set_loop_markers(self, in_pt: float, out_pt: float, enabled: bool):
        self._canvas.set_loop_markers(in_pt, out_pt, enabled)

    def clips(self) -> list[TimelineClip]:
        return self._canvas.clips()

    def playhead_position(self) -> float:
        return self._canvas.playhead_position()

    def selected_clip(self) -> Optional[TimelineClip]:
        return self._canvas.selected_clip()

    def find_clip_at(self, time: float) -> Optional[TimelineClip]:
        """Return the first video clip (track 0) that covers the given time."""
        for clip in self._canvas.clips():
            if clip.track == 0 and clip.start_time <= time < clip.end_time:
                return clip
        return None

    # ------------------------------------------------------------------ zoom

    def _zoom_in(self):
        self._canvas.set_zoom(self._canvas.zoom_level() * 1.25)
        self._update_zoom_label()

    def _zoom_out(self):
        self._canvas.set_zoom(self._canvas.zoom_level() / 1.25)
        self._update_zoom_label()

    def _update_zoom_label(self):
        self._zoom_label.setText(f"{self._canvas.zoom_level():.0f} px/s")

    def zoom_in(self):
        self._zoom_in()

    def zoom_out(self):
        self._zoom_out()

    def _fit_all(self):
        """Zoom so all clips fit in the visible viewport width."""
        clips = self._canvas.clips()
        if not clips:
            return
        max_end = max(c.end_time for c in clips)
        if max_end <= 0:
            return
        vw = self._scroll.viewport().width() - HEADER_WIDTH - 20
        new_zoom = max(MIN_ZOOM, min(MAX_ZOOM, vw / max_end))
        self._canvas.set_zoom(new_zoom)
        self._update_zoom_label()
        self._scroll.horizontalScrollBar().setValue(0)

    # ------------------------------------------------------------------ helpers

    def _scroll_to_playhead(self, seconds: float):
        x = HEADER_WIDTH + int(seconds * self._canvas.zoom_level())
        vw = self._scroll.viewport().width()
        sb = self._scroll.horizontalScrollBar()
        cur = sb.value()
        if x < cur + HEADER_WIDTH or x > cur + vw - 40:
            sb.setValue(max(0, x - vw // 2))
