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

        self.local_image_button = QPushButton("本地图像")
        self.queue_image_button = QPushButton("当前队列")
        self.recent_qwen_button = QPushButton("最近 Qwen")
        self.source_label = QLabel("未选择来源")
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

        self.run_button = QPushButton("开始超分")
        self.open_output_button = QPushButton("打开输出目录")
        self.add_to_queue_button = QPushButton("加入队列")
        self.set_reference_button = QPushButton("设为色盘参考")
        self.add_to_queue_button.setEnabled(False)
        self.set_reference_button.setEnabled(False)

        self.status_label = QLabel("空闲")
        self.before_preview = self._preview_label("原图")
        self.after_preview = self._preview_label("结果")
        self.before_size_label = QLabel("原图：-")
        self.after_size_label = QLabel("结果：-")
        self.output_path_label = QLabel("输出：-")
        self.output_path_label.setWordWrap(True)
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)

        self._build_layout()
        self._connect_signals()
        self._sync_quality_enabled()

    def options(self) -> SuperResolutionOptions:
        if self._source_path is None:
            raise ValueError("请先选择来源图像。")
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
        self.status_label.setText("空闲")
        self.before_size_label.setText(f"原图：{image.width} x {image.height}")
        self.after_size_label.setText("结果：-")
        self.output_path_label.setText("输出：-")
        self.error_label.setText("")
        self.add_to_queue_button.setEnabled(False)
        self.set_reference_button.setEnabled(False)
        self._set_preview(self.before_preview, source_path)
        self.after_preview.setText("结果")

    def set_running(self, running: bool) -> None:
        self.run_button.setEnabled(not running)
        self.local_image_button.setEnabled(not running)
        self.queue_image_button.setEnabled(not running)
        self.recent_qwen_button.setEnabled(not running)
        self.status_label.setText("处理中" if running else self.status_label.text())

    def set_result(self, result: SuperResolutionResult) -> None:
        self._output_path = result.output_path
        self.status_label.setText("成功")
        self.after_size_label.setText(f"结果：{result.after_size[0]} x {result.after_size[1]}")
        self.output_path_label.setText(f"输出：{result.output_path}")
        self.error_label.setText("")
        self._set_preview(self.after_preview, result.output_path)
        self.add_to_queue_button.setEnabled(True)
        self.set_reference_button.setEnabled(True)

    def set_error(self, message: str) -> None:
        self.status_label.setText("失败")
        self.error_label.setText(message)

    def _build_layout(self) -> None:
        title = QLabel("超分")
        title.setObjectName("panelTitle")

        source_group = QGroupBox("输入来源")
        source_buttons = QHBoxLayout()
        source_buttons.addWidget(self.local_image_button)
        source_buttons.addWidget(self.queue_image_button)
        source_buttons.addWidget(self.recent_qwen_button)
        source_layout = QVBoxLayout(source_group)
        source_layout.addLayout(source_buttons)
        source_layout.addWidget(self.source_label)

        parameter_group = QGroupBox("参数")
        parameter_form = QFormLayout(parameter_group)
        parameter_form.addRow("放大倍数", self.factor_combo)
        parameter_form.addRow("输出格式", self.format_combo)
        parameter_form.addRow("JPG 质量", self.quality_spin)

        preview_group = QGroupBox("预览")
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
        layout.addWidget(QLabel("状态"))
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
            "选择超分来源图像",
            "",
            "图像文件 (*.png *.jpg *.jpeg *.webp *.bmp *.tga *.tif *.tiff);;所有文件 (*.*)",
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
