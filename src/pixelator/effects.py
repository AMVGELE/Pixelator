from __future__ import annotations

import numpy as np
from PIL import Image, ImageChops

from pixelator.config import EffectsConfig


def apply_effects(image: Image.Image, config: EffectsConfig, frame_index: int = 0) -> Image.Image:
    result = image.convert("RGB")
    if config.crt == "subtle":
        result = _apply_scanlines(result)
    if config.vhs == "light":
        result = _apply_chroma_offset(result, config.chroma_offset)
        result = _apply_noise(result, config.noise_amount, frame_index)
    return result


def _apply_scanlines(image: Image.Image) -> Image.Image:
    array = np.array(image).astype(np.float32)
    array[1::2, :, :] *= 0.78
    return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8))


def _apply_chroma_offset(image: Image.Image, offset: int) -> Image.Image:
    if offset <= 0:
        return image
    red, green, blue = image.split()
    red = ImageChops.offset(red, offset, 0)
    blue = ImageChops.offset(blue, -offset, 0)
    return Image.merge("RGB", (red, green, blue))


def _apply_noise(image: Image.Image, amount: float, frame_index: int) -> Image.Image:
    if amount <= 0:
        return image
    rng = np.random.default_rng(seed=frame_index)
    array = np.array(image).astype(np.float32)
    noise = rng.normal(0, 255 * amount, array.shape)
    return Image.fromarray(np.clip(array + noise, 0, 255).astype(np.uint8))
