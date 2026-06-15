from __future__ import annotations

import numpy as np
from PIL import Image

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
    array[1::2, :, :] *= 0.94
    return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8))


def _apply_chroma_offset(image: Image.Image, offset: int) -> Image.Image:
    if offset <= 0:
        return image
    red, green, blue = image.split()
    red = _shift_channel_no_wrap(red, offset)
    blue = _shift_channel_no_wrap(blue, -offset)
    return Image.merge("RGB", (red, green, blue))


def _shift_channel_no_wrap(channel: Image.Image, offset: int) -> Image.Image:
    if offset == 0:
        return channel

    width, height = channel.size
    shift = min(abs(offset), width)
    shifted = Image.new(channel.mode, channel.size)
    if offset > 0:
        if width > shift:
            shifted.paste(channel.crop((0, 0, width - shift, height)), (shift, 0))
        edge = channel.crop((0, 0, 1, height)).resize((shift, height))
        shifted.paste(edge, (0, 0))
        return shifted

    if width > shift:
        shifted.paste(channel.crop((shift, 0, width, height)), (0, 0))
    edge = channel.crop((width - 1, 0, width, height)).resize((shift, height))
    shifted.paste(edge, (width - shift, 0))
    return shifted


def _apply_noise(image: Image.Image, amount: float, frame_index: int) -> Image.Image:
    if amount <= 0:
        return image
    rng = np.random.default_rng(seed=frame_index)
    array = np.array(image).astype(np.float32)
    height, width, _channels = array.shape
    cell_size = 8
    noise_width = max(1, (width + cell_size - 1) // cell_size)
    noise_height = max(1, (height + cell_size - 1) // cell_size)
    coarse = rng.normal(0, 255 * amount, (noise_height, noise_width)).astype(np.float32)
    noise = np.asarray(
        Image.fromarray(coarse).resize((width, height), Image.Resampling.NEAREST),
        dtype=np.float32,
    )
    return Image.fromarray(np.clip(array + noise[:, :, None], 0, 255).astype(np.uint8))
