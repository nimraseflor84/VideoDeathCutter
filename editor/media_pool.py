import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QListWidgetItem, QPushButton, QLabel, QFileDialog, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from .models import MediaFile
from .utils import get_media_info, is_supported_media


class MediaPool(QWidget):
    """Left panel: imported media files."""

    clip_added_to_timeline = pyqtSignal(object)  # MediaFile
    clip_preview_requested = pyqtSignal(object)  # MediaFile

    def __init__(self, parent=None):
        super().__init__(parent)
        self._media_files: list[MediaFile] = []
        self._setup_ui()
        self.setAcceptDrops(True)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        title = QLabel("Media Pool")
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: #ccc;")
        layout.addWidget(title)

        btn_layout = QHBoxLayout()
        self._import_btn = QPushButton("Import (Ctrl+I)")
        self._import_btn.clicked.connect(self._import_dialog)
        btn_layout.addWidget(self._import_btn)
        layout.addLayout(btn_layout)

        self._list = QListWidget()
        self._list.setDragEnabled(True)
        self._list.setToolTip("Click to preview · Double-click to add to Timeline")
        self._list.itemClicked.connect(self._on_single_click)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._list)

        hint = QLabel("Drag files here or use Import")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(hint)

    def _import_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Media",
            os.path.expanduser("~"),
            "Media Files (*.mp4 *.mov *.mkv *.avi *.wmv *.flv *.m4v *.webm "
            "*.ts *.mts *.m2ts *.mp3 *.aac *.wav *.flac *.m4a *.ogg);;All Files (*)",
        )
        for path in paths:
            self._add_file(path)

    def _add_file(self, path: str):
        if not os.path.isfile(path):
            return
        if not is_supported_media(path):
            return
        # Avoid duplicates
        if any(m.path == path for m in self._media_files):
            return

        info = get_media_info(path)
        if info is None:
            QMessageBox.warning(self, "Import Error",
                                f"Could not read media info for:\n{path}")
            return

        media = MediaFile(
            path=path,
            name=os.path.basename(path),
            duration=info["duration"],
            width=info["width"],
            height=info["height"],
            fps=info["fps"],
            has_audio=info["has_audio"],
        )
        self._media_files.append(media)

        item = QListWidgetItem(f"{media.name}  [{media.duration_str()}]")
        item.setData(Qt.ItemDataRole.UserRole, media)
        item.setToolTip(
            f"{media.path}\n{media.width}x{media.height} @ {media.fps:.2f}fps\n"
            f"Duration: {media.duration_str()}"
        )
        self._list.addItem(item)

    def _on_single_click(self, item: QListWidgetItem):
        media = item.data(Qt.ItemDataRole.UserRole)
        if media:
            self.clip_preview_requested.emit(media)

    def _on_double_click(self, item: QListWidgetItem):
        media = item.data(Qt.ItemDataRole.UserRole)
        if media:
            self.clip_added_to_timeline.emit(media)

    # --- Drag & Drop ---

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            self._add_file(path)
        event.acceptProposedAction()

    def media_files(self) -> list[MediaFile]:
        return list(self._media_files)
