from __future__ import annotations

import numpy as np
from PIL import Image, ImageEnhance

from pixelator.config import ImageConfig, PixelConfig

_SRGB_VALUES = np.linspace(0.0, 1.0, 256, dtype=np.float32)
_SRGB_TO_LINEAR_LUT = np.where(
    _SRGB_VALUES <= 0.04045,
    _SRGB_VALUES / 12.92,
    ((_SRGB_VALUES + 0.055) / 1.055) ** 2.4,
).astype(np.float32)


def resolve_pixel_size(size: tuple[int, int], config: PixelConfig) -> tuple[int, int]:
    width, height = size
    if config.target_width is not None:
        ratio = config.target_width / width
        return max(1, config.target_width), max(1, round(height * ratio))
    return max(1, width // config.scale), max(1, height // config.scale)


def pixelate_frame(image: Image.Image, config: PixelConfig) -> Image.Image:
    low = pixelate_frame_low(image, config)
    source = image.convert("RGB")
    return low.resize(source.size, Image.Resampling.NEAREST)


def pixelate_frame_low(image: Image.Image, config: PixelConfig) -> Image.Image:
    source = image.convert("RGB")
    low_size = resolve_pixel_size(source.size, config)
    return _resize_linear_light(source, low_size)


def adjust_frame(image: Image.Image, config: ImageConfig) -> Image.Image:
    result = image.convert("RGB")
    result = ImageEnhance.Brightness(result).enhance(config.brightness)
    result = ImageEnhance.Sharpness(result).enhance(config.sharpness)
    result = ImageEnhance.Color(result).enhance(config.saturation)
    return result


def _resize_linear_light(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    if image.size == size:
        return image.copy()

    linear = _SRGB_TO_LINEAR_LUT[np.asarray(image, dtype=np.uint8)]
    resized_channels = [
        np.asarray(
            Image.fromarray(np.ascontiguousarray(linear[:, :, channel])).resize(size, Image.Resampling.BOX),
            dtype=np.float32,
        )
        for channel in range(3)
    ]
    resized_linear = np.stack(resized_channels, axis=2)
    return Image.fromarray(_linear_to_srgb(resized_linear))


def _linear_to_srgb(linear: np.ndarray) -> np.ndarray:
    clipped = np.clip(linear, 0.0, 1.0)
    srgb = np.where(
        clipped <= 0.0031308,
        clipped * 12.92,
        1.055 * np.power(clipped, 1.0 / 2.4) - 0.055,
    )
    return np.clip(np.rint(srgb * 255.0), 0, 255).astype(np.uint8)
