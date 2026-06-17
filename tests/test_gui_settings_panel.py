import os

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
    assert settings.pixel_scale == 8
    assert settings.colors == 16
    assert settings.output_format == "gif"
    assert emissions == []

    panel.pixel_scale_spin.setValue(9)

    assert emissions == ["changed"]
