from PIL import Image

from pixelator.config import ImageConfig, PixelConfig
from pixelator.image_ops import adjust_frame, pixelate_frame, resolve_pixel_size


def test_resolve_pixel_size_uses_scale():
    assert resolve_pixel_size((320, 180), PixelConfig(scale=4)) == (80, 45)


def test_resolve_pixel_size_uses_target_width():
    assert resolve_pixel_size((320, 180), PixelConfig(scale=4, target_width=160)) == (160, 90)


def test_pixelate_frame_preserves_original_dimensions():
    image = Image.new("RGB", (32, 16), (120, 80, 40))

    result = pixelate_frame(image, PixelConfig(scale=4))

    assert result.size == (32, 16)
    assert result.mode == "RGB"


def test_adjust_frame_changes_saturation_without_changing_size():
    image = Image.new("RGB", (8, 8), (120, 80, 40))

    result = adjust_frame(image, ImageConfig(brightness=1.0, sharpness=1.0, saturation=1.5))

    assert result.size == image.size
    assert result.mode == "RGB"
