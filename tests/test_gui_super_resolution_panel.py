from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from pixelator.ai.super_resolution import SuperResolutionResult
from pixelator.gui.super_resolution_panel import SuperResolutionPanel


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_super_resolution_panel_builds_options_from_source(tmp_path: Path, qapp):
    source = tmp_path / "source.png"
    Image.new("RGB", (4, 5), (255, 0, 0)).save(source)
    panel = SuperResolutionPanel()

    panel.set_source_path(source)
    panel.factor_combo.setCurrentIndex(panel.factor_combo.findData(4))
    panel.format_combo.setCurrentIndex(panel.format_combo.findData("jpg"))
    panel.quality_spin.setValue(90)
    options = panel.options()

    assert options.source_path == source
    assert options.upscale_factor == 4
    assert options.output_format == "jpg"
    assert options.jpg_quality == 90
    assert panel.before_size_label.text() == "原图：4 x 5"
    assert panel.quality_spin.isEnabled()


def test_super_resolution_panel_reports_result_and_enables_actions(tmp_path: Path, qapp):
    source = tmp_path / "source.png"
    output = tmp_path / "source_sr2x.png"
    Image.new("RGB", (4, 4), (255, 0, 0)).save(source)
    Image.new("RGB", (8, 8), (0, 255, 0)).save(output)
    panel = SuperResolutionPanel()

    panel.set_source_path(source)
    panel.set_result(
        SuperResolutionResult(
            source_path=source,
            output_path=output,
            source_url=None,
            output_url="https://example.test/out.png",
            before_size=(4, 4),
            after_size=(8, 8),
            upscale_factor=2,
            output_format="png",
        )
    )

    assert panel.status_label.text() == "成功"
    assert panel.after_size_label.text() == "结果：8 x 8"
    assert panel.add_to_queue_button.isEnabled()
    assert panel.set_reference_button.isEnabled()
