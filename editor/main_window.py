import json
import os

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter,
    QMessageBox, QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QAction, QKeyEvent, QDragEnterEvent, QDropEvent

from .models import MediaFile, TimelineClip
from .media_pool import MediaPool
from .preview_player import PreviewPlayer
from .timeline_widget import TimelineWidget
from .export_dialog import ExportDialog
from .clip_properties import ClipPropertiesDialog
from .utils import is_supported_media

CLIP_COLORS = ["#2a6496", "#1a7a4a", "#7a4a1a"]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VideoDeathCutter")
        self.resize(1400, 900)
        self.setAcceptDrops(True)

        # Undo / Redo stack (snapshots of clip lists)
        self._undo_stack: list[list[TimelineClip]] = []
        self._undo_index = -1

        self._setup_menu()
        self._setup_ui()
        self._connect_signals()

        self.statusBar().showMessage(
            "Bereit  ·  Ctrl+I = Import  ·  Doppelklick auf Clip = Eigenschaften  ·  Ctrl+K = Teilen  ·  Entf = Löschen"
        )
        self._push_undo()   # initial empty state

    # ------------------------------------------------------------------ menu

    def _setup_menu(self):
        mb = self.menuBar()

        # ── Datei ──────────────────────────────────────────────────────
        fm = mb.addMenu("Datei")
        self._a(fm, "Medien importieren…", "Ctrl+I", self._import_media)
        fm.addSeparator()
        self._a(fm, "Projekt speichern…", "Ctrl+S", self._save_project)
        self._a(fm, "Projekt öffnen…",    "Ctrl+O", self._load_project)
        fm.addSeparator()
        self._a(fm, "Exportieren…", "Ctrl+E", self._open_export)
        fm.addSeparator()
        self._a(fm, "Beenden", "Ctrl+Q", self.close)

        # ── Bearbeiten ─────────────────────────────────────────────────
        em = mb.addMenu("Bearbeiten")
        self._undo_action = self._a(em, "Rückgängig", "Ctrl+Z", self._undo)
        self._redo_action = self._a(em, "Wiederholen", "Ctrl+Y", self._redo)
        em.addSeparator()
        self._a(em, "Clip teilen (am Playhead)", "Ctrl+K", self._split_at_playhead)
        self._a(em, "Ausgewählten Clip löschen", "Delete", self._delete_selected)
        em.addSeparator()
        self._a(em, "Clip-Eigenschaften…", "Ctrl+P", self._show_clip_properties)
        self._update_undo_actions()

        # ── Ansicht ────────────────────────────────────────────────────
        vm = mb.addMenu("Ansicht")
        self._a(vm, "Timeline vergrößern", "Ctrl+=", lambda: self._timeline.zoom_in())
        self._a(vm, "Timeline verkleinern", "Ctrl+-", lambda: self._timeline.zoom_out())

        # ── Hilfe ──────────────────────────────────────────────────────
        hm = mb.addMenu("Hilfe")
        self._a(hm, "Shortcuts & Info", None, self._show_about)

    def _a(self, menu, label, shortcut, slot):
        act = QAction(label, self)
        if shortcut:
            act.setShortcut(shortcut)
        act.triggered.connect(slot)
        menu.addAction(act)
        return act

    # ------------------------------------------------------------------ UI

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top_split = QSplitter(Qt.Orientation.Horizontal)
        top_split.setChildrenCollapsible(False)

        self._media_pool = MediaPool()
        self._media_pool.setMinimumWidth(200)
        self._media_pool.setMaximumWidth(320)
        top_split.addWidget(self._media_pool)

        self._preview = PreviewPlayer()
        self._preview.setMinimumWidth(400)
        top_split.addWidget(self._preview)
        top_split.setStretchFactor(0, 0)
        top_split.setStretchFactor(1, 1)

        v_split = QSplitter(Qt.Orientation.Vertical)
        v_split.setChildrenCollapsible(False)
        v_split.addWidget(top_split)

        self._timeline = TimelineWidget()
        self._timeline.setMinimumHeight(200)
        v_split.addWidget(self._timeline)
        v_split.setStretchFactor(0, 2)
        v_split.setStretchFactor(1, 1)

        root.addWidget(v_split)

    def _connect_signals(self):
        # Media pool
        self._media_pool.clip_preview_requested.connect(self._preview_media)
        self._media_pool.clip_added_to_timeline.connect(self._add_clip_to_timeline)

        # Timeline → preview
        self._timeline.position_changed.connect(self._on_timeline_seek)
        self._timeline.status_message.connect(self.statusBar().showMessage)

        # Timeline clip events
        self._timeline.clip_moved.connect(self._on_clip_changed)
        self._timeline.clip_trimmed.connect(self._on_clip_changed)
        self._timeline.clip_delete_requested.connect(self._delete_clip)
        self._timeline.clip_split_requested.connect(self._split_clip)
        self._timeline.clip_properties_requested.connect(self._show_clip_properties_for)

        # Preview → timeline playhead
        self._preview.position_updated.connect(self._timeline.set_playhead)

        # Loop markers
        self._preview.loop_in_changed.connect(self._on_loop_in)
        self._preview.loop_out_changed.connect(self._on_loop_out)

    # ------------------------------------------------------------------ drag & drop

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if is_supported_media(path):
                self._media_pool._add_file(path)
        event.acceptProposedAction()

    # ------------------------------------------------------------------ media pool slots

    @pyqtSlot(object)
    def _preview_media(self, media: MediaFile):
        self._preview.load(media.path)
        self.statusBar().showMessage(f"Preview: {media.name}  [{media.duration_str()}]")

    @pyqtSlot(object)
    def _add_clip_to_timeline(self, media: MediaFile):
        track = 2 if media.width == 0 else 0
        clips_on_track = [c for c in self._timeline.clips() if c.track == track]
        start = max((c.end_time for c in clips_on_track), default=0.0)
        clip = TimelineClip(
            media=media, track=track, start_time=start, color=CLIP_COLORS[track]
        )
        self._timeline.add_clip(clip)
        self._preview.load(media.path)
        self._push_undo()
        track_name = ["Video 1", "Video 2", "Audio 1"][track]
        self.statusBar().showMessage(
            f"'{media.name}' zu {track_name} hinzugefügt  (Start: {start:.1f} s)"
        )

    # ------------------------------------------------------------------ timeline slots

    @pyqtSlot(float)
    def _on_timeline_seek(self, seconds: float):
        clip = self._timeline.find_clip_at(seconds)
        if clip:
            offset = seconds - clip.start_time + clip.in_point
            self._preview.load(clip.media.path, seek_to=offset)
        self._timeline.set_playhead(seconds)

    @pyqtSlot(object)
    def _on_clip_changed(self, clip):
        """Called after move or trim — save undo state."""
        self._push_undo()

    @pyqtSlot(object)
    def _delete_clip(self, clip: TimelineClip):
        self._timeline.remove_clip(clip)
        self._push_undo()
        self.statusBar().showMessage(f"'{clip.display_name()}' gelöscht.")

    @pyqtSlot(object, float)
    def _split_clip(self, clip: TimelineClip, split_time: float):
        if not (clip.start_time < split_time < clip.end_time):
            self.statusBar().showMessage("Playhead liegt nicht innerhalb des Clips.")
            return
        timeline_offset = split_time - clip.start_time

        # Source position at split (within one loop cycle)
        src_duration = clip.out_point - clip.in_point
        if src_duration <= 0:
            return
        src_offset = (timeline_offset * clip.speed) % src_duration
        source_pos = clip.in_point + src_offset

        left = clip.copy()
        left.out_point = source_pos
        left.loop_count = 1

        right = clip.copy()
        right.start_time = split_time
        right.in_point = source_pos
        right.loop_count = 1

        self._timeline.remove_clip(clip)
        self._timeline.add_clip(left)
        self._timeline.add_clip(right)
        self._push_undo()
        self.statusBar().showMessage(f"'{clip.media.name}' bei {split_time:.2f} s geteilt.")

    @pyqtSlot(object)
    def _show_clip_properties_for(self, clip: TimelineClip):
        # Compute useful context durations for the "match" buttons
        audio_dur = sum(c.duration for c in self._timeline.clips() if c.track == 2)
        video_dur = sum(c.duration for c in self._timeline.clips() if c.track in (0, 1))
        dlg = ClipPropertiesDialog(
            clip,
            audio_duration=audio_dur,
            video_duration=video_dur,
            parent=self
        )
        if dlg.exec():
            self._timeline._canvas._update_min_width()
            self._timeline._canvas.update()
            self._push_undo()
            self.statusBar().showMessage(
                f"'{clip.display_name()}' aktualisiert."
            )

    # ------------------------------------------------------------------ loop markers

    @pyqtSlot(float)
    def _on_loop_in(self, t: float):
        self._timeline.set_loop_markers(t, self._preview._loop_out,
                                        self._preview._loop_enabled)

    @pyqtSlot(float)
    def _on_loop_out(self, t: float):
        self._timeline.set_loop_markers(self._preview._loop_in, t,
                                        self._preview._loop_enabled)

    # ------------------------------------------------------------------ project save / load

    def _save_project(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Projekt speichern", os.path.expanduser("~"),
            "VideoDeathCutter Project (*.vdc);;All Files (*)"
        )
        if not path:
            return
        if not path.endswith(".vdc"):
            path += ".vdc"

        media_list = []
        for m in self._media_pool.media_files():
            media_list.append({
                "path": m.path,
                "name": m.name,
                "duration": m.duration,
                "width": m.width,
                "height": m.height,
                "fps": m.fps,
                "has_audio": m.has_audio,
            })

        clip_list = []
        for c in self._timeline.clips():
            clip_list.append({
                "media_path": c.media.path,
                "track": c.track,
                "start_time": c.start_time,
                "in_point": c.in_point,
                "out_point": c.out_point,
                "color": c.color,
                "loop_count": c.loop_count,
                "speed": c.speed,
                "muted": c.muted,
            })

        data = {"version": 1, "media_pool": media_list, "timeline_clips": clip_list}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self.statusBar().showMessage(f"Projekt gespeichert: {path}")

    def _load_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Projekt öffnen", os.path.expanduser("~"),
            "VideoDeathCutter Project (*.vdc);;All Files (*)"
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Projektdatei konnte nicht gelesen werden:\n{e}")
            return

        if data.get("version", 0) != 1:
            QMessageBox.warning(self, "Versionsfehler",
                                "Unbekannte Projektversion – versuche trotzdem zu laden.")

        # Build MediaFile objects; skip missing files
        missing = []
        media_by_path: dict[str, MediaFile] = {}
        for m in data.get("media_pool", []):
            p = m.get("path", "")
            if not os.path.isfile(p):
                missing.append(p)
                continue
            mf = MediaFile(
                path=p,
                name=m.get("name", os.path.basename(p)),
                duration=m.get("duration", 0.0),
                width=m.get("width", 0),
                height=m.get("height", 0),
                fps=m.get("fps", 0.0),
                has_audio=m.get("has_audio", True),
            )
            media_by_path[p] = mf

        if missing:
            QMessageBox.warning(
                self, "Fehlende Dateien",
                "Folgende Mediendateien wurden nicht gefunden und übersprungen:\n\n"
                + "\n".join(missing)
            )

        # Reset state
        self._media_pool.clear()
        self._timeline.set_clips([])

        for mf in media_by_path.values():
            self._media_pool.add_media_file(mf)

        clips = []
        for c in data.get("timeline_clips", []):
            mp = c.get("media_path", "")
            if mp not in media_by_path:
                continue
            clip = TimelineClip(
                media=media_by_path[mp],
                track=c.get("track", 0),
                start_time=c.get("start_time", 0.0),
                in_point=c.get("in_point", 0.0),
                out_point=c.get("out_point", 0.0),
                color=c.get("color", "#2a6496"),
                loop_count=c.get("loop_count", 1),
                speed=c.get("speed", 1.0),
                muted=c.get("muted", False),
            )
            clips.append(clip)
        self._timeline.set_clips(clips)
        self._push_undo()
        self.statusBar().showMessage(f"Projekt geladen: {path}")

    # ------------------------------------------------------------------ menu actions

    def _import_media(self):
        self._media_pool._import_dialog()

    def _open_export(self):
        ExportDialog(self._timeline.clips(), self).exec()

    def _delete_selected(self):
        clip = self._timeline.selected_clip()
        if clip:
            self._delete_clip(clip)
        else:
            self.statusBar().showMessage("Kein Clip ausgewählt.")

    def _split_at_playhead(self):
        ph = self._timeline.playhead_position()
        clip = self._timeline.find_clip_at(ph)
        if clip:
            self._split_clip(clip, ph)
        else:
            self.statusBar().showMessage("Kein Clip am Playhead auf Video 1.")

    def _show_clip_properties(self):
        clip = self._timeline.selected_clip()
        if clip:
            self._show_clip_properties_for(clip)
        else:
            self.statusBar().showMessage("Kein Clip ausgewählt.")

    def _show_about(self):
        QMessageBox.about(self, "Video Editor – Shortcuts", """\
<b>Tastenkürzel</b><br><br>
<table>
<tr><td><b>Ctrl+I</b></td><td>Medien importieren</td></tr>
<tr><td><b>Ctrl+E</b></td><td>Exportieren</td></tr>
<tr><td><b>Ctrl+Z / Y</b></td><td>Rückgängig / Wiederholen</td></tr>
<tr><td><b>Ctrl+K</b></td><td>Clip am Playhead teilen</td></tr>
<tr><td><b>Entf</b></td><td>Ausgewählten Clip löschen</td></tr>
<tr><td><b>Ctrl+P</b></td><td>Clip-Eigenschaften (Loop, Tempo, Mute)</td></tr>
<tr><td><b>Space</b></td><td>Play / Pause</td></tr>
<tr><td><b>I / O</b></td><td>Loop IN / OUT setzen</td></tr>
<tr><td><b>L</b></td><td>Loop ein/aus</td></tr>
<tr><td><b>Ctrl+/−</b></td><td>Timeline zoomen</td></tr>
</table><br>
<b>Timeline</b><br>
Clip-Ränder ziehen = Trimmen<br>
Clip verschieben = Drag &amp; Drop<br>
Rechtsklick auf Clip = Kontextmenü<br>
Doppelklick auf Clip = Eigenschaften<br><br>
<b>Loop-Export-Beispiel</b><br>
5-Sek. Video + 5-Min. Audio →<br>
Export → Track-Sync → "Video loopen"
""")

    # ------------------------------------------------------------------ undo / redo

    def _push_undo(self):
        """Save current timeline state onto the undo stack."""
        state = [c.copy() for c in self._timeline.clips()]
        # Truncate redo history
        self._undo_stack = self._undo_stack[:self._undo_index + 1]
        self._undo_stack.append(state)
        if len(self._undo_stack) > 60:
            self._undo_stack.pop(0)
        else:
            self._undo_index += 1
        self._update_undo_actions()

    def _undo(self):
        if self._undo_index > 0:
            self._undo_index -= 1
            self._restore(self._undo_stack[self._undo_index])
            self.statusBar().showMessage("Rückgängig.")
        self._update_undo_actions()

    def _redo(self):
        if self._undo_index < len(self._undo_stack) - 1:
            self._undo_index += 1
            self._restore(self._undo_stack[self._undo_index])
            self.statusBar().showMessage("Wiederholt.")
        self._update_undo_actions()

    def _restore(self, state: list[TimelineClip]):
        self._timeline.set_clips(state)

    def _update_undo_actions(self):
        self._undo_action.setEnabled(self._undo_index > 0)
        self._redo_action.setEnabled(self._undo_index < len(self._undo_stack) - 1)

    # ------------------------------------------------------------------ keyboard

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key in (Qt.Key.Key_I, Qt.Key.Key_O, Qt.Key.Key_L, Qt.Key.Key_Space):
            self._preview.handle_key(key)
        else:
            super().keyPressEvent(event)
