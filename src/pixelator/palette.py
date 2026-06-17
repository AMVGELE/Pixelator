from __future__ import annotations

from collections.abc import Iterable

from PIL import Image

from pixelator.config import PaletteConfig
from pixelator.palette_io import RGB, parse_hex_color, parse_palette_colors
from pixelator.palette_studio import auto_match_palette_pairs, perceptual_color_distance, rgb_to_hex

_AUTO_MATCH_SOURCE_DISTANCE_LIMIT = 0.18
_AUTO_MATCH_TARGET_DISTANCE_MARGIN = 0.04


def quantize_per_frame(image: Image.Image, config: PaletteConfig) -> Image.Image:
    return (
        image.convert("RGB")
        .quantize(colors=config.colors, dither=Image.Dither.NONE)
        .convert("RGB")
    )


def build_global_palette(frames: Iterable[Image.Image], config: PaletteConfig) -> list[RGB]:
    prepared = [frame.convert("RGB").resize((64, 64), Image.Resampling.BOX) for frame in frames]
    if not prepared:
        return [(0, 0, 0)]
    atlas = Image.new("RGB", (64, 64 * len(prepared)))
    for index, frame in enumerate(prepared):
        atlas.paste(frame, (0, index * 64))
    quantized = atlas.quantize(colors=config.colors, dither=Image.Dither.NONE)
    raw_palette = quantized.getpalette() or []
    used_indices = sorted(set(quantized.getdata()))
    colors: list[RGB] = []
    for index in used_indices[: config.colors]:
        offset = index * 3
        colors.append(tuple(raw_palette[offset : offset + 3]))  # type: ignore[arg-type]
    return colors or [(0, 0, 0)]


def custom_palette(config: PaletteConfig) -> list[RGB] | None:
    if config.strategy != "custom" or config.custom_colors is None:
        return None
    return parse_palette_colors(config.custom_colors)


def auto_match_palette(config: PaletteConfig) -> tuple[list[str], list[str], str] | None:
    if config.strategy != "auto_match" or config.source_colors is None or config.custom_colors is None:
        return None
    return config.source_colors, config.custom_colors, config.match_sort


def apply_palette(image: Image.Image, palette: list[RGB]) -> Image.Image:
    palette_image = Image.new("P", (1, 1))
    flat: list[int] = []
    for color in palette[:256]:
        flat.extend(color)
    flat.extend([0] * (768 - len(flat)))
    palette_image.putpalette(flat)
    return image.convert("RGB").quantize(palette=palette_image, dither=Image.Dither.NONE).convert("RGB")


def apply_auto_match_palette(
    image: Image.Image,
    source_colors: list[str],
    target_colors: list[str],
    sort_mode: str,
) -> Image.Image:
    source_palette = parse_palette_colors(source_colors)
    pairs = dict(auto_match_palette_pairs(source_colors, target_colors, sort_mode))
    if not source_palette or not pairs:
        return image.convert("RGB")

    palette_image = Image.new("P", (1, 1))
    flat: list[int] = []
    for color in source_palette[:256]:
        flat.extend(color)
    flat.extend([0] * (768 - len(flat)))
    palette_image.putpalette(flat)

    quantized = image.convert("RGB").quantize(palette=palette_image, dither=Image.Dither.NONE)
    pixel_data = quantized.get_flattened_data() if hasattr(quantized, "get_flattened_data") else quantized.getdata()
    source_hex = [rgb_to_hex(color) for color in source_palette]
    fallback = next(iter(pairs.values()))
    normalized_targets = list(dict.fromkeys(target_colors))
    target_rgb = {color: parse_hex_color(color) for color in set([*pairs.values(), *normalized_targets])}
    source_rgb = {color: parse_hex_color(color) for color in source_hex}
    source_data = list(pixel_data)
    original_data = list(image.convert("RGB").getdata())
    choice_cache: dict[tuple[RGB, int], RGB] = {}
    mapped = [
        _guarded_auto_match_color(
            pixel,
            source_data[index],
            source_hex,
            pairs,
            fallback,
            normalized_targets,
            source_rgb,
            target_rgb,
            choice_cache,
        )
        for index, pixel in enumerate(original_data)
    ]

    result = Image.new("RGB", image.size)
    result.putdata(mapped)
    return result


def _guarded_auto_match_color(
    pixel: RGB,
    source_index: int,
    source_hex: list[str],
    pairs: dict[str, str],
    fallback: str,
    target_colors: list[str],
    source_rgb: dict[str, RGB],
    target_rgb: dict[str, RGB],
    choice_cache: dict[tuple[RGB, int], RGB],
) -> RGB:
    cache_key = (pixel, source_index)
    cached = choice_cache.get(cache_key)
    if cached is not None:
        return cached

    matched_source = source_hex[source_index] if source_index < len(source_hex) else source_hex[0]
    mapped_target = pairs.get(matched_source, fallback)
    mapped_rgb = target_rgb[mapped_target]
    source_distance = perceptual_color_distance(pixel, source_rgb[matched_source])
    if source_distance <= _AUTO_MATCH_SOURCE_DISTANCE_LIMIT:
        choice_cache[cache_key] = mapped_rgb
        return mapped_rgb

    direct_target = min(target_colors, key=lambda color: perceptual_color_distance(pixel, target_rgb[color]))
    direct_rgb = target_rgb[direct_target]
    direct_distance = perceptual_color_distance(pixel, direct_rgb)
    mapped_distance = perceptual_color_distance(pixel, mapped_rgb)
    if direct_distance + _AUTO_MATCH_TARGET_DISTANCE_MARGIN < mapped_distance:
        choice_cache[cache_key] = direct_rgb
        return direct_rgb

    choice_cache[cache_key] = mapped_rgb
    return mapped_rgb


def unique_rgb_count(image: Image.Image) -> int:
    return len(set(image.convert("RGB").getdata()))
