from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from pixelator.gui.models import JobQueue
from pixelator.gui.queue_panel import QueuePanel
from pixelator.gui.settings_panel import SettingsPanel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.queue = JobQueue()
        self.queue_panel = QueuePanel()
        self.settings_panel = SettingsPanel()
        self.preview_placeholder = QLabel("Drop or add a video to preview")
        self.preview_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_placeholder.setMinimumSize(560, 360)
        self.preview_placeholder.setFrameShape(QFrame.Shape.StyledPanel)

        self.trim_start_spin = QDoubleSpinBox()
        self.trim_start_spin.setRange(0.0, 24 * 60 * 60.0)
        self.trim_start_spin.setDecimals(3)
        self.trim_start_spin.setSuffix(" s")

        self.trim_end_spin = QDoubleSpinBox()
        self.trim_end_spin.setRange(0.0, 24 * 60 * 60.0)
        self.trim_end_spin.setDecimals(3)
        self.trim_end_spin.setSuffix(" s")

        self.scrubber_slider = QSlider(Qt.Orientation.Horizontal)
        self.scrubber_slider.setRange(0, 1000)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)

        self._build_layout()
        self._apply_style()
        self.setWindowTitle("Pixelator Desktop")
        self.setMinimumSize(1280, 720)
        self.statusBar().showMessage("Ready")

    def _build_layout(self) -> None:
        trim_row = QHBoxLayout()
        trim_row.addWidget(QLabel("Start"))
        trim_row.addWidget(self.trim_start_spin)
        trim_row.addWidget(QLabel("End"))
        trim_row.addWidget(self.trim_end_spin)

        preview_layout = QVBoxLayout()
        preview_layout.addWidget(QLabel("Preview"))
        preview_layout.addWidget(self.preview_placeholder, 1)
        preview_layout.addWidget(self.scrubber_slider)
        preview_layout.addLayout(trim_row)

        preview_widget = QWidget()
        preview_widget.setLayout(preview_layout)

        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.addWidget(self.queue_panel)
        top_splitter.addWidget(preview_widget)
        top_splitter.addWidget(self.settings_panel)
        top_splitter.setSizes([260, 680, 320])

        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(self.log_view)
        main_splitter.setSizes([560, 160])

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.addWidget(main_splitter)
        self.setCentralWidget(root)

    def append_log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #202326;
                color: #e5e7eb;
                font-size: 12px;
            }
            QLabel#panelTitle {
                font-weight: 600;
                padding: 2px 0 6px 0;
            }
            QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
                min-height: 24px;
            }
            QPlainTextEdit, QListWidget, QLabel[frameShape="6"] {
                background: #151719;
                border: 1px solid #3a3f45;
            }
            """
        )
