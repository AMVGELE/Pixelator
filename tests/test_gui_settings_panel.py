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
    assert settings.style_filter == "clean_pixel"
    assert settings.palette_mode == "fixed"
    assert settings.crt == "off"
    assert settings.vhs == "off"
    assert settings.dither == "off"
    assert settings.dither_ramp == "nearest"
    assert settings.dither_space == "output"
    assert settings.target_width is None
    assert not panel.target_width_spin.isEnabled()


def test_settings_panel_set_settings_updates_controls_without_emitting(qapp):
    panel = SettingsPanel()
    emissions = []
    panel.settingsChanged.connect(lambda: emissions.append("changed"))

    panel.set_settings(
        RenderSettings(
            style_filter="dark_fantasy_dither",
            palette_mode="auto_preserve_lights",
            mode="fast",
            palette_strategy="original",
            pixel_scale=8,
            target_width=1280,
            colors=16,
            brightness=1.25,
            sharpness=1.5,
            saturation=0.8,
            crt="subtle",
            vhs="light",
            dither="diamond",
            dither_ramp="tone",
            dither_space="pixel",
            dither_strength=0.7,
            dither_scale=5,
            dither_angle=45.0,
            keep_audio=False,
            overwrite=True,
            output_format="gif",
        )
    )

    settings = panel.settings()
    assert settings.style_filter == "dark_fantasy_dither"
    assert settings.palette_mode == "auto_preserve_lights"
    assert settings.mode == "fast"
    assert settings.palette_strategy == "original"
    assert settings.pixel_scale == 8
    assert settings.target_width == 1280
    assert panel.target_width_spin.isEnabled()
    assert settings.colors == 16
    assert settings.dither == "diamond"
    assert settings.dither_ramp == "tone"
    assert settings.dither_space == "pixel"
    assert settings.dither_strength == 0.7
    assert settings.dither_scale == 5
    assert settings.dither_angle == 45.0
    assert settings.output_format == "gif"
    assert not panel.colors_spin.isEnabled()
    assert not panel.dither_combo.isEnabled()
    assert emissions == []

    panel.pixel_scale_spin.setValue(9)

    assert emissions == ["changed"]


def test_settings_panel_style_filter_applies_render_defaults(qapp):
    panel = SettingsPanel()
    styles = []
    panel.styleFilterChanged.connect(styles.append)
    panel.target_width_check.setChecked(True)
    panel.target_width_spin.setValue(2048)

    panel.style_filter_combo.setCurrentText("暗黑幻想抖动")

    settings = panel.settings()
    assert styles == ["dark_fantasy_dither"]
    assert settings.style_filter == "dark_fantasy_dither"
    assert settings.pixel_scale == 2
    assert settings.colors == 7
    assert settings.dither == "ordered"
    assert settings.dither_ramp == "tone"
    assert settings.dither_space == "pixel"
    assert settings.target_width == 2048
    assert panel.style_status_label.text() == "滤镜：暗黑幻想抖动"


def test_settings_panel_target_width_toggle_controls_high_resolution_output(qapp):
    panel = SettingsPanel()
    emissions = []
    panel.settingsChanged.connect(lambda: emissions.append("changed"))

    panel.target_width_check.setChecked(True)
    panel.target_width_spin.setValue(2560)

    settings = panel.settings()
    assert settings.target_width == 2560
    assert panel.target_width_spin.isEnabled()
    assert emissions == ["changed", "changed"]

    panel.target_width_check.setChecked(False)

    assert panel.settings().target_width is None
    assert not panel.target_width_spin.isEnabled()


def test_settings_panel_original_colors_emits_and_disables_color_count(qapp):
    panel = SettingsPanel()
    emissions = []
    panel.settingsChanged.connect(lambda: emissions.append("changed"))

    panel.palette_strategy_combo.setCurrentText("原始颜色")

    settings = panel.settings()
    assert settings.palette_strategy == "original"
    assert settings.to_config().palette.strategy == "original"
    assert not panel.colors_spin.isEnabled()
    assert not panel.palette_mode_combo.isEnabled()
    assert not panel.generate_palette_button.isEnabled()
    assert not panel.dither_combo.isEnabled()
    assert not panel.dither_strength_spin.isEnabled()
    assert emissions == ["changed"]


def test_settings_panel_palette_mode_change_requests_palette_generation(qapp):
    panel = SettingsPanel()
    requests = []
    emissions = []
    panel.paletteGenerationRequested.connect(lambda: requests.append("generate"))
    panel.settingsChanged.connect(lambda: emissions.append("changed"))

    panel.palette_mode_combo.setCurrentText("自动统一")

    assert panel.settings().palette_mode == "auto_unified"
    assert requests == ["generate"]
    assert emissions == ["changed"]


def test_settings_panel_disables_output_controls_when_they_cannot_affect_output(qapp):
    panel = SettingsPanel()

    panel.set_media_type("image")

    assert not panel.output_format_combo.isEnabled()
    assert not panel.keep_audio_check.isEnabled()

    panel.set_media_type("video")

    assert panel.output_format_combo.isEnabled()
    assert panel.keep_audio_check.isEnabled()

    panel.output_format_combo.setCurrentText("GIF")

    assert panel.output_format_combo.isEnabled()
    assert not panel.keep_audio_check.isEnabled()


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
