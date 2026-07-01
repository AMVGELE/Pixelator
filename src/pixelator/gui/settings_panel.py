from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSignalBlocker, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pixelator.gui.models import RenderSettings
from pixelator.style_filters import (
    PALETTE_MODE_AUTO_PRESERVE_LIGHTS,
    PALETTE_MODE_AUTO_UNIFIED,
    PALETTE_MODE_FIXED,
    STYLE_FILTERS,
    style_filter_by_id,
)


class SettingsPanel(QWidget):
    settingsChanged = Signal()
    styleFilterChanged = Signal(str)
    paletteGenerationRequested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._applying_style_filter = False
        self._media_type: str | None = None
        self.scope_label = QLabel("设置：全局默认")
        self.scope_label.setObjectName("panelTitle")
        self.customize_button = QPushButton("自定义此项")
        self.use_global_button = QPushButton("使用全局")

        self.style_filter_combo = QComboBox()
        for style in STYLE_FILTERS:
            self.style_filter_combo.addItem(style.label, style.id)

        self.palette_mode_combo = QComboBox()
        self.palette_mode_combo.addItem("固定色盘", PALETTE_MODE_FIXED)
        self.palette_mode_combo.addItem("自动统一", PALETTE_MODE_AUTO_UNIFIED)
        self.palette_mode_combo.addItem("自动保留灯色", PALETTE_MODE_AUTO_PRESERVE_LIGHTS)
        self.generate_palette_button = QPushButton("生成色盘")
        self.style_status_label = QLabel("滤镜：干净像素")

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("稳定", "stable")
        self.mode_combo.addItem("快速", "fast")

        self.palette_strategy_combo = QComboBox()
        self.palette_strategy_combo.addItem("自动色盘", "global_sampled")
        self.palette_strategy_combo.addItem("原始颜色", "original")

        self.pixel_scale_spin = QSpinBox()
        self.pixel_scale_spin.setRange(1, 64)
        self.pixel_scale_spin.setValue(4)

        self.target_width_check = QCheckBox()
        self.target_width_check.setToolTip("启用后按目标宽度生成更细的像素结果；关闭时使用像素尺度。")

        self.target_width_spin = QSpinBox()
        self.target_width_spin.setRange(16, 16384)
        self.target_width_spin.setSingleStep(64)
        self.target_width_spin.setSuffix(" px")
        self.target_width_spin.setValue(1920)
        self.target_width_spin.setToolTip("高清输出的目标宽度，会覆盖像素尺度的低分辨率尺寸计算。")

        self.colors_spin = QSpinBox()
        self.colors_spin.setRange(2, 256)
        self.colors_spin.setValue(32)

        self.brightness_spin = self._factor_spin(1.0)
        self.sharpness_spin = self._factor_spin(1.2)
        self.saturation_spin = self._factor_spin(1.1)

        self.crt_combo = QComboBox()
        self.crt_combo.addItem("关闭", "off")
        self.crt_combo.addItem("轻微", "subtle")

        self.vhs_combo = QComboBox()
        self.vhs_combo.addItem("关闭", "off")
        self.vhs_combo.addItem("轻微", "light")

        self.dither_combo = QComboBox()
        self.dither_combo.addItem("关闭", "off")
        self.dither_combo.addItem("有序", "ordered")
        self.dither_combo.addItem("菱形", "diamond")

        self.dither_ramp_combo = QComboBox()
        self.dither_ramp_combo.addItem("邻近色", "nearest")
        self.dither_ramp_combo.addItem("明度阶梯", "tone")

        self.dither_space_combo = QComboBox()
        self.dither_space_combo.addItem("输出尺寸", "output")
        self.dither_space_combo.addItem("像素格", "pixel")

        self.dither_strength_spin = QDoubleSpinBox()
        self.dither_strength_spin.setRange(0.0, 1.0)
        self.dither_strength_spin.setSingleStep(0.05)
        self.dither_strength_spin.setDecimals(2)
        self.dither_strength_spin.setValue(0.45)

        self.dither_scale_spin = QSpinBox()
        self.dither_scale_spin.setRange(2, 32)
        self.dither_scale_spin.setValue(4)

        self.dither_angle_spin = QDoubleSpinBox()
        self.dither_angle_spin.setRange(-180.0, 180.0)
        self.dither_angle_spin.setSingleStep(5.0)
        self.dither_angle_spin.setDecimals(1)
        self.dither_angle_spin.setValue(0.0)

        self.keep_audio_check = QCheckBox()
        self.keep_audio_check.setChecked(True)

        self.overwrite_check = QCheckBox()
        self.overwrite_check.setChecked(True)

        self.output_format_combo = QComboBox()
        self.output_format_combo.addItems(["MP4", "GIF"])

        self.output_folder_edit = QLineEdit(str(Path("outputs")))
        self.output_browse_button = QPushButton("浏览")
        self.output_open_button = QPushButton("打开")
        self.output_browse_button.clicked.connect(self._choose_output_folder)
        self.output_open_button.clicked.connect(self._open_output_folder)

        title = QLabel("渲染设置")
        title.setObjectName("panelTitle")

        scope_row = QHBoxLayout()
        scope_row.addWidget(self.scope_label, 1)
        scope_row.addWidget(self.customize_button)
        scope_row.addWidget(self.use_global_button)

        form = QFormLayout()
        form.addRow("风格滤镜", self.style_filter_combo)
        form.addRow("调色盘模式", self.palette_mode_combo)
        form.addRow("", self.generate_palette_button)
        form.addRow("", self.style_status_label)
        form.addRow("渲染模式", self.mode_combo)
        form.addRow("调色方式", self.palette_strategy_combo)
        form.addRow("像素尺度", self.pixel_scale_spin)
        form.addRow("高清输出", self.target_width_check)
        form.addRow("目标宽度", self.target_width_spin)
        form.addRow("颜色数量", self.colors_spin)
        form.addRow("亮度", self.brightness_spin)
        form.addRow("锐度", self.sharpness_spin)
        form.addRow("饱和度", self.saturation_spin)
        form.addRow("CRT", self.crt_combo)
        form.addRow("VHS", self.vhs_combo)
        form.addRow("抖动", self.dither_combo)
        form.addRow("抖动色阶", self.dither_ramp_combo)
        form.addRow("抖动空间", self.dither_space_combo)
        form.addRow("抖动强度", self.dither_strength_spin)
        form.addRow("抖动尺度", self.dither_scale_spin)
        form.addRow("抖动角度", self.dither_angle_spin)
        form.addRow("保留音频", self.keep_audio_check)
        form.addRow("覆盖输出", self.overwrite_check)
        form.addRow("输出格式", self.output_format_combo)

        output_row = QHBoxLayout()
        output_row.addWidget(self.output_folder_edit, 1)
        output_row.addWidget(self.output_browse_button)
        output_row.addWidget(self.output_open_button)
        form.addRow("输出文件夹", output_row)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(scope_row)
        layout.addLayout(form)
        layout.addStretch(1)
        self._connect_setting_signals()
        self._set_target_width_enabled(False)
        self._update_palette_controls()
        self._update_output_controls()
        self.set_settings_scope(customized=False)

    def settings(self) -> RenderSettings:
        return RenderSettings(
            style_filter=self._combo_data(self.style_filter_combo),
            palette_mode=self._combo_data(self.palette_mode_combo),
            mode=self._combo_data(self.mode_combo),
            palette_strategy=str(self.palette_strategy_combo.currentData() or "global_sampled"),
            pixel_scale=self.pixel_scale_spin.value(),
            target_width=self.target_width_spin.value() if self.target_width_check.isChecked() else None,
            colors=self.colors_spin.value(),
            brightness=self.brightness_spin.value(),
            sharpness=self.sharpness_spin.value(),
            saturation=self.saturation_spin.value(),
            crt=self._combo_data(self.crt_combo),
            vhs=self._combo_data(self.vhs_combo),
            dither=self._combo_data(self.dither_combo),
            dither_ramp=self._combo_data(self.dither_ramp_combo),
            dither_space=self._combo_data(self.dither_space_combo),
            dither_strength=self.dither_strength_spin.value(),
            dither_scale=self.dither_scale_spin.value(),
            dither_angle=self.dither_angle_spin.value(),
            keep_audio=self.keep_audio_check.isChecked(),
            overwrite=self.overwrite_check.isChecked(),
            output_format=self.output_format_combo.currentText().lower(),
        )

    def set_settings(self, settings: RenderSettings) -> None:
        blockers = [QSignalBlocker(widget) for widget in self._setting_widgets()]
        try:
            self._set_combo_data(self.style_filter_combo, settings.style_filter)
            self._set_combo_data(self.palette_mode_combo, settings.palette_mode)
            self._set_combo_data(self.mode_combo, settings.mode)
            self._set_combo_data(self.palette_strategy_combo, settings.palette_strategy)
            self.pixel_scale_spin.setValue(settings.pixel_scale)
            self.target_width_check.setChecked(settings.target_width is not None)
            if settings.target_width is not None:
                self.target_width_spin.setValue(settings.target_width)
            self._set_target_width_enabled(settings.target_width is not None)
            self.colors_spin.setValue(settings.colors)
            self.brightness_spin.setValue(settings.brightness)
            self.sharpness_spin.setValue(settings.sharpness)
            self.saturation_spin.setValue(settings.saturation)
            self._set_combo_data(self.crt_combo, settings.crt)
            self._set_combo_data(self.vhs_combo, settings.vhs)
            self._set_combo_data(self.dither_combo, settings.dither)
            self._set_combo_data(self.dither_ramp_combo, settings.dither_ramp)
            self._set_combo_data(self.dither_space_combo, settings.dither_space)
            self.dither_strength_spin.setValue(settings.dither_strength)
            self.dither_scale_spin.setValue(settings.dither_scale)
            self.dither_angle_spin.setValue(settings.dither_angle)
            self.keep_audio_check.setChecked(settings.keep_audio)
            self.overwrite_check.setChecked(settings.overwrite)
            self.output_format_combo.setCurrentText(settings.output_format.upper())
            self._update_palette_controls()
            self._set_style_status(settings.style_filter)
        finally:
            del blockers

    def set_settings_scope(self, customized: bool) -> None:
        self.scope_label.setText("设置：已自定义" if customized else "设置：全局默认")
        self.customize_button.setEnabled(not customized)
        self.use_global_button.setEnabled(customized)

    def output_folder(self) -> Path:
        return Path(self.output_folder_edit.text()).expanduser()

    def set_media_type(self, media_type: str | None) -> None:
        self._media_type = media_type
        self._update_output_controls()

    def _choose_output_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "选择输出文件夹", self.output_folder_edit.text())
        if selected:
            self.output_folder_edit.setText(selected)

    def _open_output_folder(self) -> None:
        output_dir = self.output_folder()
        output_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_dir.resolve())))

    def _factor_spin(self, value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0.1, 4.0)
        spin.setSingleStep(0.05)
        spin.setDecimals(2)
        spin.setValue(value)
        return spin

    def _connect_setting_signals(self) -> None:
        self.style_filter_combo.currentIndexChanged.connect(lambda index: self._on_style_filter_changed())
        self.palette_mode_combo.currentIndexChanged.connect(lambda index: self._on_palette_mode_changed())
        self.generate_palette_button.clicked.connect(lambda: self.paletteGenerationRequested.emit())
        self.target_width_check.toggled.connect(self._on_target_width_toggled)
        for combo in (
            self.mode_combo,
            self.palette_strategy_combo,
            self.crt_combo,
            self.vhs_combo,
            self.dither_combo,
            self.dither_ramp_combo,
            self.dither_space_combo,
            self.output_format_combo,
        ):
            combo.currentIndexChanged.connect(lambda index: self._mark_customized_and_emit())
        self.palette_strategy_combo.currentIndexChanged.connect(lambda index: self._update_palette_controls())
        self.output_format_combo.currentIndexChanged.connect(lambda index: self._update_output_controls())
        for spin in (
            self.pixel_scale_spin,
            self.target_width_spin,
            self.colors_spin,
            self.brightness_spin,
            self.sharpness_spin,
            self.saturation_spin,
            self.dither_strength_spin,
            self.dither_scale_spin,
            self.dither_angle_spin,
        ):
            spin.valueChanged.connect(lambda value: self._mark_customized_and_emit())
        self.keep_audio_check.toggled.connect(lambda checked: self.settingsChanged.emit())
        self.overwrite_check.toggled.connect(lambda checked: self.settingsChanged.emit())

    def _setting_widgets(self) -> list[QWidget]:
        return [
            self.style_filter_combo,
            self.palette_mode_combo,
            self.mode_combo,
            self.palette_strategy_combo,
            self.pixel_scale_spin,
            self.target_width_check,
            self.target_width_spin,
            self.colors_spin,
            self.brightness_spin,
            self.sharpness_spin,
            self.saturation_spin,
            self.crt_combo,
            self.vhs_combo,
            self.dither_combo,
            self.dither_ramp_combo,
            self.dither_space_combo,
            self.dither_strength_spin,
            self.dither_scale_spin,
            self.dither_angle_spin,
            self.keep_audio_check,
            self.overwrite_check,
            self.output_format_combo,
        ]

    def _style_target_widgets(self) -> list[QWidget]:
        return [
            self.mode_combo,
            self.palette_strategy_combo,
            self.pixel_scale_spin,
            self.colors_spin,
            self.brightness_spin,
            self.sharpness_spin,
            self.saturation_spin,
            self.crt_combo,
            self.vhs_combo,
            self.dither_combo,
            self.dither_ramp_combo,
            self.dither_space_combo,
            self.dither_strength_spin,
            self.dither_scale_spin,
            self.dither_angle_spin,
        ]

    def _update_palette_controls(self) -> None:
        palette_enabled = self.palette_strategy_combo.currentData() != "original"
        self.palette_mode_combo.setEnabled(palette_enabled)
        self.generate_palette_button.setEnabled(palette_enabled)
        self.colors_spin.setEnabled(palette_enabled)
        for widget in (
            self.dither_combo,
            self.dither_ramp_combo,
            self.dither_space_combo,
            self.dither_strength_spin,
            self.dither_scale_spin,
            self.dither_angle_spin,
        ):
            widget.setEnabled(palette_enabled)

    def _update_output_controls(self) -> None:
        is_image = self._media_type == "image"
        output_is_mp4 = self.output_format_combo.currentText().lower() == "mp4"
        self.output_format_combo.setEnabled(not is_image)
        self.keep_audio_check.setEnabled(not is_image and output_is_mp4)

    def _on_palette_mode_changed(self) -> None:
        self.paletteGenerationRequested.emit()
        self.settingsChanged.emit()

    def _on_style_filter_changed(self) -> None:
        style_id = self._combo_data(self.style_filter_combo)
        self.apply_style_filter(style_id)
        self.styleFilterChanged.emit(style_id)
        self.settingsChanged.emit()

    def apply_style_filter(self, style_id: str) -> None:
        style = style_filter_by_id(style_id)
        blockers = [QSignalBlocker(widget) for widget in self._style_target_widgets()]
        self._applying_style_filter = True
        try:
            self._set_combo_data(self.mode_combo, "stable")
            self._set_combo_data(self.palette_strategy_combo, "global_sampled")
            self.pixel_scale_spin.setValue(style.pixel_scale)
            self.colors_spin.setValue(style.colors)
            self.brightness_spin.setValue(style.brightness)
            self.sharpness_spin.setValue(style.sharpness)
            self.saturation_spin.setValue(style.saturation)
            self._set_combo_data(self.crt_combo, style.crt)
            self._set_combo_data(self.vhs_combo, style.vhs)
            self._set_combo_data(self.dither_combo, style.dither)
            self._set_combo_data(self.dither_ramp_combo, style.dither_ramp)
            self._set_combo_data(self.dither_space_combo, style.dither_space)
            self.dither_strength_spin.setValue(style.dither_strength)
            self.dither_scale_spin.setValue(style.dither_scale)
            self.dither_angle_spin.setValue(style.dither_angle)
            self._update_palette_controls()
            self._set_style_status(style.id)
        finally:
            self._applying_style_filter = False
            del blockers

    def _mark_customized_and_emit(self) -> None:
        if not self._applying_style_filter:
            self.style_status_label.setText("滤镜：已自定义")
        self.settingsChanged.emit()

    def _on_target_width_toggled(self, checked: bool) -> None:
        self._set_target_width_enabled(checked)
        self._mark_customized_and_emit()

    def _set_target_width_enabled(self, enabled: bool) -> None:
        self.target_width_spin.setEnabled(enabled)

    def _set_style_status(self, style_id: str) -> None:
        self.style_status_label.setText(f"滤镜：{style_filter_by_id(style_id).label}")

    def _combo_data(self, combo: QComboBox) -> str:
        data = combo.currentData()
        return str(data if data is not None else combo.currentText())

    def _set_combo_data(self, combo: QComboBox, value: str) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return
        combo.setCurrentIndex(0)
