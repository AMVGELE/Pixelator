from __future__ import annotations

from pathlib import Path

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
    def __init__(self) -> None:
        super().__init__()
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
        self.crt_combo.addItems(["subtle", "off"])

        self.vhs_combo = QComboBox()
        self.vhs_combo.addItems(["light", "off"])

        self.keep_audio_check = QCheckBox()
        self.keep_audio_check.setChecked(True)

        self.overwrite_check = QCheckBox()
        self.overwrite_check.setChecked(True)

        self.output_format_combo = QComboBox()
        self.output_format_combo.addItems(["MP4", "GIF"])

        self.output_folder_edit = QLineEdit(str(Path("outputs")))
        self.output_browse_button = QPushButton("Browse")
        self.output_browse_button.clicked.connect(self._choose_output_folder)

        title = QLabel("Settings")
        title.setObjectName("panelTitle")

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
        layout.addLayout(form)
        layout.addStretch(1)

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
