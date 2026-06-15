import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import pytest
from PIL import Image

from pixelator.gui.palette_panel import PalettePanel


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_palette_panel_defaults_to_automatic(qapp):
    panel = PalettePanel()

    assert panel.colors() == []
    assert panel.has_custom_palette() is False


def test_palette_panel_add_delete_and_reorder(qapp):
    panel = PalettePanel()

    panel.add_color("#000000")
    panel.add_color("#ffcc00")
    panel.add_color("#ffffff")
    panel.select_index(2)
    panel.move_selected_up()
    assert panel.colors() == ["#000000", "#ffffff", "#ffcc00"]

    panel.select_index(2)
    panel.delete_selected()

    assert panel.colors() == ["#000000", "#ffffff"]
    assert panel.has_custom_palette() is True


def test_palette_panel_updates_selected_color_from_hex(qapp):
    panel = PalettePanel()
    panel.set_colors(["#000000", "#ffffff"])
    panel.select_index(1)
    panel.hex_edit.setText("#ffcc00")

    panel.apply_hex_to_selected()

    assert panel.colors() == ["#000000", "#ffcc00"]


def test_palette_panel_save_and_load(tmp_path, qapp):
    source = PalettePanel()
    source.set_colors(["#1a1c2c", "#ffcc00"])
    path = tmp_path / "palette.yaml"

    source.save_palette(path)

    target = PalettePanel()
    target.load_palette(path)

    assert target.colors() == ["#1a1c2c", "#ffcc00"]


def test_palette_panel_extracts_from_image_file(tmp_path, qapp):
    image = Image.new("RGB", (6, 1))
    image.putdata(
        [(255, 0, 0)] * 3
        + [(0, 255, 0)] * 2
        + [(0, 0, 255)]
    )
    path = tmp_path / "source.png"
    image.save(path)
    panel = PalettePanel()
    panel.extract_count_spin.setValue(3)

    panel.extract_from_image_file(path)

    assert panel.colors() == ["#ff0000", "#00ff00", "#0000ff"]
    assert panel.source_colors() == ["#ff0000", "#00ff00", "#0000ff"]
    assert panel.match_board.row_count() == 3


def test_palette_panel_extract_preserves_existing_render_palette_for_automatch(tmp_path, qapp):
    image = Image.new("RGB", (4, 1))
    image.putdata([(255, 0, 0)] * 3 + [(0, 0, 255)])
    path = tmp_path / "source.png"
    image.save(path)
    panel = PalettePanel()
    panel.set_colors(["#1a1c2c", "#f4f4f4"])

    panel.extract_from_image_file(path)

    assert panel.source_colors() == ["#ff0000", "#0000ff"]
    assert panel.colors() == ["#1a1c2c", "#f4f4f4"]
    assert panel.auto_match_enabled() is True
    assert panel.match_board.row_count() == 2


def test_palette_panel_imports_lospec_text(tmp_path, qapp):
    path = tmp_path / "palette.hex"
    path.write_text("1a1c2c\n#ffcc00\n", encoding="utf-8")
    panel = PalettePanel()

    panel.import_lospec_palette(path)

    assert panel.colors() == ["#1a1c2c", "#ffcc00"]
    assert panel.source_colors() == ["#1a1c2c", "#ffcc00"]


def test_palette_panel_saves_loads_and_deletes_presets(tmp_path, qapp):
    panel = PalettePanel(preset_dir=tmp_path)
    panel.set_colors(["#000000", "#ffcc00"])
    panel.preset_name_edit.setText("Test Palette")

    panel.save_preset()
    panel.set_colors(["#ffffff", "#00ff00"])
    panel.load_selected_preset()

    assert panel.colors() == ["#000000", "#ffcc00"]

    panel.delete_selected_preset(confirm=False)

    assert panel.preset_combo.count() == 0


def test_palette_panel_applies_sort(qapp):
    panel = PalettePanel()
    panel.set_colors(["#ffffff", "#000000", "#808080"])
    panel.sort_combo.setCurrentText("Brightness")

    panel.apply_sort()

    assert panel.colors() == ["#000000", "#808080", "#ffffff"]


def test_palette_panel_replace_render_color_keeps_source_reference(qapp):
    panel = PalettePanel()
    panel.set_source_and_render_colors(["#000000", "#ffffff"])
    panel.select_index(1)

    panel.replace_selected_color("#ffcc00")

    assert panel.colors() == ["#000000", "#ffcc00"]
    assert panel.source_colors() == ["#000000", "#ffffff"]


def test_palette_panel_source_selection_updates_mapping_view(qapp):
    panel = PalettePanel()
    panel.set_source_and_render_colors(["#f00000", "#0000ff"])
    panel.set_colors(["#ff1010", "#0010ff"])

    panel.select_source_index(0)

    assert "#f00000 -> #ff1010" in panel.mapping_view.mapping_label.text()


def test_palette_panel_automatch_uses_perceptual_pairing(qapp):
    panel = PalettePanel()
    panel.set_source_and_render_colors(["#ff0000", "#0000ff"])
    panel.set_colors(["#0000cc", "#ff3300"])
    panel.sort_combo.setCurrentText("Original")

    panel.select_source_index(1)

    assert "#0000ff -> #0000cc" in panel.mapping_view.mapping_label.text()
    assert "AutoMatch" in panel.mapping_view.mapping_label.text()
    assert "perceptual distance" in panel.mapping_view.mapping_label.text()


def test_palette_panel_add_color_helper_updates_render_palette(qapp):
    panel = PalettePanel()
    panel.add_color("#123456")

    assert panel.colors() == ["#123456"]
    assert panel.source_colors() == []
    assert panel.match_board.row_count() == 1
