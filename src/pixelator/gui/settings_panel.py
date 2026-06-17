from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Signal
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


class SettingsPanel(QWidget):
    settingsChanged = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.scope_label = QLabel("Settings: Global Default")
        self.scope_label.setObjectName("panelTitle")
        self.customize_button = QPushButton("Customize This Item")
        self.use_global_button = QPushButton("Use Global")

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["stable", "fast"])

        self.pixel_scale_spin = QSpinBox()
        self.pixel_scale_spin.setRange(1, 64)
        self.pixel_scale_spin.setValue(4)

        self.colors_spin = QSpinBox()
        self.colors_spin.setRange(2, 256)
        self.colors_spin.setValue(32)

        self.brightness_spin = self._factor_spin(1.0)
        self.sharpness_spin = self._factor_spin(1.2)
        self.saturation_spin = self._factor_spin(1.1)

        self.crt_combo = QComboBox()
        self.crt_combo.addItems(["off", "subtle"])

        self.vhs_combo = QComboBox()
        self.vhs_combo.addItems(["off", "light"])

        self.keep_audio_check = QCheckBox()
        self.keep_audio_check.setChecked(True)

        self.overwrite_check = QCheckBox()
        self.overwrite_check.setChecked(True)

        self.output_format_combo = QComboBox()
        self.output_format_combo.addItems(["MP4", "GIF"])

        self.output_folder_edit = QLineEdit(str(Path("outputs")))
        self.output_browse_button = QPushButton("Browse")
        self.output_browse_button.clicked.connect(self._choose_output_folder)

        title = QLabel("Render Settings")
        title.setObjectName("panelTitle")

        scope_row = QHBoxLayout()
        scope_row.addWidget(self.scope_label, 1)
        scope_row.addWidget(self.customize_button)
        scope_row.addWidget(self.use_global_button)

        form = QFormLayout()
        form.addRow("Mode", self.mode_combo)
        form.addRow("Pixel scale", self.pixel_scale_spin)
        form.addRow("Colors", self.colors_spin)
        form.addRow("Brightness", self.brightness_spin)
        form.addRow("Sharpness", self.sharpness_spin)
        form.addRow("Saturation", self.saturation_spin)
        form.addRow("CRT", self.crt_combo)
        form.addRow("VHS", self.vhs_combo)
        form.addRow("Keep audio", self.keep_audio_check)
        form.addRow("Overwrite", self.overwrite_check)
        form.addRow("Output format", self.output_format_combo)

        output_row = QHBoxLayout()
        output_row.addWidget(self.output_folder_edit, 1)
        output_row.addWidget(self.output_browse_button)
        form.addRow("Output folder", output_row)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(scope_row)
        layout.addLayout(form)
        layout.addStretch(1)
        self._connect_setting_signals()
        self.set_settings_scope(customized=False)

    def settings(self) -> RenderSettings:
        return RenderSettings(
            mode=self.mode_combo.currentText(),
            pixel_scale=self.pixel_scale_spin.value(),
            colors=self.colors_spin.value(),
            brightness=self.brightness_spin.value(),
            sharpness=self.sharpness_spin.value(),
            saturation=self.saturation_spin.value(),
            crt=self.crt_combo.currentText(),
            vhs=self.vhs_combo.currentText(),
            keep_audio=self.keep_audio_check.isChecked(),
            overwrite=self.overwrite_check.isChecked(),
            output_format=self.output_format_combo.currentText().lower(),
        )

    def set_settings(self, settings: RenderSettings) -> None:
        blockers = [QSignalBlocker(widget) for widget in self._setting_widgets()]
        try:
            self.mode_combo.setCurrentText(settings.mode)
            self.pixel_scale_spin.setValue(settings.pixel_scale)
            self.colors_spin.setValue(settings.colors)
            self.brightness_spin.setValue(settings.brightness)
            self.sharpness_spin.setValue(settings.sharpness)
            self.saturation_spin.setValue(settings.saturation)
            self.crt_combo.setCurrentText(settings.crt)
            self.vhs_combo.setCurrentText(settings.vhs)
            self.keep_audio_check.setChecked(settings.keep_audio)
            self.overwrite_check.setChecked(settings.overwrite)
            self.output_format_combo.setCurrentText(settings.output_format.upper())
        finally:
            del blockers

    def set_settings_scope(self, customized: bool) -> None:
        self.scope_label.setText("Settings: Customized" if customized else "Settings: Global Default")
        self.customize_button.setEnabled(not customized)
        self.use_global_button.setEnabled(customized)

    def output_folder(self) -> Path:
        return Path(self.output_folder_edit.text()).expanduser()

    def _choose_output_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Select output folder", self.output_folder_edit.text())
        if selected:
            self.output_folder_edit.setText(selected)

    def _factor_spin(self, value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0.1, 4.0)
        spin.setSingleStep(0.05)
        spin.setDecimals(2)
        spin.setValue(value)
        return spin

    def _connect_setting_signals(self) -> None:
        for combo in (self.mode_combo, self.crt_combo, self.vhs_combo, self.output_format_combo):
            combo.currentIndexChanged.connect(lambda index: self.settingsChanged.emit())
        for spin in (
            self.pixel_scale_spin,
            self.colors_spin,
            self.brightness_spin,
            self.sharpness_spin,
            self.saturation_spin,
        ):
            spin.valueChanged.connect(lambda value: self.settingsChanged.emit())
        self.keep_audio_check.toggled.connect(lambda checked: self.settingsChanged.emit())
        self.overwrite_check.toggled.connect(lambda checked: self.settingsChanged.emit())

    def _setting_widgets(self) -> list[QWidget]:
        return [
            self.mode_combo,
            self.pixel_scale_spin,
            self.colors_spin,
            self.brightness_spin,
            self.sharpness_spin,
            self.saturation_spin,
            self.crt_combo,
            self.vhs_combo,
            self.keep_audio_check,
            self.overwrite_check,
            self.output_format_combo,
        ]
