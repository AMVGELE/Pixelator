import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from pixelator.ai.env import config_value, local_env_values
from pixelator.ai.types import AiAssetRecord
from pixelator.gui.ai_panel import AiAssetsPanel
from pixelator.gui.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_ai_panel_builds_generation_request(qapp):
    panel = AiAssetsPanel()
    panel.description_edit.setPlainText("Fire slime monster")
    panel.size_combo.setCurrentText("64x64")
    panel.count_spin.setValue(2)

    request = panel.request()

    assert request.description == "Fire slime monster"
    assert request.size == "64x64"
    assert request.count == 2
    assert "Fire slime monster" in panel.prompt_preview.toPlainText()


def test_ai_panel_exposes_qwen_key_in_provider_settings(qapp):
    panel = AiAssetsPanel()

    assert panel.api_key_edit.placeholderText() == "留空时使用 DASHSCOPE_API_KEY 或 .env.local"
    assert panel.save_api_key_button.text() == "保存"
    panel.api_key_edit.setText("session-key")

    assert panel.key_source_label.text() == "使用本次粘贴的密钥"


def test_ai_panel_saves_qwen_key_for_cli(monkeypatch, tmp_path: Path, qapp):
    env_file = tmp_path / ".env.local"
    monkeypatch.setenv("PIXELATOR_ENV_FILE", str(env_file))
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    local_env_values.cache_clear()
    panel = AiAssetsPanel()

    panel.api_key_edit.setText("saved-gui-key")
    panel.save_api_key_button.click()

    assert env_file.read_text(encoding="utf-8") == "DASHSCOPE_API_KEY=saved-gui-key\n"
    assert config_value("DASHSCOPE_API_KEY") == "saved-gui-key"
    assert panel.key_source_label.text() == "已保存到 .env.local；CLI 使用 DASHSCOPE_API_KEY"
    assert "已保存 Qwen API key" in panel.status_label.text()


def test_ai_panel_preserves_status_when_generation_stops(qapp):
    panel = AiAssetsPanel()

    panel.set_status_message("Saved 1 AI asset")
    panel.set_generating(False)

    assert panel.status_label.text() == "Saved 1 AI asset"


def test_main_window_has_ai_assets_tab(qapp):
    window = MainWindow()

    assert window.right_tabs.count() == 5
    assert window.right_tabs.tabText(2) == "AI 资产"
    window.close()


def test_main_window_adds_generated_asset_records_to_ai_panel(tmp_path: Path, qapp):
    source = tmp_path / "asset.png"
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(source)
    window = MainWindow()
    record = _record(source)

    window._on_ai_generation_completed([record])

    assert window.ai_panel.result_list.count() >= 1
    assert "已在" in window.log_view.toPlainText()
    assert "生成 1 个 AI 资产" in window.log_view.toPlainText()
    window.close()


def test_main_window_adds_ai_asset_to_existing_queue(tmp_path: Path, qapp):
    source = tmp_path / "asset.png"
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(source)
    window = MainWindow()

    window._add_ai_asset_to_queue(str(source))

    assert len(window.queue.jobs) == 1
    assert window.queue.jobs[0].is_image
    assert window.preview_widget.source_size() == (4, 4)
    window.close()


def _record(path: Path) -> AiAssetRecord:
    return AiAssetRecord(
        id="asset_1",
        batch_id="batch_1",
        name="asset",
        asset_type="character",
        style="pixel_art",
        game_genre="rpg",
        view="front",
        size="64x64",
        background="transparent",
        prompt="positive",
        negative_prompt="negative",
        image_path=path,
        created_at="2026-06-17T00:00:00+00:00",
    )
