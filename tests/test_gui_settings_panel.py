import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import pytest

from pixelator.gui.settings_panel import SettingsPanel


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
