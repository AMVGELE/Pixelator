from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pixelator.ai.super_resolution import SuperResolutionOptions, SuperResolutionResult
from pixelator.image_io import load_static_image


class SuperResolutionPanel(QWidget):
    upscaleRequested = Signal(object)
    useQueueImageRequested = Signal()
    useRecentQwenRequested = Signal()
    openOutputDirectoryRequested = Signal()
    addOutputToQueueRequested = Signal(str)
    setReferenceRequested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._source_path: Path | None = None
        self._output_path: Path | None = None

        self.local_image_button = QPushButton("Local Image")
        self.queue_image_button = QPushButton("Current Queue")
        self.recent_qwen_button = QPushButton("Recent Qwen")
        self.source_label = QLabel("No source selected")
        self.source_label.setWordWrap(True)

        self.factor_combo = QComboBox()
        for factor in (1, 2, 3, 4):
            self.factor_combo.addItem(str(factor), factor)
        self.factor_combo.setCurrentIndex(self.factor_combo.findData(2))
        self.format_combo = QComboBox()
        for output_format in ("png", "jpg", "bmp"):
            self.format_combo.addItem(output_format, output_format)
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(95)

        self.run_button = QPushButton("Run Super Resolution")
        self.open_output_button = QPushButton("Open Output Dir")
        self.add_to_queue_button = QPushButton("Add To Queue")
        self.set_reference_button = QPushButton("Set Reference")
        self.add_to_queue_button.setEnabled(False)
        self.set_reference_button.setEnabled(False)

        self.status_label = QLabel("idle")
        self.before_preview = self._preview_label("Before")
        self.after_preview = self._preview_label("After")
        self.before_size_label = QLabel("Before: -")
        self.after_size_label = QLabel("After: -")
        self.output_path_label = QLabel("Output: -")
        self.output_path_label.setWordWrap(True)
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)

        self._build_layout()
        self._connect_signals()
        self._sync_quality_enabled()

    def options(self) -> SuperResolutionOptions:
        if self._source_path is None:
            raise ValueError("Select a source image first.")
        return SuperResolutionOptions(
            source_path=self._source_path,
            upscale_factor=int(self.factor_combo.currentData() or 2),
            output_format=str(self.format_combo.currentData() or "png"),
            jpg_quality=self.quality_spin.value(),
        )

    def set_source_path(self, path: str | Path, label: str | None = None) -> None:
        source_path = Path(path)
        image = load_static_image(source_path)
        self._source_path = source_path
        self._output_path = None
        self.source_label.setText(label or str(source_path))
        self.status_label.setText("idle")
        self.before_size_label.setText(f"Before: {image.width} x {image.height}")
        self.after_size_label.setText("After: -")
        self.output_path_label.setText("Output: -")
        self.error_label.setText("")
        self.add_to_queue_button.setEnabled(False)
        self.set_reference_button.setEnabled(False)
        self._set_preview(self.before_preview, source_path)
        self.after_preview.setText("After")

    def set_running(self, running: bool) -> None:
        self.run_button.setEnabled(not running)
        self.local_image_button.setEnabled(not running)
        self.queue_image_button.setEnabled(not running)
        self.recent_qwen_button.setEnabled(not running)
        self.status_label.setText("running" if running else self.status_label.text())

    def set_result(self, result: SuperResolutionResult) -> None:
        self._output_path = result.output_path
        self.status_label.setText("succeeded")
        self.after_size_label.setText(f"After: {result.after_size[0]} x {result.after_size[1]}")
        self.output_path_label.setText(f"Output: {result.output_path}")
        self.error_label.setText("")
        self._set_preview(self.after_preview, result.output_path)
        self.add_to_queue_button.setEnabled(True)
        self.set_reference_button.setEnabled(True)

    def set_error(self, message: str) -> None:
        self.status_label.setText("failed")
        self.error_label.setText(message)

    def _build_layout(self) -> None:
        title = QLabel("Super Resolution / 超分")
        title.setObjectName("panelTitle")

        source_group = QGroupBox("Input Source")
        source_buttons = QHBoxLayout()
        source_buttons.addWidget(self.local_image_button)
        source_buttons.addWidget(self.queue_image_button)
        source_buttons.addWidget(self.recent_qwen_button)
        source_layout = QVBoxLayout(source_group)
        source_layout.addLayout(source_buttons)
        source_layout.addWidget(self.source_label)

        parameter_group = QGroupBox("Parameters")
        parameter_form = QFormLayout(parameter_group)
        parameter_form.addRow("UpscaleFactor", self.factor_combo)
        parameter_form.addRow("OutputFormat", self.format_combo)
        parameter_form.addRow("jpg quality", self.quality_spin)

        preview_group = QGroupBox("Preview")
        preview_grid = QGridLayout(preview_group)
        preview_grid.addWidget(self.before_preview, 0, 0)
        preview_grid.addWidget(self.after_preview, 0, 1)
        preview_grid.addWidget(self.before_size_label, 1, 0)
        preview_grid.addWidget(self.after_size_label, 1, 1)
        preview_grid.addWidget(self.output_path_label, 2, 0, 1, 2)
        preview_grid.addWidget(self.error_label, 3, 0, 1, 2)

        action_row = QHBoxLayout()
        action_row.addWidget(self.run_button)
        action_row.addWidget(self.open_output_button)
        action_row.addWidget(self.add_to_queue_button)
        action_row.addWidget(self.set_reference_button)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(source_group)
        layout.addWidget(parameter_group)
        layout.addWidget(QLabel("Status"))
        layout.addWidget(self.status_label)
        layout.addWidget(preview_group)
        layout.addLayout(action_row)
        layout.addStretch(1)

    def _connect_signals(self) -> None:
        self.local_image_button.clicked.connect(self._choose_local_image)
        self.queue_image_button.clicked.connect(self.useQueueImageRequested.emit)
        self.recent_qwen_button.clicked.connect(self.useRecentQwenRequested.emit)
        self.open_output_button.clicked.connect(self.openOutputDirectoryRequested.emit)
        self.run_button.clicked.connect(self._on_run_clicked)
        self.add_to_queue_button.clicked.connect(self._on_add_to_queue_clicked)
        self.set_reference_button.clicked.connect(self._on_set_reference_clicked)
        self.format_combo.currentIndexChanged.connect(lambda index: self._sync_quality_enabled())

    def _choose_local_image(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Select super-resolution source",
            "",
            "Image files (*.png *.jpg *.jpeg *.webp *.bmp *.tga *.tif *.tiff);;All files (*.*)",
        )
        if selected:
            try:
                self.set_source_path(selected)
            except Exception as exc:  # noqa: BLE001 - surface image loading errors in the panel.
                self.set_error(str(exc))

    def _on_run_clicked(self) -> None:
        try:
            options = self.options()
        except ValueError as exc:
            self.set_error(str(exc))
            return
        self.upscaleRequested.emit(options)

    def _on_add_to_queue_clicked(self) -> None:
        if self._output_path is not None:
            self.addOutputToQueueRequested.emit(str(self._output_path))

    def _on_set_reference_clicked(self) -> None:
        if self._output_path is not None:
            self.setReferenceRequested.emit(str(self._output_path))

    def _sync_quality_enabled(self) -> None:
        self.quality_spin.setEnabled(str(self.format_combo.currentData() or "png") == "jpg")

    def _set_preview(self, label: QLabel, path: Path) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            label.setText(path.name)
            return
        label.setPixmap(pixmap.scaled(132, 132, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def _preview_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedSize(QSize(140, 140))
        label.setFrameShape(QFrame.Shape.Box)
        return label
