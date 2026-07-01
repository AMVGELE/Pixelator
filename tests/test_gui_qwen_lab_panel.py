import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from pixelator.ai.env import config_value, local_env_values
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


def test_qwen_lab_panel_saves_qwen_key_for_cli(monkeypatch, tmp_path: Path, qapp):
    env_file = tmp_path / ".env.local"
    monkeypatch.setenv("PIXELATOR_ENV_FILE", str(env_file))
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    local_env_values.cache_clear()
    panel = QwenLabPanel()

    panel.api_key_edit.setText("saved-lab-key")
    panel.save_api_key_button.click()

    assert env_file.read_text(encoding="utf-8") == "DASHSCOPE_API_KEY=saved-lab-key\n"
    assert config_value("DASHSCOPE_API_KEY") == "saved-lab-key"
    assert panel.key_source_label.text() == "已保存到 .env.local；CLI 使用 DASHSCOPE_API_KEY"
    assert "已保存 Qwen API key" in panel.status_label.text()


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

    with pytest.raises(ValueError, match="512x512 和 2048x2048"):
        panel.generation_request()


def test_main_window_has_qwen_lab_tab(qapp):
    window = MainWindow()

    assert window.right_tabs.count() == 5
    assert window.right_tabs.tabText(2) == "AI 资产"
    assert window.right_tabs.tabText(3) == "Qwen 实验室"
    window.close()


def test_main_window_auto_adds_qwen_lab_outputs_to_queue(tmp_path: Path, qapp):
    source = tmp_path / "lab_asset.png"
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(source)
    window = MainWindow()
    record = _record(source)
    previous_count = window.qwen_lab_panel.result_list.count()

    window._on_qwen_lab_generation_completed([record])

    assert window.qwen_lab_panel.result_list.count() == previous_count + 1
    assert len(window.queue.jobs) == 1
    assert window.queue.jobs[0].source_path == source
    window.close()


def test_main_window_uses_recent_qwen_output_for_super_resolution(tmp_path: Path, qapp):
    source = tmp_path / "lab_asset.png"
    Image.new("RGBA", (5, 6), (255, 0, 0, 255)).save(source)
    window = MainWindow()
    record = _record(source)

    window._on_qwen_lab_generation_completed([record])
    window._use_recent_qwen_output_for_super_resolution()

    assert window.super_resolution_panel.options().source_path == source
    assert window.super_resolution_panel.before_size_label.text() == "原图：5 x 6"
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
