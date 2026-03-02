import sys
import traceback
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt

from editor.main_window import MainWindow


class Application(QApplication):
    """QApplication-Unterklasse, die Python-Exceptions in Slots abfängt.

    In PyQt6 >= 6.x führt eine unbehandelte Exception in einem Slot zu
    QMessageLogger::fatal() → abort(). Durch Überschreiben von notify()
    werden alle solchen Exceptions als Fehlerdialog angezeigt.
    """

    def notify(self, obj, event):
        try:
            return super().notify(obj, event)
        except Exception:
            msg = traceback.format_exc()
            QMessageBox.critical(
                None,
                "Unerwarteter Fehler",
                f"Ein Fehler ist aufgetreten:\n\n{msg}",
            )
            return False


DARK_STYLE = """
QWidget {
    background-color: #1a1a1f;
    color: #e0e0e0;
    font-family: -apple-system, "Segoe UI", sans-serif;
    font-size: 12px;
}
QMenuBar {
    background-color: #111116;
    color: #e0e0e0;
    border-bottom: 1px solid #c0392b;
}
QMenuBar::item:selected {
    background-color: #c0392b;
    color: #fff;
}
QMenu {
    background-color: #1e1e26;
    color: #e0e0e0;
    border: 1px solid #c0392b;
}
QMenu::item:selected {
    background-color: #c0392b;
    color: #fff;
}
QPushButton {
    background-color: #252530;
    color: #e0e0e0;
    border: 1px solid #444;
    border-radius: 4px;
    padding: 4px 10px;
}
QPushButton:hover {
    background-color: #2e2e3e;
    border-color: #c0392b;
    color: #fff;
}
QPushButton:pressed {
    background-color: #c0392b;
    color: #fff;
}
QPushButton:checked {
    background-color: #8b1a1a;
    border-color: #c0392b;
    color: #fff;
}
QPushButton:disabled {
    color: #555;
    border-color: #2a2a2a;
}
QGroupBox {
    border: 1px solid #c0392b;
    border-radius: 5px;
    margin-top: 8px;
    padding-top: 4px;
    color: #c0392b;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: #c0392b;
}
QListWidget {
    background-color: #1e1e26;
    border: 1px solid #333;
    border-radius: 4px;
    alternate-background-color: #222230;
}
QListWidget::item:selected {
    background-color: #8b1a1a;
    color: #fff;
}
QListWidget::item:hover {
    background-color: #2a2a3a;
}
QScrollBar:horizontal {
    background: #1a1a1f;
    height: 10px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background: #c0392b;
    border-radius: 5px;
    min-width: 20px;
}
QScrollBar::handle:horizontal:hover {
    background: #e74c3c;
}
QScrollBar:vertical {
    background: #1a1a1f;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #c0392b;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::add-line, QScrollBar::sub-line {
    width: 0px;
    height: 0px;
}
QSlider::groove:horizontal {
    background: #2a2a3a;
    height: 4px;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #c0392b;
    width: 12px;
    height: 12px;
    border-radius: 6px;
    margin: -4px 0;
}
QSlider::sub-page:horizontal {
    background: #c0392b;
    border-radius: 2px;
}
QComboBox {
    background-color: #252530;
    color: #e0e0e0;
    border: 1px solid #444;
    border-radius: 4px;
    padding: 3px 8px;
}
QComboBox:hover {
    border-color: #c0392b;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #1e1e26;
    color: #e0e0e0;
    selection-background-color: #c0392b;
    border: 1px solid #c0392b;
}
QSpinBox {
    background-color: #252530;
    color: #e0e0e0;
    border: 1px solid #444;
    border-radius: 4px;
    padding: 3px 8px;
}
QSpinBox:hover {
    border-color: #c0392b;
}
QLineEdit {
    background-color: #1e1e26;
    color: #e0e0e0;
    border: 1px solid #444;
    border-radius: 4px;
    padding: 4px 8px;
}
QLineEdit:focus {
    border-color: #c0392b;
}
QDialog {
    background-color: #1a1a1f;
}
QStatusBar {
    background-color: #111116;
    color: #888;
    border-top: 2px solid #c0392b;
}
QSplitter::handle {
    background-color: #c0392b;
}
QSplitter::handle:horizontal {
    width: 2px;
}
QSplitter::handle:vertical {
    height: 2px;
}
QProgressBar {
    background-color: #252530;
    border: 1px solid #444;
    border-radius: 4px;
    text-align: center;
    color: #fff;
}
QProgressBar::chunk {
    background-color: #c0392b;
    border-radius: 3px;
}
QProgressDialog {
    background-color: #1a1a1f;
    color: #e0e0e0;
}
QDialogButtonBox QPushButton {
    min-width: 80px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #555;
    border-radius: 3px;
    background: #252530;
}
QCheckBox::indicator:checked {
    background: #c0392b;
    border-color: #c0392b;
}
QToolTip {
    background-color: #1e1e26;
    color: #e0e0e0;
    border: 1px solid #c0392b;
    padding: 4px;
}
"""


def main():
    app = Application(sys.argv)
    app.setApplicationName("VideoDeathCutter")
    app.setOrganizationName("VideoDeathCutter")
    app.setStyleSheet(DARK_STYLE)

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#1a1a1f"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e0e0e0"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#1e1e26"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#222230"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e0e0e0"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#252530"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e0e0e0"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#c0392b"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#fff"))
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
