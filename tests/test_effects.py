from PIL import Image

from pixelator.config import EffectsConfig
from pixelator.effects import apply_effects


def test_effects_off_returns_equivalent_image():
    image = Image.new("RGB", (8, 8), (100, 120, 140))

    result = apply_effects(image, EffectsConfig(crt="off", vhs="off"))

    assert list(result.getdata()) == list(image.getdata())


def test_subtle_crt_darkens_every_other_row():
    image = Image.new("RGB", (4, 4), (100, 100, 100))

    result = apply_effects(image, EffectsConfig(crt="subtle", vhs="off"))

    assert result.getpixel((0, 1))[0] < result.getpixel((0, 0))[0]


def test_light_vhs_is_deterministic_for_frame_index():
    image = Image.new("RGB", (8, 8), (100, 120, 140))
    config = EffectsConfig(crt="off", vhs="light", noise_amount=0.02)

    first = apply_effects(image, config, frame_index=7)
    second = apply_effects(image, config, frame_index=7)

    assert list(first.getdata()) == list(second.getdata())
