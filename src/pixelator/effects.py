from __future__ import annotations

import math

import numpy as np
from PIL import Image

from pixelator.config import EffectsConfig
from pixelator.palette_io import RGB

_BAYER_4 = np.array(
    [
        [0, 8, 2, 10],
        [12, 4, 14, 6],
        [3, 11, 1, 9],
        [15, 7, 13, 5],
    ],
    dtype=np.float32,
) / 16.0
_BAYER_2 = (np.array([[0, 2], [3, 1]], dtype=np.float32) + 0.5) / 4.0
_DIAMOND_CLUSTER_4 = (
    np.array(
        [
            [12, 5, 6, 13],
            [4, 0, 1, 7],
            [11, 3, 2, 8],
            [15, 10, 9, 14],
        ],
        dtype=np.float32,
    )
    + 0.5
) / 16.0
_PALETTE_CHUNK_SIZE = 32768


def apply_effects(image: Image.Image, config: EffectsConfig, frame_index: int = 0) -> Image.Image:
    result = image.convert("RGB")
    if config.crt == "subtle":
        result = _apply_scanlines(result)
    if config.vhs == "light":
        result = _apply_chroma_offset(result, config.chroma_offset)
        result = _apply_noise(result, config.noise_amount, frame_index)
    return result


def dither_enabled(config: EffectsConfig) -> bool:
    return config.dither != "off" and config.dither_strength > 0.0


def apply_palette_dither(image: Image.Image, palette: list[RGB], config: EffectsConfig) -> Image.Image:
    if not dither_enabled(config) or len(palette) < 2:
        return image.convert("RGB")

    source = np.asarray(image.convert("RGB"), dtype=np.float32)
    height, width, _channels = source.shape
    palette_array = np.asarray(palette[:256], dtype=np.float32)
    threshold = _dither_thresholds(width, height, config).reshape(-1)
    tonal_mask = _tonal_mask(source)
    mapped = _map_pixels_to_dithered_palette(
        source,
        palette_array,
        threshold,
        tonal_mask.reshape(-1),
        config.dither_strength,
        config.dither_ramp,
    )
    return Image.fromarray(mapped.reshape((height, width, 3)))


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


def _dither_thresholds(width: int, height: int, config: EffectsConfig) -> np.ndarray:
    x_rotated, y_rotated = _rotated_coordinates(width, height, config.dither_angle)
    scale = float(max(2, config.dither_scale))
    if config.dither == "diamond":
        if config.dither_scale <= 2:
            x_index = np.floor(np.mod(x_rotated, 2)).astype(np.int32)
            y_index = np.floor(np.mod(y_rotated, 2)).astype(np.int32)
            return _BAYER_2[y_index, x_index].astype(np.float32)
        x_index = np.floor(np.mod(x_rotated, scale) * 4.0 / scale).astype(np.int32)
        y_index = np.floor(np.mod(y_rotated, scale) * 4.0 / scale).astype(np.int32)
        x_index = np.clip(x_index, 0, 3)
        y_index = np.clip(y_index, 0, 3)
        return _DIAMOND_CLUSTER_4[y_index, x_index].astype(np.float32)

    x_index = np.floor(np.mod(x_rotated, scale) * 4.0 / scale).astype(np.int32)
    y_index = np.floor(np.mod(y_rotated, scale) * 4.0 / scale).astype(np.int32)
    x_index = np.clip(x_index, 0, 3)
    y_index = np.clip(y_index, 0, 3)
    return _BAYER_4[y_index, x_index].astype(np.float32)


def _rotated_coordinates(width: int, height: int, angle: float) -> tuple[np.ndarray, np.ndarray]:
    y, x = np.indices((height, width), dtype=np.float32)
    radians = math.radians(angle)
    cosine = math.cos(radians)
    sine = math.sin(radians)
    return x * cosine + y * sine, -x * sine + y * cosine


def _tonal_mask(array: np.ndarray) -> np.ndarray:
    luminance = (
        array[:, :, 0] * 0.2126 + array[:, :, 1] * 0.7152 + array[:, :, 2] * 0.0722
    ) / 255.0
    return _smoothstep(0.10, 0.28, luminance).astype(np.float32)


def _smoothstep(edge0: float, edge1: float, value: np.ndarray) -> np.ndarray:
    normalized = np.clip((value - edge0) / (edge1 - edge0), 0.0, 1.0)
    return normalized * normalized * (3.0 - 2.0 * normalized)


def _map_pixels_to_dithered_palette(
    array: np.ndarray,
    palette: np.ndarray,
    threshold: np.ndarray,
    tonal_mask: np.ndarray,
    strength: float,
    ramp: str,
) -> np.ndarray:
    if ramp == "tone":
        return _map_pixels_to_tone_ramp(array, palette, threshold, tonal_mask, strength)
    return _map_pixels_to_nearest_ramp(array, palette, threshold, tonal_mask, strength)


def _map_pixels_to_nearest_ramp(
    array: np.ndarray,
    palette: np.ndarray,
    threshold: np.ndarray,
    tonal_mask: np.ndarray,
    strength: float,
) -> np.ndarray:
    flat = array.reshape((-1, 3))
    mapped = np.empty(flat.shape, dtype=np.uint8)
    palette_uint8 = np.clip(np.rint(palette), 0, 255).astype(np.uint8)
    for start in range(0, flat.shape[0], _PALETTE_CHUNK_SIZE):
        chunk = flat[start : start + _PALETTE_CHUNK_SIZE]
        distances = _palette_distances(chunk, palette)
        nearest_two = np.argpartition(distances, 1, axis=1)[:, :2]
        nearest_two_distances = np.take_along_axis(distances, nearest_two, axis=1)
        order = np.argsort(nearest_two_distances, axis=1)
        nearest_two = np.take_along_axis(nearest_two, order, axis=1)

        nearest_indices = nearest_two[:, 0]
        second_indices = nearest_two[:, 1]
        nearest_colors = palette[nearest_indices]
        second_colors = palette[second_indices]
        toward_second = second_colors - nearest_colors
        denominator = np.sum(toward_second * toward_second, axis=1)
        denominator = np.where(denominator <= 0.0, 1.0, denominator)
        projection = np.sum((chunk - nearest_colors) * toward_second, axis=1) / denominator
        second_mix = np.clip(projection, 0.0, 0.5) * strength * tonal_mask[start : start + chunk.shape[0]]
        use_second = threshold[start : start + chunk.shape[0]] < second_mix
        choices = np.where(use_second, second_indices, nearest_indices)
        mapped[start : start + chunk.shape[0]] = palette_uint8[choices]
    return mapped


def _map_pixels_to_tone_ramp(
    array: np.ndarray,
    palette: np.ndarray,
    threshold: np.ndarray,
    tonal_mask: np.ndarray,
    strength: float,
) -> np.ndarray:
    flat = array.reshape((-1, 3))
    mapped = np.empty(flat.shape, dtype=np.uint8)
    palette_luminance = _luminance(palette)
    order = np.argsort(palette_luminance)
    ramp_palette = palette[order]
    ramp_luminance = palette_luminance[order]
    palette_uint8 = np.clip(np.rint(ramp_palette), 0, 255).astype(np.uint8)

    for start in range(0, flat.shape[0], _PALETTE_CHUNK_SIZE):
        chunk = flat[start : start + _PALETTE_CHUNK_SIZE]
        luminance = _luminance(chunk)
        upper_indices = np.searchsorted(ramp_luminance, luminance, side="right")
        upper_indices = np.clip(upper_indices, 1, len(ramp_luminance) - 1)
        lower_indices = upper_indices - 1
        lower_luminance = ramp_luminance[lower_indices]
        upper_luminance = ramp_luminance[upper_indices]
        span = np.maximum(upper_luminance - lower_luminance, 1.0)
        mix = np.clip((luminance - lower_luminance) / span, 0.0, 1.0)
        mix *= strength * tonal_mask[start : start + chunk.shape[0]]
        use_upper = threshold[start : start + chunk.shape[0]] < mix
        choices = np.where(use_upper, upper_indices, lower_indices)
        mapped[start : start + chunk.shape[0]] = palette_uint8[choices]
    return mapped


def _luminance(array: np.ndarray) -> np.ndarray:
    return array[:, 0] * 0.2126 + array[:, 1] * 0.7152 + array[:, 2] * 0.0722


def _palette_distances(chunk: np.ndarray, palette: np.ndarray) -> np.ndarray:
    difference = chunk[:, None, :] - palette[None, :, :]
    return np.sum(difference * difference, axis=2)
