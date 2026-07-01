from PIL import Image

from pixelator.config import EffectsConfig
from pixelator.effects import apply_effects, apply_palette_dither, dither_enabled


def test_effects_off_returns_equivalent_image():
    image = Image.new("RGB", (8, 8), (100, 120, 140))

    result = apply_effects(image, EffectsConfig(crt="off", vhs="off"))

    assert list(result.getdata()) == list(image.getdata())


def test_default_effects_do_not_create_scanlines_on_solid_color():
    image = Image.new("RGB", (8, 8), (100, 120, 140))

    result = apply_effects(image, EffectsConfig())

    assert len({result.getpixel((0, y)) for y in range(result.height)}) == 1
    assert list(result.getdata()) == list(image.getdata())


def test_dither_enabled_requires_mode_and_strength():
    assert not dither_enabled(EffectsConfig(dither="off", dither_strength=1.0))
    assert not dither_enabled(EffectsConfig(dither="diamond", dither_strength=0.0))
    assert dither_enabled(EffectsConfig(dither="diamond", dither_strength=0.5))


def test_subtle_crt_lightly_darkens_every_other_row():
    image = Image.new("RGB", (4, 4), (100, 100, 100))

    result = apply_effects(image, EffectsConfig(crt="subtle", vhs="off"))

    assert result.getpixel((0, 1))[0] < result.getpixel((0, 0))[0]
    assert result.getpixel((0, 1))[0] >= 93


def test_light_vhs_is_deterministic_for_frame_index():
    image = Image.new("RGB", (8, 8), (100, 120, 140))
    config = EffectsConfig(crt="off", vhs="light", noise_amount=0.02)

    first = apply_effects(image, config, frame_index=7)
    second = apply_effects(image, config, frame_index=7)

    assert list(first.getdata()) == list(second.getdata())


def test_light_vhs_noise_does_not_shatter_solid_pixel_blocks():
    image = Image.new("RGB", (16, 16), (32, 38, 58))
    for y in range(4, 12):
        for x in range(4, 12):
            image.putpixel((x, y), (20, 24, 36))

    result = apply_effects(
        image,
        EffectsConfig(crt="off", vhs="light", chroma_offset=0, noise_amount=0.006),
        frame_index=0,
    )
    center_colors = {result.getpixel((x, y)) for y in range(4, 12) for x in range(4, 12)}

    assert len(center_colors) <= 4


def test_chroma_offset_does_not_wrap_pixels_across_edges():
    image = Image.new("RGB", (6, 1), (0, 0, 0))
    image.putpixel((5, 0), (255, 0, 0))

    result = apply_effects(
        image,
        EffectsConfig(crt="off", vhs="light", chroma_offset=1, noise_amount=0),
        frame_index=0,
    )

    assert result.getpixel((0, 0)) == (0, 0, 0)


def test_diamond_dither_is_deterministic_and_palette_bounded():
    image = Image.linear_gradient("L").resize((16, 16)).convert("RGB")
    palette = [(0, 0, 0), (96, 96, 96), (192, 192, 192), (255, 255, 255)]
    config = EffectsConfig(dither="diamond", dither_strength=0.8, dither_scale=4, dither_angle=45.0)

    first = apply_palette_dither(image, palette, config)
    second = apply_palette_dither(image, palette, config)

    colors = set(first.getdata())
    assert list(first.getdata()) == list(second.getdata())
    assert colors.issubset(set(palette))
    assert len(colors) > 2


def test_diamond_dither_inserts_neighbor_color_as_pixel_dots():
    image = Image.new("RGB", (8, 8), (128, 128, 128))
    palette = [(0, 0, 0), (255, 255, 255)]
    config = EffectsConfig(dither="diamond", dither_strength=1.0, dither_scale=2, dither_angle=0.0)

    result = apply_palette_dither(image, palette, config)

    colors = set(result.getdata())
    dark_count = list(result.getdata()).count((0, 0, 0))
    assert colors == {(0, 0, 0), (255, 255, 255)}
    assert dark_count == 32
    assert result.getpixel((0, 0)) == (0, 0, 0)
    assert result.getpixel((1, 0)) == (255, 255, 255)


def test_tone_ramp_dither_uses_ordered_luminance_steps():
    image = Image.new("RGB", (8, 8), (64, 64, 64))
    palette = [(0, 0, 0), (128, 128, 128), (255, 255, 255)]
    config = EffectsConfig(dither="diamond", dither_ramp="tone", dither_strength=1.0, dither_scale=2)

    result = apply_palette_dither(image, palette, config)

    colors = set(result.getdata())
    mid_count = list(result.getdata()).count((128, 128, 128))
    assert colors == {(0, 0, 0), (128, 128, 128)}
    assert mid_count == 32


def test_diamond_dither_keeps_deep_shadow_stable():
    image = Image.new("RGB", (8, 8), (16, 16, 18))
    palette = [(0, 0, 0), (80, 80, 88)]
    config = EffectsConfig(dither="diamond", dither_strength=1.0, dither_scale=4)

    result = apply_palette_dither(image, palette, config)

    assert set(result.getdata()) == {(0, 0, 0)}
