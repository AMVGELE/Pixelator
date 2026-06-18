import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from pixelator.ai.types import AiAssetRecord
from pixelator.gui.main_window import MainWindow
from pixelator.gui.qwen_lab_panel import QwenLabPanel


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_qwen_lab_panel_fills_editable_prompt_from_builder(qapp):
    panel = QwenLabPanel()

    panel.description_edit.setPlainText("Clockwork owl familiar")
    panel.keywords_edit.setText("brass wings, readable silhouette")
    panel.positive_prompt_edit.appendPlainText("extra note: two animation-ready poses")
    request, prompt = panel.generation_request()

    assert "Clockwork owl familiar" in panel.positive_prompt_edit.toPlainText()
    assert "brass wings" in prompt.positive_prompt
    assert "two animation-ready poses" in prompt.positive_prompt
    assert request.description == "Clockwork owl familiar"


def test_qwen_lab_panel_starts_with_empty_prompt_editor(qapp):
    panel = QwenLabPanel()

    assert panel.positive_prompt_edit.toPlainText() == ""
    assert panel.negative_prompt_edit.toPlainText() == ""


def test_qwen_lab_panel_builds_dynamic_resolution_request(qapp):
    panel = QwenLabPanel()

    panel.description_edit.setPlainText("Tall magic door")
    panel.width_spin.setValue(384)
    panel.height_spin.setValue(768)
    panel.count_spin.setValue(2)
    panel.background_combo.setCurrentIndex(panel.background_combo.findData("transparent"))
    request, prompt = panel.generation_request()

    assert request.size == "384x768"
    assert request.count == 2
    assert request.background == "transparent"
    assert prompt.negative_prompt


def test_qwen_lab_panel_rejects_size_outside_qwen_pixel_budget(qapp):
    panel = QwenLabPanel()

    panel.description_edit.setPlainText("Tiny coin")
    panel.width_spin.setValue(256)
    panel.height_spin.setValue(256)

    with pytest.raises(ValueError, match="between 512x512 and 2048x2048"):
        panel.generation_request()


def test_main_window_has_qwen_lab_tab(qapp):
    window = MainWindow()

    assert window.right_tabs.count() == 4
    assert window.right_tabs.tabText(2) == "AI Assets"
    assert window.right_tabs.tabText(3) == "Qwen Lab"
    window.close()


def test_main_window_auto_adds_qwen_lab_outputs_to_queue(tmp_path: Path, qapp):
    source = tmp_path / "lab_asset.png"
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(source)
    window = MainWindow()
    record = _record(source)

    window._on_qwen_lab_generation_completed([record])

    assert window.qwen_lab_panel.result_list.count() == 1
    assert len(window.queue.jobs) == 1
    assert window.queue.jobs[0].source_path == source
    window.close()


def _record(path: Path) -> AiAssetRecord:
    return AiAssetRecord(
        id="asset_1",
        batch_id="batch_1",
        name="lab asset",
        asset_type="custom",
        style="free_prompt",
        game_genre="custom",
        view="custom",
        size="384x768",
        background="transparent",
        prompt="positive",
        negative_prompt="negative",
        image_path=path,
        created_at="2026-06-18T00:00:00+00:00",
    )
