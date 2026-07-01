from PIL import Image

from pixelator.palette_io import parse_hex_color
from pixelator.style_filters import (
    PALETTE_MODE_AUTO_PRESERVE_LIGHTS,
    PALETTE_MODE_AUTO_UNIFIED,
    PALETTE_MODE_FIXED,
    STYLE_FILTERS,
    generate_palette_for_style,
    style_filter_by_id,
)


def test_style_filter_ids_labels_and_palettes_are_valid():
    ids = [style.id for style in STYLE_FILTERS]
    labels = [style.label for style in STYLE_FILTERS]

    assert len(ids) == len(set(ids))
    assert len(labels) == len(set(labels))
    for style in STYLE_FILTERS:
        if not style.palette:
            continue
        assert len(style.palette) == style.colors
        for color in style.palette:
            parse_hex_color(color)


def test_fixed_style_palette_uses_builtin_colors():
    style = style_filter_by_id("dark_fantasy_dither")

    generated = generate_palette_for_style(None, style.id, PALETTE_MODE_FIXED)

    assert generated.render_colors == style.palette
    assert generated.source_colors == []
    assert generated.auto_match is False


def test_auto_unified_palette_keeps_style_color_count():
    image = Image.new("RGB", (8, 1))
    image.putdata(
        [
            (8, 9, 10),
            (18, 20, 22),
            (40, 48, 52),
            (70, 84, 90),
            (96, 110, 116),
            (130, 135, 138),
            (165, 168, 166),
            (210, 210, 204),
        ]
    )

    generated = generate_palette_for_style(image, "cold_sci_fi_dither", PALETTE_MODE_AUTO_UNIFIED)

    assert len(generated.render_colors) == style_filter_by_id("cold_sci_fi_dither").colors
    assert len(generated.source_colors) >= 2
    assert generated.auto_match is False


def test_auto_preserve_lights_keeps_saturated_accents():
    image = Image.new("RGB", (9, 1))
    image.putdata(
        [
            (6, 6, 8),
            (20, 22, 26),
            (45, 52, 60),
            (70, 74, 78),
            (210, 28, 24),
            (24, 86, 240),
            (245, 245, 250),
            (12, 12, 12),
            (36, 36, 38),
        ]
    )

    generated = generate_palette_for_style(image, "dark_fantasy_dither", PALETTE_MODE_AUTO_PRESERVE_LIGHTS)
    rgbs = [parse_hex_color(color) for color in generated.render_colors]

    assert len(generated.render_colors) == style_filter_by_id("dark_fantasy_dither").colors
    assert any(red > 120 and red > blue * 1.4 for red, _green, blue in rgbs)
    assert any(blue > 140 and blue > red * 1.4 for red, _green, blue in rgbs)
