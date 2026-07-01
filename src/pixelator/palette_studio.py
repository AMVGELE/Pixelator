from __future__ import annotations

import colorsys
import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from pixelator.errors import ConfigError
from pixelator.palette_io import RGB, load_palette_file, normalize_hex_colors, parse_hex_color, save_palette_file

_LOSPEC_TOKEN = re.compile(r"#?[0-9a-fA-F]{6}")


@dataclass(frozen=True)
class PalettePreset:
    name: str
    path: Path
    colors: list[str]


def extract_palette_from_image(image: Image.Image, count: int, method: str = "dominant") -> list[str]:
    if not 2 <= count <= 256:
        raise ConfigError("palette extract count must be between 2 and 256")

    source = image.convert("RGB")
    if method == "dominant":
        return _extract_dominant_palette(source, count)
    if method == "balanced_hue":
        return _extract_balanced_hue_palette(source, count)
    if method == "tonal":
        return _extract_tonal_palette(source, count)
    raise ConfigError("palette extract method must be dominant, balanced_hue, or tonal")


def _extract_dominant_palette(source: Image.Image, count: int) -> list[str]:
    return [color for color, _frequency in _quantized_color_counts(source, count)][:count]


def _extract_balanced_hue_palette(source: Image.Image, count: int) -> list[str]:
    candidates = _quantized_color_counts(source, min(256, max(count * 4, count)))
    buckets: dict[int, list[str]] = {}
    for color, _frequency in candidates:
        hue, saturation, _value = _hsv(parse_hex_color(color))
        bucket = 12 if saturation < 0.12 else min(11, int(hue * 12))
        buckets.setdefault(bucket, []).append(color)

    result: list[str] = []
    bucket_order = [key for key in sorted(buckets) if key != 12]
    if 12 in buckets:
        bucket_order.append(12)
    while len(result) < count and bucket_order:
        progressed = False
        for key in bucket_order:
            if buckets[key]:
                color = buckets[key].pop(0)
                if color not in result:
                    result.append(color)
                    progressed = True
                if len(result) >= count:
                    break
        if not progressed:
            break
    return result


def _extract_tonal_palette(source: Image.Image, count: int) -> list[str]:
    groups: list[list[RGB]] = [[], [], []]
    for pixel in source.getdata():
        rgb = pixel[:3] if isinstance(pixel, tuple) else (pixel, pixel, pixel)
        luminance = _luminance(rgb)  # type: ignore[arg-type]
        if luminance < 85:
            groups[0].append(rgb)  # type: ignore[arg-type]
        elif luminance < 170:
            groups[1].append(rgb)  # type: ignore[arg-type]
        else:
            groups[2].append(rgb)  # type: ignore[arg-type]

    non_empty = [(index, pixels) for index, pixels in enumerate(groups) if pixels]
    if not non_empty:
        return []

    allocations = _tonal_allocations([len(pixels) for _index, pixels in non_empty], count)
    result: list[str] = []
    for (_index, pixels), quota in zip(non_empty, allocations, strict=True):
        group_image = Image.new("RGB", (len(pixels), 1))
        group_image.putdata(pixels)
        for color in _extract_dominant_palette(group_image, min(256, quota)):
            if color not in result:
                result.append(color)
            if len(result) >= count:
                return result
    return result


def _tonal_allocations(group_sizes: list[int], count: int) -> list[int]:
    allocations = [1 for _size in group_sizes]
    remaining = max(0, count - len(allocations))
    total = sum(group_sizes)
    if total <= 0:
        return allocations
    shares = [(size / total) * remaining for size in group_sizes]
    for index, share in enumerate(shares):
        extra = int(share)
        allocations[index] += extra
        remaining -= extra
    remainders = sorted(
        range(len(group_sizes)),
        key=lambda index: shares[index] - int(shares[index]),
        reverse=True,
    )
    for index in remainders[:remaining]:
        allocations[index] += 1
    return allocations


def _quantized_color_counts(source: Image.Image, count: int) -> list[tuple[str, int]]:
    quantized = source.quantize(colors=count, dither=Image.Dither.NONE)
    raw_palette = quantized.getpalette() or []
    pixel_data = quantized.get_flattened_data() if hasattr(quantized, "get_flattened_data") else quantized.getdata()
    counts = Counter(pixel_data)

    colors: list[tuple[str, int]] = []
    for index, _frequency in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        offset = index * 3
        rgb = tuple(raw_palette[offset : offset + 3])
        if len(rgb) != 3:
            continue
        color = rgb_to_hex(rgb)  # type: ignore[arg-type]
        if color not in [existing for existing, _count in colors]:
            colors.append((color, int(_frequency)))
    return colors[:count]


def load_lospec_palette_file(path: str | Path) -> list[str]:
    palette_path = Path(path)
    try:
        text = palette_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Could not read Lospec palette file: {palette_path}") from exc

    colors: list[str] = []
    for match in _LOSPEC_TOKEN.finditer(text):
        color = match.group(0)
        if not color.startswith("#"):
            color = f"#{color}"
        normalized = color.lower()
        if normalized not in colors:
            colors.append(normalized)
    if not colors:
        raise ConfigError("Lospec palette file did not contain any #RRGGBB colors")
    return colors


def sort_palette_colors(colors: list[str], mode: str) -> list[str]:
    normalized = normalize_hex_colors(colors)
    if mode == "original":
        return normalized
    if mode == "brightness":
        return sorted(normalized, key=lambda color: _luminance(parse_hex_color(color)))
    if mode == "hue":
        return sorted(normalized, key=lambda color: _hsv(parse_hex_color(color))[0])
    if mode == "hue_brightness":
        return sorted(
            normalized,
            key=lambda color: (
                round(_hsv(parse_hex_color(color))[0], 4),
                _luminance(parse_hex_color(color)),
            ),
        )
    if mode == "saturation":
        return sorted(normalized, key=lambda color: _hsv(parse_hex_color(color))[1])
    raise ConfigError("palette sort mode must be original, brightness, hue, hue_brightness, or saturation")


def auto_match_palette_pairs(
    source_colors: list[str],
    target_colors: list[str],
    sort_mode: str = "hue_brightness",
    mode: str = "perceptual",
) -> list[tuple[str, str]]:
    source = normalize_hex_colors(source_colors)
    target = normalize_hex_colors(target_colors)
    if not source or not target:
        return []
    if mode == "perceptual":
        source_rank_positions, target_rank_positions = _rank_fallback_positions(source, target, sort_mode)
        return [
            (
                source_color,
                min(
                    target,
                    key=lambda target_color: (
                        perceptual_color_distance(source_color, target_color),
                        _rank_fallback_distance(source_color, target_color, source_rank_positions, target_rank_positions),
                    ),
                ),
            )
            for source_color in source
        ]
    if mode == "rank":
        return _rank_match_palette_pairs(source, target, sort_mode)
    raise ConfigError("palette auto match mode must be perceptual or rank")


def perceptual_color_distance(a: str | RGB, b: str | RGB) -> float:
    first = _oklab(_as_rgb(a))
    second = _oklab(_as_rgb(b))
    lightness = (first[0] - second[0]) * 1.25
    green_red = first[1] - second[1]
    blue_yellow = first[2] - second[2]
    chroma = (_chroma(first) - _chroma(second)) * 0.5
    return math.sqrt(lightness * lightness + green_red * green_red + blue_yellow * blue_yellow + chroma * chroma)


def _rank_match_palette_pairs(source_colors: list[str], target_colors: list[str], sort_mode: str) -> list[tuple[str, str]]:
    source = sort_palette_colors(source_colors, sort_mode)
    target = sort_palette_colors(target_colors, sort_mode)
    if not source or not target:
        return []
    if len(source) == 1:
        return [(source[0], target[0])]
    scale = (len(target) - 1) / (len(source) - 1) if len(target) > 1 else 0.0
    return [(source_color, target[round(index * scale)]) for index, source_color in enumerate(source)]


def _rank_fallback_positions(
    source_colors: list[str],
    target_colors: list[str],
    sort_mode: str,
) -> tuple[dict[str, float], dict[str, float]]:
    try:
        source_sorted = sort_palette_colors(source_colors, sort_mode)
        target_sorted = sort_palette_colors(target_colors, sort_mode)
    except ConfigError:
        return {}, {}
    return (
        {color: _normalized_rank(source_sorted, color) for color in source_sorted},
        {color: _normalized_rank(target_sorted, color) for color in target_sorted},
    )


def _rank_fallback_distance(
    source_color: str,
    target_color: str,
    source_rank_positions: dict[str, float],
    target_rank_positions: dict[str, float],
) -> float:
    if not source_rank_positions or not target_rank_positions:
        return 0.0
    return abs(source_rank_positions.get(source_color, 0.0) - target_rank_positions.get(target_color, 0.0))


def nearest_palette_color(source: str, palette: list[str]) -> str | None:
    normalized = normalize_hex_colors(palette)
    if not normalized:
        return None
    return min(normalized, key=lambda color: rgb_distance(source, color))


def rgb_distance(a: str | RGB, b: str | RGB) -> float:
    first = _as_rgb(a)
    second = _as_rgb(b)
    return math.sqrt(sum((first[index] - second[index]) ** 2 for index in range(3)))


def hsv_position(color: str) -> tuple[float, float]:
    rgb = parse_hex_color(color)
    hue, _saturation, value = _hsv(rgb)
    return hue, value


def default_palette_preset_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Pixelator" / "palettes"
    return Path.home() / ".pixelator" / "palettes"


def list_palette_presets(directory: str | Path | None = None) -> list[PalettePreset]:
    preset_dir = Path(directory) if directory is not None else default_palette_preset_dir()
    if not preset_dir.exists():
        return []

    presets: list[PalettePreset] = []
    for path in sorted([*preset_dir.glob("*.yaml"), *preset_dir.glob("*.yml")]):
        try:
            palette = load_palette_file(path)
        except ConfigError:
            continue
        presets.append(PalettePreset(name=palette.name or path.stem, path=path, colors=palette.colors))
    return sorted(presets, key=lambda preset: preset.name.lower())


def save_palette_preset(name: str, colors: list[str], directory: str | Path | None = None) -> Path:
    preset_name = name.strip()
    if not preset_name:
        raise ConfigError("palette preset name is required")
    preset_dir = Path(directory) if directory is not None else default_palette_preset_dir()
    path = preset_dir / f"{_slugify_preset_name(preset_name)}.yaml"
    save_palette_file(path, colors, name=preset_name)
    return path


def delete_palette_preset(path: str | Path) -> None:
    preset_path = Path(path)
    try:
        preset_path.unlink()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ConfigError(f"Could not delete palette preset: {preset_path}") from exc


def rgb_to_hex(rgb: RGB) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _slugify_preset_name(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip()).strip("-").lower()
    if not slug:
        raise ConfigError("palette preset name must contain letters or numbers")
    return slug


def _luminance(rgb: RGB) -> float:
    return (0.299 * rgb[0]) + (0.587 * rgb[1]) + (0.114 * rgb[2])


def _hsv(rgb: RGB) -> tuple[float, float, float]:
    return colorsys.rgb_to_hsv(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)


def _as_rgb(color: str | RGB) -> RGB:
    if isinstance(color, str):
        return parse_hex_color(color)
    return color


def _normalized_rank(colors: list[str], color: str) -> float:
    if len(colors) <= 1:
        return 0.0
    try:
        return colors.index(color) / (len(colors) - 1)
    except ValueError:
        return 0.0


def _oklab(rgb: RGB) -> tuple[float, float, float]:
    red = _srgb_to_linear(rgb[0] / 255)
    green = _srgb_to_linear(rgb[1] / 255)
    blue = _srgb_to_linear(rgb[2] / 255)

    lms_l = 0.4122214708 * red + 0.5363325363 * green + 0.0514459929 * blue
    lms_m = 0.2119034982 * red + 0.6806995451 * green + 0.1073969566 * blue
    lms_s = 0.0883024619 * red + 0.2817188376 * green + 0.6299787005 * blue

    l_ = math.copysign(abs(lms_l) ** (1 / 3), lms_l)
    m_ = math.copysign(abs(lms_m) ** (1 / 3), lms_m)
    s_ = math.copysign(abs(lms_s) ** (1 / 3), lms_s)

    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def _srgb_to_linear(value: float) -> float:
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def _chroma(oklab: tuple[float, float, float]) -> float:
    return math.sqrt(oklab[1] * oklab[1] + oklab[2] * oklab[2])
