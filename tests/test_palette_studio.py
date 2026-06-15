from pathlib import Path

import pytest
from PIL import Image

from pixelator.errors import ConfigError
from pixelator.palette_studio import (
    auto_match_palette_pairs,
    delete_palette_preset,
    extract_palette_from_image,
    hsv_position,
    list_palette_presets,
    load_lospec_palette_file,
    nearest_palette_color,
    perceptual_color_distance,
    rgb_distance,
    save_palette_preset,
    sort_palette_colors,
)


def test_extract_palette_from_image_returns_frequency_ordered_hex_colors():
    image = Image.new("RGB", (10, 1))
    image.putdata(
        [(255, 0, 0)] * 6
        + [(0, 255, 0)] * 3
        + [(0, 0, 255)]
    )

    colors = extract_palette_from_image(image, 3)

    assert colors == ["#ff0000", "#00ff00", "#0000ff"]


def test_extract_palette_from_low_color_image_can_return_fewer_than_requested():
    image = Image.new("RGB", (4, 1))
    image.putdata([(0, 0, 0), (0, 0, 0), (255, 255, 255), (255, 255, 255)])

    colors = extract_palette_from_image(image, 8)

    assert len(colors) == 2
    assert set(colors) == {"#000000", "#ffffff"}


def test_extract_palette_from_image_rejects_invalid_count():
    image = Image.new("RGB", (1, 1))

    with pytest.raises(ConfigError, match="between 2 and 256"):
        extract_palette_from_image(image, 1)


def test_load_lospec_palette_file_accepts_hash_and_plain_hex(tmp_path: Path):
    path = tmp_path / "palette.hex"
    path.write_text("#1a1c2c\n5d275d\n#1A1C2C\n", encoding="utf-8")

    colors = load_lospec_palette_file(path)

    assert colors == ["#1a1c2c", "#5d275d"]


def test_load_lospec_palette_file_rejects_files_without_colors(tmp_path: Path):
    path = tmp_path / "empty.txt"
    path.write_text("not a palette", encoding="utf-8")

    with pytest.raises(ConfigError, match="did not contain"):
        load_lospec_palette_file(path)


def test_sort_palette_colors_supports_brightness_hue_and_saturation():
    assert sort_palette_colors(["#ffffff", "#000000", "#808080"], "brightness") == [
        "#000000",
        "#808080",
        "#ffffff",
    ]
    assert sort_palette_colors(["#0000ff", "#ff0000", "#00ff00"], "hue") == [
        "#ff0000",
        "#00ff00",
        "#0000ff",
    ]
    assert sort_palette_colors(["#ff0000", "#808080"], "saturation") == ["#808080", "#ff0000"]
    assert sort_palette_colors(["#0000ff", "#ff8080", "#ff0000"], "hue_brightness") == [
        "#ff0000",
        "#ff8080",
        "#0000ff",
    ]


def test_auto_match_palette_pairs_can_use_sorted_rank_fallback():
    pairs = auto_match_palette_pairs(
        ["#0000ff", "#ff0000", "#00ff00"],
        ["#1010ff", "#ff1010"],
        "hue",
        mode="rank",
    )

    assert pairs == [
        ("#ff0000", "#ff1010"),
        ("#00ff00", "#ff1010"),
        ("#0000ff", "#1010ff"),
    ]


def test_auto_match_palette_pairs_default_to_perceptual_nearest():
    pairs = auto_match_palette_pairs(
        ["#808080", "#ff0000", "#0000ff"],
        ["#0030ff", "#777777", "#ff3300"],
        "original",
    )

    assert pairs == [
        ("#808080", "#777777"),
        ("#ff0000", "#ff3300"),
        ("#0000ff", "#0030ff"),
    ]


def test_perceptual_color_distance_prefers_similar_hue_and_neutrality():
    assert perceptual_color_distance("#808080", "#777777") < perceptual_color_distance("#808080", "#ff0000")
    assert perceptual_color_distance("#0000ff", "#0030ff") < perceptual_color_distance("#0000ff", "#ffff00")


def test_nearest_palette_color_uses_rgb_distance():
    assert nearest_palette_color("#f00000", ["#0000ff", "#ff1010", "#00ff00"]) == "#ff1010"
    assert nearest_palette_color("#f00000", []) is None


def test_rgb_distance_and_hsv_position_are_stable():
    assert rgb_distance("#000000", "#030400") == pytest.approx(5.0)
    assert hsv_position("#ff0000") == pytest.approx((0.0, 1.0))


def test_palette_preset_save_list_load_delete_round_trip(tmp_path: Path):
    saved = save_palette_preset("Test Palette", ["#000000", "#ffcc00"], tmp_path)

    presets = list_palette_presets(tmp_path)

    assert saved.exists()
    assert [preset.name for preset in presets] == ["Test Palette"]
    assert presets[0].colors == ["#000000", "#ffcc00"]

    delete_palette_preset(saved)

    assert list_palette_presets(tmp_path) == []
