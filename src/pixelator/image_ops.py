from __future__ import annotations

from PIL import Image, ImageEnhance

from pixelator.config import ImageConfig, PixelConfig


def resolve_pixel_size(size: tuple[int, int], config: PixelConfig) -> tuple[int, int]:
    width, height = size
    if config.target_width is not None:
        ratio = config.target_width / width
        return max(1, config.target_width), max(1, round(height * ratio))
    return max(1, width // config.scale), max(1, height // config.scale)


def pixelate_frame(image: Image.Image, config: PixelConfig) -> Image.Image:
    source = image.convert("RGB")
    low_size = resolve_pixel_size(source.size, config)
    low = source.resize(low_size, Image.Resampling.BOX)
    return low.resize(source.size, Image.Resampling.NEAREST)


def adjust_frame(image: Image.Image, config: ImageConfig) -> Image.Image:
    result = image.convert("RGB")
    result = ImageEnhance.Brightness(result).enhance(config.brightness)
    result = ImageEnhance.Sharpness(result).enhance(config.sharpness)
    result = ImageEnhance.Color(result).enhance(config.saturation)
    return result
