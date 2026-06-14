from PIL import Image

from pixelator.config import PaletteConfig
from pixelator.palette import apply_palette, build_global_palette, quantize_per_frame, unique_rgb_count


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
