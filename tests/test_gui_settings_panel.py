import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import pytest

from pixelator.gui.settings_panel import SettingsPanel
from pixelator.gui.models import RenderSettings


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_settings_panel_defaults_to_automatic_palette(qapp):
    panel = SettingsPanel()

    settings = panel.settings()

    assert settings.palette_strategy == "global_sampled"
    assert settings.custom_palette is None
    assert settings.to_config().palette.custom_colors is None
    assert settings.crt == "off"
    assert settings.vhs == "off"


def test_settings_panel_set_settings_updates_controls_without_emitting(qapp):
    panel = SettingsPanel()
    emissions = []
    panel.settingsChanged.connect(lambda: emissions.append("changed"))

    panel.set_settings(
        RenderSettings(
            mode="fast",
            palette_strategy="original",
            pixel_scale=8,
            colors=16,
            brightness=1.25,
            sharpness=1.5,
            saturation=0.8,
            crt="subtle",
            vhs="light",
            keep_audio=False,
            overwrite=True,
            output_format="gif",
        )
    )

    settings = panel.settings()
    assert settings.mode == "fast"
    assert settings.palette_strategy == "original"
    assert settings.pixel_scale == 8
    assert settings.colors == 16
    assert settings.output_format == "gif"
    assert not panel.colors_spin.isEnabled()
    assert emissions == []

    panel.pixel_scale_spin.setValue(9)

    assert emissions == ["changed"]


def test_settings_panel_original_colors_emits_and_disables_color_count(qapp):
    panel = SettingsPanel()
    emissions = []
    panel.settingsChanged.connect(lambda: emissions.append("changed"))

    panel.palette_strategy_combo.setCurrentText("Original Colors")

    settings = panel.settings()
    assert settings.palette_strategy == "original"
    assert settings.to_config().palette.strategy == "original"
    assert not panel.colors_spin.isEnabled()
    assert emissions == ["changed"]


def test_settings_panel_open_output_dir_creates_and_opens_folder(monkeypatch, tmp_path: Path, qapp):
    panel = SettingsPanel()
    output_dir = tmp_path / "nested" / "outputs"
    opened_urls = []

    def fake_open_url(url):
        opened_urls.append(url)
        return True

    monkeypatch.setattr("pixelator.gui.settings_panel.QDesktopServices.openUrl", fake_open_url)
    panel.output_folder_edit.setText(str(output_dir))

    panel._open_output_folder()

    assert output_dir.is_dir()
    assert len(opened_urls) == 1
    assert Path(opened_urls[0].toLocalFile()) == output_dir.resolve()
