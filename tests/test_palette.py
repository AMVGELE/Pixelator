from PIL import Image

from pixelator.config import PaletteConfig
from pixelator.palette import (
    apply_auto_match_palette,
    apply_palette,
    build_global_palette,
    quantize_per_frame,
    unique_rgb_count,
)
from pixelator.palette_io import load_palette_file, parse_palette_colors, save_palette_file


def test_quantize_per_frame_limits_unique_colors():
    image = Image.linear_gradient("L").resize((32, 32)).convert("RGB")

    result = quantize_per_frame(image, PaletteConfig(colors=8))

    assert unique_rgb_count(result) <= 8


def test_build_global_palette_returns_requested_color_count_or_less():
    frames = [
        Image.new("RGB", (8, 8), (255, 0, 0)),
        Image.new("RGB", (8, 8), (0, 255, 0)),
        Image.new("RGB", (8, 8), (0, 0, 255)),
    ]

    palette = build_global_palette(frames, PaletteConfig(colors=4))

    assert 1 <= len(palette) <= 4


def test_apply_palette_uses_palette_colors():
    image = Image.linear_gradient("L").resize((16, 16)).convert("RGB")
    palette = [(0, 0, 0), (255, 255, 255)]

    result = apply_palette(image, palette)

    assert unique_rgb_count(result) <= 2


def test_parse_palette_colors_accepts_strict_hex_values():
    assert parse_palette_colors(["#000000", "#ffcc00"]) == [(0, 0, 0), (255, 204, 0)]


def test_apply_custom_palette_limits_output_to_selected_colors():
    image = Image.linear_gradient("L").resize((16, 16)).convert("RGB")
    palette = parse_palette_colors(["#000000", "#ffffff"])

    result = apply_palette(image, palette)

    assert set(result.getdata()).issubset({(0, 0, 0), (255, 255, 255)})


def test_apply_auto_match_palette_maps_source_to_render_pairs():
    image = Image.new("RGB", (2, 1))
    image.putdata([(250, 0, 0), (0, 0, 250)])

    result = apply_auto_match_palette(
        image,
        ["#ff0000", "#0000ff"],
        ["#0000cc", "#ff3300"],
        "original",
    )

    assert list(result.getdata()) == [(255, 51, 0), (0, 0, 204)]


def test_apply_auto_match_palette_falls_back_when_source_palette_misses_pixel_color():
    image = Image.new("RGB", (2, 1))
    image.putdata([(240, 240, 240), (34, 34, 40)])

    result = apply_auto_match_palette(
        image,
        ["#202020", "#303038"],
        ["#000000", "#eeeeee"],
        "original",
    )

    assert list(result.getdata()) == [(238, 238, 238), (0, 0, 0)]


def test_palette_file_round_trips_named_yaml(tmp_path):
    path = tmp_path / "palette.yaml"

    save_palette_file(path, ["#1a1c2c", "#ffcc00"], name="Test Palette")

    loaded = load_palette_file(path)

    assert loaded.name == "Test Palette"
    assert loaded.colors == ["#1a1c2c", "#ffcc00"]


def test_palette_file_loads_raw_color_list(tmp_path):
    path = tmp_path / "palette.yaml"
    path.write_text('["#000000", "#ffffff"]', encoding="utf-8")

    loaded = load_palette_file(path)

    assert loaded.colors == ["#000000", "#ffffff"]
