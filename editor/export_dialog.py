import os
import subprocess
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QSlider,
    QFileDialog, QProgressDialog, QMessageBox, QDialogButtonBox,
    QGroupBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from .models import TimelineClip
from .utils import find_ffmpeg


class ExportWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, cmd: list[str], duration: float):
        super().__init__()
        self._cmd = cmd
        self._duration = duration
        self._cancelled = False

    def run(self):
        try:
            proc = subprocess.Popen(
                self._cmd,
                stderr=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                text=True,
            )
            for line in proc.stderr:
                if self._cancelled:
                    proc.terminate()
                    self.finished.emit(False, "Abgebrochen.")
                    return
                if "time=" in line:
                    try:
                        ts = line.split("time=")[1].split()[0]
                        h, m, s = ts.split(":")
                        secs = float(h) * 3600 + float(m) * 60 + float(s)
                        pct = int(min(99, secs / self._duration * 100)) \
                            if self._duration > 0 else 0
                        self.progress.emit(pct)
                    except Exception:
                        pass
            proc.wait()
            if proc.returncode == 0:
                self.progress.emit(100)
                self.finished.emit(True, "Export erfolgreich abgeschlossen.")
            else:
                self.finished.emit(False, f"FFmpeg Fehler (Code {proc.returncode})")
        except Exception as e:
            self.finished.emit(False, str(e))

    def cancel(self):
        self._cancelled = True


class ExportDialog(QDialog):
    def __init__(self, clips: list[TimelineClip], parent=None):
        super().__init__(parent)
        self._all_clips = clips
        self._video_clips = [c for c in clips if c.track in (0, 1)]
        self._audio_clips = [c for c in clips if c.track == 2]
        self._worker: Optional[ExportWorker] = None
        self.setWindowTitle("Video exportieren")
        self.setModal(True)
        self.resize(520, 520)
        self._setup_ui()

    # ------------------------------------------------------------------ UI

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ── Output ────────────────────────────────────────────────────
        out_group = QGroupBox("Ausgabe")
        out_form = QFormLayout(out_group)

        path_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Ausgabedatei wählen…")
        path_row.addWidget(self._path_edit)
        browse_btn = QPushButton("…")
        browse_btn.setFixedWidth(32)
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(browse_btn)
        out_form.addRow("Datei:", path_row)

        self._format_combo = QComboBox()
        self._format_combo.addItems(["MP4", "MOV", "MKV"])
        self._format_combo.currentTextChanged.connect(self._update_extension)
        out_form.addRow("Format:", self._format_combo)
        layout.addWidget(out_group)

        # ── Codec & Qualität ──────────────────────────────────────────
        codec_group = QGroupBox("Codec & Qualität")
        codec_form = QFormLayout(codec_group)

        self._codec_combo = QComboBox()
        self._codec_combo.addItems(["H.264 (libx264)", "H.265 (libx265)", "ProRes (Mac)"])
        codec_form.addRow("Codec:", self._codec_combo)

        self._res_combo = QComboBox()
        self._res_combo.addItems(["Original", "3840×2160 (4K)", "1920×1080 (1080p)",
                                   "1280×720 (720p)"])
        codec_form.addRow("Auflösung:", self._res_combo)

        crf_row = QHBoxLayout()
        self._crf_slider = QSlider(Qt.Orientation.Horizontal)
        self._crf_slider.setRange(0, 51)
        self._crf_slider.setValue(18)
        self._crf_label = QLabel("18")
        self._crf_slider.valueChanged.connect(lambda v: self._crf_label.setText(str(v)))
        crf_row.addWidget(self._crf_slider)
        crf_row.addWidget(self._crf_label)
        crf_hint = QLabel("(0 = beste Qualität, 51 = kleinste Datei)")
        crf_hint.setStyleSheet("color:#666; font-size:10px;")
        codec_form.addRow("Qualität (CRF):", crf_row)
        codec_form.addRow("", crf_hint)
        layout.addWidget(codec_group)

        # ── Track-Synchronisation ─────────────────────────────────────
        sync_group = QGroupBox("Track-Synchronisation  (Loop-Funktion)")
        sync_form = QFormLayout(sync_group)

        self._sync_combo = QComboBox()
        self._sync_combo.addItems([
            "Kein Loop  (Clips exakt wie in der Timeline)",
            "Video loopen  →  Audio-Länge füllen",
            "Audio loopen  →  Video-Länge füllen",
            "Kürzeren Track an längeren anpassen (automatisch)",
        ])
        sync_form.addRow("Modus:", self._sync_combo)

        hint = QLabel(
            "Beispiel: 5-Sek. Video + 5-Min. Audio → \"Video loopen\" "
            "wiederholt das Video 60× und füllt die volle Audio-Länge."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#888; font-size:11px;")
        sync_form.addRow("", hint)
        layout.addWidget(sync_group)

        # ── Info ──────────────────────────────────────────────────────
        vdur = sum(c.duration for c in self._video_clips)
        adur = sum(c.duration for c in self._audio_clips)
        info = QLabel(
            f"Video-Clips: {len(self._video_clips)}  ({vdur:.1f} s)  ·  "
            f"Audio-Clips: {len(self._audio_clips)}  ({adur:.1f} s)"
        )
        info.setStyleSheet("color:#888; font-size:11px;")
        layout.addWidget(info)

        if not self._video_clips:
            warn = QLabel("⚠  Keine Video-Clips in der Timeline.")
            warn.setStyleSheet("color:#f80; font-size:12px;")
            layout.addWidget(warn)

        layout.addStretch()

        # Buttons
        btn_box = QDialogButtonBox()
        self._export_btn = btn_box.addButton(
            "Exportieren", QDialogButtonBox.ButtonRole.AcceptRole)
        self._export_btn.clicked.connect(self._start_export)
        self._export_btn.setEnabled(bool(self._video_clips))
        btn_box.addButton("Abbrechen", QDialogButtonBox.ButtonRole.RejectRole
                          ).clicked.connect(self.reject)
        layout.addWidget(btn_box)

    def _browse(self):
        fmt = self._format_combo.currentText().lower()
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportdatei wählen",
            os.path.expanduser(f"~/Desktop/export.{fmt}"),
            f"Video (*.{fmt});;Alle Dateien (*)"
        )
        if path:
            self._path_edit.setText(path)

    def _update_extension(self, fmt: str):
        p = self._path_edit.text()
        if p:
            self._path_edit.setText(os.path.splitext(p)[0] + "." + fmt.lower())

    # ------------------------------------------------------------------ FFmpeg

    def _build_cmd(self, output_path: str) -> tuple[list[str], float]:
        ffmpeg, _ = find_ffmpeg()

        codec_text = self._codec_combo.currentText()
        is_lossy = "prores" not in codec_text.lower()
        codec_map = {
            "H.264 (libx264)": ["-c:v", "libx264", "-preset", "slow"],
            "H.265 (libx265)": ["-c:v", "libx265", "-preset", "slow"],
            "ProRes (Mac)":    ["-c:v", "prores_ks", "-profile:v", "3"],
        }
        codec_args = codec_map.get(codec_text, ["-c:v", "libx264", "-preset", "slow"])
        crf_args = ["-crf", str(self._crf_slider.value())] if is_lossy else []
        pix_fmt = ["format=yuv420p"] if is_lossy else []

        res_map = {
            "3840×2160 (4K)":    "3840:2160",
            "1920×1080 (1080p)": "1920:1080",
            "1280×720 (720p)":   "1280:720",
        }
        scale = [f"scale={res_map[r]}"]  \
            if (r := self._res_combo.currentText()) in res_map else []

        sync_mode = self._sync_combo.currentIndex()
        v_clips = sorted(self._video_clips, key=lambda c: c.start_time)
        a_clips = sorted(self._audio_clips, key=lambda c: c.start_time)

        video_dur = sum(c.duration for c in v_clips)
        audio_dur = sum(c.duration for c in a_clips)

        # Effective target durations based on sync mode
        if sync_mode == 0:
            v_target = video_dur
            a_target = audio_dur
        elif sync_mode == 1:  # loop video to fill audio
            v_target = audio_dur if audio_dur > 0 else video_dur
            a_target = audio_dur
        elif sync_mode == 2:  # loop audio to fill video
            v_target = video_dur
            a_target = video_dur if video_dur > 0 else audio_dur
        else:  # auto
            longer = max(video_dur, audio_dur)
            v_target = longer
            a_target = longer

        total_duration = max(v_target, a_target) if (v_clips or a_clips) else 0

        cmd = [ffmpeg, "-y"]

        # ── inputs ────────────────────────────────────────────────────
        for clip in v_clips:
            lc = clip.loop_count
            if sync_mode != 0:
                # In loop-sync mode: loop every video clip infinitely, cut later
                cmd += ["-stream_loop", "-1"]
            elif lc == -1:
                cmd += ["-stream_loop", "-1"]
            elif lc > 1:
                cmd += ["-stream_loop", str(lc - 1)]
            cmd += ["-ss", str(clip.in_point), "-i", clip.media.path]

        for clip in a_clips:
            lc = clip.loop_count
            if sync_mode in (2, 3):
                cmd += ["-stream_loop", "-1"]
            elif lc == -1:
                cmd += ["-stream_loop", "-1"]
            elif lc > 1:
                cmd += ["-stream_loop", str(lc - 1)]
            cmd += ["-ss", str(clip.in_point), "-i", clip.media.path]

        nv = len(v_clips)
        na = len(a_clips)
        n_total = nv + na
        post = scale + pix_fmt

        if n_total == 0:
            raise RuntimeError("Keine Clips zum Exportieren vorhanden.")

        # ── filter_complex ────────────────────────────────────────────
        fc_parts: list[str] = []

        if nv == 1 and na == 0:
            # Single video clip (possibly looping) — simple case
            clip = v_clips[0]
            if sync_mode != 0 or clip.loop_count != 1:
                # Limit duration via trim in filter
                fc_parts.append(
                    f"[0:v]trim=duration={v_target:.4f},setpts=PTS-STARTPTS[tv]"
                )
                if clip.media.has_audio and not clip.muted:
                    fc_parts.append(
                        f"[0:a]atrim=duration={v_target:.4f},asetpts=PTS-STARTPTS[ta]"
                    )
                    if post:
                        fc_parts.append(f"[tv]{','.join(post)}[outv]")
                        fc_parts.append("[ta]anull[outa]")
                    else:
                        fc_parts.append("[tv]null[outv]")
                        fc_parts.append("[ta]anull[outa]")
                else:
                    if post:
                        fc_parts.append(f"[tv]{','.join(post)}[outv]")
                    else:
                        fc_parts.append("[tv]null[outv]")
                    fc_parts.append("anullsrc=r=44100:cl=stereo[outa]")

                cmd += ["-filter_complex", ";".join(fc_parts),
                        "-map", "[outv]", "-map", "[outa]"]
            else:
                # Completely normal single clip
                vf = post
                if vf:
                    cmd += ["-vf", ",".join(vf)]
                if clip.muted:
                    cmd += ["-an"]
                else:
                    cmd += ["-c:a", "aac", "-b:a", "256k"]
                cmd += ["-t", str(clip.duration)] + codec_args + crf_args
                cmd += ["-c:a", "aac", "-b:a", "256k", output_path]
                return cmd, clip.duration

        elif nv >= 1 and na == 0:
            # Multiple video clips, no separate audio
            for i, clip in enumerate(v_clips):
                dur = v_target / nv if sync_mode != 0 else clip.duration
                fc_parts.append(
                    f"[{i}:v]trim=duration={dur:.4f},setpts=PTS-STARTPTS[v{i}]"
                )
                if clip.media.has_audio and not clip.muted:
                    fc_parts.append(
                        f"[{i}:a]atrim=duration={dur:.4f},asetpts=PTS-STARTPTS[a{i}]"
                    )
                else:
                    fc_parts.append(
                        f"anullsrc=r=44100:cl=stereo:d={dur:.4f}[a{i}]"
                    )
            concat_in = "".join(f"[v{i}][a{i}]" for i in range(nv))
            concat_out = "[cv][outa]"
            fc_parts.append(f"{concat_in}concat=n={nv}:v=1:a=1{concat_out}")
            if post:
                fc_parts.append(f"[cv]{','.join(post)}[outv]")
            else:
                fc_parts.append("[cv]null[outv]")
            cmd += ["-filter_complex", ";".join(fc_parts),
                    "-map", "[outv]", "-map", "[outa]"]

        elif nv >= 1 and na >= 1:
            # Video + separate audio tracks
            for i, clip in enumerate(v_clips):
                dur = v_target / nv if sync_mode in (1, 3) else clip.duration
                fc_parts.append(
                    f"[{i}:v]trim=duration={dur:.4f},setpts=PTS-STARTPTS[v{i}]"
                )
            concat_v_in = "".join(f"[v{i}]" for i in range(nv))
            if nv > 1:
                fc_parts.append(f"{concat_v_in}concat=n={nv}:v=1:a=0[cv]")
            else:
                fc_parts.append(f"[v0]null[cv]")

            for j, clip in enumerate(a_clips):
                dur = a_target / na if sync_mode in (2, 3) else clip.duration
                idx = nv + j
                fc_parts.append(
                    f"[{idx}:a]atrim=duration={dur:.4f},asetpts=PTS-STARTPTS[a{j}]"
                )
            concat_a_in = "".join(f"[a{j}]" for j in range(na))
            if na > 1:
                fc_parts.append(f"{concat_a_in}concat=n={na}:v=0:a=1[outa]")
            else:
                fc_parts.append(f"[a0]anull[outa]")

            if post:
                fc_parts.append(f"[cv]{','.join(post)}[outv]")
            else:
                fc_parts.append("[cv]null[outv]")

            cmd += ["-filter_complex", ";".join(fc_parts),
                    "-map", "[outv]", "-map", "[outa]"]

        else:
            # Only audio clips
            for j, clip in enumerate(a_clips):
                dur = a_target / na if sync_mode != 0 else clip.duration
                fc_parts.append(
                    f"[{j}:a]atrim=duration={dur:.4f},asetpts=PTS-STARTPTS[a{j}]"
                )
            concat_a_in = "".join(f"[a{j}]" for j in range(na))
            if na > 1:
                fc_parts.append(f"{concat_a_in}concat=n={na}:v=0:a=1[outa]")
            else:
                fc_parts.append(f"[a0]anull[outa]")
            cmd += ["-filter_complex", ";".join(fc_parts), "-map", "[outa]",
                    "-vn"]
            cmd += ["-c:a", "aac", "-b:a", "256k", output_path]
            return cmd, total_duration

        # Apply speed per clip (simple: use setpts for video speed)
        # (speed already factored into source_duration via model, trim handles it)

        cmd += codec_args + crf_args + ["-c:a", "aac", "-b:a", "256k", output_path]
        return cmd, total_duration

    # ------------------------------------------------------------------ export

    def _start_export(self):
        path = self._path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "Export", "Bitte Ausgabedatei wählen.")
            return
        try:
            cmd, duration = self._build_cmd(path)
        except RuntimeError as e:
            QMessageBox.critical(self, "FFmpeg Fehler", str(e))
            return

        progress = QProgressDialog("Exportiere…", "Abbrechen", 0, 100, self)
        progress.setWindowTitle("Export")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        self._worker = ExportWorker(cmd, duration)
        self._worker.progress.connect(progress.setValue)
        self._worker.finished.connect(
            lambda ok, msg: self._export_done(ok, msg, progress))
        progress.canceled.connect(self._worker.cancel)
        self._worker.start()

    def _export_done(self, ok: bool, msg: str, progress: QProgressDialog):
        progress.close()
        if ok:
            QMessageBox.information(self, "Export abgeschlossen", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "Export fehlgeschlagen", msg)
