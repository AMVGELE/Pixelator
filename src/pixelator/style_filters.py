from __future__ import annotations

import colorsys
from dataclasses import dataclass

from PIL import Image

from pixelator.errors import ConfigError
from pixelator.palette_io import RGB, normalize_hex_color, parse_hex_color
from pixelator.palette_studio import extract_palette_from_image, perceptual_color_distance, rgb_to_hex

PALETTE_MODE_FIXED = "fixed"
PALETTE_MODE_AUTO_UNIFIED = "auto_unified"
PALETTE_MODE_AUTO_PRESERVE_LIGHTS = "auto_preserve_lights"
PALETTE_MODES = {
    PALETTE_MODE_FIXED,
    PALETTE_MODE_AUTO_UNIFIED,
    PALETTE_MODE_AUTO_PRESERVE_LIGHTS,
}


@dataclass(frozen=True)
class StyleFilter:
    id: str
    label: str
    pixel_scale: int
    colors: int
    brightness: float
    sharpness: float
    saturation: float
    crt: str
    vhs: str
    dither: str
    dither_ramp: str
    dither_space: str
    dither_strength: float
    dither_scale: int
    dither_angle: float
    palette: list[str]


@dataclass(frozen=True)
class GeneratedPalette:
    source_colors: list[str]
    render_colors: list[str]
    auto_match: bool = False


STYLE_FILTERS: tuple[StyleFilter, ...] = (
    StyleFilter(
        id="clean_pixel",
        label="干净像素",
        pixel_scale=4,
        colors=32,
        brightness=1.0,
        sharpness=1.2,
        saturation=1.1,
        crt="off",
        vhs="off",
        dither="off",
        dither_ramp="nearest",
        dither_space="output",
        dither_strength=0.45,
        dither_scale=4,
        dither_angle=0.0,
        palette=[],
    ),
    StyleFilter(
        id="dark_fantasy_dither",
        label="暗黑幻想抖动",
        pixel_scale=2,
        colors=7,
        brightness=0.96,
        sharpness=1.15,
        saturation=0.7,
        crt="off",
        vhs="off",
        dither="ordered",
        dither_ramp="tone",
        dither_space="pixel",
        dither_strength=0.9,
        dither_scale=4,
        dither_angle=0.0,
        palette=["#1f1714", "#2b2523", "#343839", "#41494a", "#6d584e", "#8c6c5b", "#ad856b"],
    ),
    StyleFilter(
        id="cold_sci_fi_dither",
        label="冷色科幻抖动",
        pixel_scale=2,
        colors=7,
        brightness=0.98,
        sharpness=1.18,
        saturation=0.78,
        crt="off",
        vhs="off",
        dither="ordered",
        dither_ramp="tone",
        dither_space="pixel",
        dither_strength=0.86,
        dither_scale=4,
        dither_angle=0.0,
        palette=["#101519", "#182226", "#243235", "#34484a", "#4f6868", "#78908e", "#aebbb3"],
    ),
    StyleFilter(
        id="amber_ruin_dither",
        label="琥珀废墟抖动",
        pixel_scale=2,
        colors=7,
        brightness=0.98,
        sharpness=1.15,
        saturation=0.74,
        crt="off",
        vhs="off",
        dither="ordered",
        dither_ramp="tone",
        dither_space="pixel",
        dither_strength=0.88,
        dither_scale=4,
        dither_angle=0.0,
        palette=["#1c1512", "#2b211b", "#3d3025", "#594434", "#7a5a3d", "#a1724c", "#d09a66"],
    ),
    StyleFilter(
        id="noir_blue_dither",
        label="蓝黑夜景抖动",
        pixel_scale=2,
        colors=7,
        brightness=0.94,
        sharpness=1.12,
        saturation=0.68,
        crt="off",
        vhs="off",
        dither="ordered",
        dither_ramp="tone",
        dither_space="pixel",
        dither_strength=0.9,
        dither_scale=4,
        dither_angle=0.0,
        palette=["#111419", "#171c25", "#222b37", "#2d3c4d", "#465d70", "#70889a", "#b0bdc2"],
    ),
    StyleFilter(
        id="muted_green_dither",
        label="低饱和灰绿抖动",
        pixel_scale=2,
        colors=7,
        brightness=0.97,
        sharpness=1.15,
        saturation=0.66,
        crt="off",
        vhs="off",
        dither="ordered",
        dither_ramp="tone",
        dither_space="pixel",
        dither_strength=0.86,
        dither_scale=4,
        dither_angle=0.0,
        palette=["#171a16", "#20261f", "#2c342e", "#3b4741", "#56635b", "#7a8577", "#aaad9d"],
    ),
    StyleFilter(
        id="rust_industrial_dither",
        label="铁锈工业抖动",
        pixel_scale=2,
        colors=7,
        brightness=0.97,
        sharpness=1.14,
        saturation=0.72,
        crt="off",
        vhs="off",
        dither="ordered",
        dither_ramp="tone",
        dither_space="pixel",
        dither_strength=0.88,
        dither_scale=4,
        dither_angle=0.0,
        palette=["#141719", "#222427", "#343533", "#4b463c", "#6b4a32", "#9b6132", "#c98749"],
    ),
    StyleFilter(
        id="sickly_neon_dither",
        label="病态霓虹抖动",
        pixel_scale=2,
        colors=7,
        brightness=0.95,
        sharpness=1.16,
        saturation=0.82,
        crt="off",
        vhs="off",
        dither="ordered",
        dither_ramp="tone",
        dither_space="pixel",
        dither_strength=0.9,
        dither_scale=4,
        dither_angle=0.0,
        palette=["#101316", "#18211f", "#24302b", "#354035", "#5a6b3d", "#9ea840", "#d9d96a"],
    ),
    StyleFilter(
        id="moonlit_castle_dither",
        label="月光石堡抖动",
        pixel_scale=2,
        colors=7,
        brightness=0.96,
        sharpness=1.12,
        saturation=0.64,
        crt="off",
        vhs="off",
        dither="ordered",
        dither_ramp="tone",
        dither_space="pixel",
        dither_strength=0.86,
        dither_scale=4,
        dither_angle=0.0,
        palette=["#12151d", "#1c2230", "#2a3342", "#3d4651", "#5b6570", "#87909a", "#c7c9bf"],
    ),
    StyleFilter(
        id="red_alert_dither",
        label="血色警报抖动",
        pixel_scale=2,
        colors=7,
        brightness=0.94,
        sharpness=1.15,
        saturation=0.78,
        crt="off",
        vhs="off",
        dither="ordered",
        dither_ramp="tone",
        dither_space="pixel",
        dither_strength=0.9,
        dither_scale=4,
        dither_angle=0.0,
        palette=["#130f11", "#1f191d", "#2f2529", "#443238", "#683a3e", "#a0443f", "#e0634e"],
    ),
    StyleFilter(
        id="dust_wasteland_dither",
        label="沙尘废土抖动",
        pixel_scale=2,
        colors=7,
        brightness=0.99,
        sharpness=1.12,
        saturation=0.7,
        crt="off",
        vhs="off",
        dither="ordered",
        dither_ramp="tone",
        dither_space="pixel",
        dither_strength=0.84,
        dither_scale=4,
        dither_angle=0.0,
        palette=["#171514", "#28221c", "#3a3023", "#51412e", "#716044", "#9a825d", "#cfb17a"],
    ),
    StyleFilter(
        id="deep_sea_module_dither",
        label="深海舱室抖动",
        pixel_scale=2,
        colors=7,
        brightness=0.96,
        sharpness=1.14,
        saturation=0.72,
        crt="off",
        vhs="off",
        dither="ordered",
        dither_ramp="tone",
        dither_space="pixel",
        dither_strength=0.88,
        dither_scale=4,
        dither_angle=0.0,
        palette=["#0d1417", "#132025", "#1c3034", "#28464b", "#3c6265", "#5f8886", "#98b7ac"],
    ),
    StyleFilter(
        id="old_film_dusk_dither",
        label="旧胶片黄昏抖动",
        pixel_scale=2,
        colors=7,
        brightness=0.98,
        sharpness=1.1,
        saturation=0.68,
        crt="off",
        vhs="off",
        dither="ordered",
        dither_ramp="tone",
        dither_space="pixel",
        dither_strength=0.82,
        dither_scale=4,
        dither_angle=0.0,
        palette=["#171412", "#28201c", "#3b2d27", "#554037", "#745b45", "#967955", "#d2aa6d"],
    ),
    StyleFilter(
        id="ash_violet_dream_dither",
        label="灰紫梦境抖动",
        pixel_scale=2,
        colors=7,
        brightness=0.97,
        sharpness=1.1,
        saturation=0.62,
        crt="off",
        vhs="off",
        dither="ordered",
        dither_ramp="tone",
        dither_space="pixel",
        dither_strength=0.85,
        dither_scale=4,
        dither_angle=0.0,
        palette=["#151318", "#211d26", "#302936", "#46384a", "#634d60", "#897073", "#c0a09a"],
    ),
)


def style_filter_by_id(style_id: str) -> StyleFilter:
    for style in STYLE_FILTERS:
        if style.id == style_id:
            return style
    raise ConfigError(f"Unknown style filter: {style_id}")


def generate_palette_for_style(
    image: Image.Image | None,
    style_id: str,
    palette_mode: str,
) -> GeneratedPalette:
    if palette_mode not in PALETTE_MODES:
        raise ConfigError("palette mode must be fixed, auto_unified, or auto_preserve_lights")
    style = style_filter_by_id(style_id)
    fixed_palette = [normalize_hex_color(color) for color in style.palette]
    if not fixed_palette:
        return GeneratedPalette(source_colors=[], render_colors=[], auto_match=False)
    if palette_mode == PALETTE_MODE_FIXED or image is None:
        return GeneratedPalette(source_colors=[], render_colors=fixed_palette, auto_match=False)

    source_colors = extract_palette_from_image(image, min(32, max(style.colors * 3, 8)), "tonal")
    render_colors = _adapt_palette_to_image(fixed_palette, source_colors, style.colors)
    if palette_mode == PALETTE_MODE_AUTO_PRESERVE_LIGHTS:
        accents = _extract_light_accents(image, render_colors, max(1, min(3, style.colors // 2)))
        render_colors = _merge_accents(render_colors, accents, style.colors)
    return GeneratedPalette(source_colors=source_colors, render_colors=render_colors, auto_match=False)


def _adapt_palette_to_image(base_palette: list[str], source_colors: list[str], count: int) -> list[str]:
    base = _sample_palette(_sort_by_luminance(base_palette), count)
    if not source_colors:
        return base
    source = _sample_palette(_sort_by_luminance(source_colors), count)
    mean_luminance = sum(_luminance(parse_hex_color(color)) for color in source) / len(source)
    target_luminance = sum(_luminance(parse_hex_color(color)) for color in base) / len(base)
    brightness_scale = _clamp(mean_luminance / max(1.0, target_luminance), 0.82, 1.18)
    adapted = [
        _blend_style_color_with_source(base_color, source_color, brightness_scale)
        for base_color, source_color in zip(base, source, strict=True)
    ]
    return _dedupe_palette(adapted, fallback=base, count=count)


def _blend_style_color_with_source(base_color: str, source_color: str, brightness_scale: float) -> str:
    base_h, base_s, base_v = _hsv(parse_hex_color(base_color))
    _source_h, source_s, source_v = _hsv(parse_hex_color(source_color))
    saturation = _clamp(base_s * 0.86 + source_s * 0.14, 0.04, 0.62)
    value = _clamp((base_v * 0.82 + source_v * 0.18) * brightness_scale, 0.02, 0.86)
    return rgb_to_hex(_rgb_from_hsv(base_h, saturation, value))


def _extract_light_accents(image: Image.Image, base_palette: list[str], count: int) -> list[str]:
    candidates = extract_palette_from_image(image, 32, "balanced_hue")
    accents: list[str] = []
    for color in sorted(candidates, key=_accent_score, reverse=True):
        rgb = parse_hex_color(color)
        hue, saturation, value = _hsv(rgb)
        luminance = _luminance(rgb)
        is_colored_light = saturation >= 0.34 and value >= 0.38 and luminance >= 38
        is_white_light = saturation <= 0.18 and value >= 0.72 and luminance >= 165
        if not is_colored_light and not is_white_light:
            continue
        accent = _compress_accent(hue, saturation, value, is_white_light)
        if _is_far_from_palette(accent, [*base_palette, *accents]):
            accents.append(accent)
        if len(accents) >= count:
            break
    return accents


def _compress_accent(hue: float, saturation: float, value: float, is_white_light: bool) -> str:
    if is_white_light:
        return rgb_to_hex(_rgb_from_hsv(hue, min(0.12, saturation), _clamp(value, 0.72, 0.92)))
    return rgb_to_hex(_rgb_from_hsv(hue, _clamp(saturation, 0.48, 0.86), _clamp(value, 0.45, 0.9)))


def _merge_accents(base_palette: list[str], accents: list[str], count: int) -> list[str]:
    if not accents:
        return _dedupe_palette(base_palette, fallback=base_palette, count=count)
    base = _sort_by_luminance(base_palette)
    keep_count = max(2, count - len(accents))
    merged = [*_sample_palette(base, keep_count), *accents]
    return _dedupe_palette(_sort_by_luminance(merged), fallback=base_palette, count=count)


def _sample_palette(colors: list[str], count: int) -> list[str]:
    if count <= 0 or not colors:
        return []
    if len(colors) == count:
        return list(colors)
    if count == 1:
        return [colors[0]]
    scale = (len(colors) - 1) / (count - 1)
    return [colors[round(index * scale)] for index in range(count)]


def _dedupe_palette(colors: list[str], fallback: list[str], count: int) -> list[str]:
    result: list[str] = []
    for color in [*colors, *fallback]:
        normalized = normalize_hex_color(color)
        if normalized not in result:
            result.append(normalized)
        if len(result) >= count:
            break
    return result


def _sort_by_luminance(colors: list[str]) -> list[str]:
    return sorted((normalize_hex_color(color) for color in colors), key=lambda color: _luminance(parse_hex_color(color)))


def _is_far_from_palette(color: str, palette: list[str]) -> bool:
    if not palette:
        return True
    return min(perceptual_color_distance(color, other) for other in palette) > 0.085


def _accent_score(color: str) -> float:
    rgb = parse_hex_color(color)
    _hue, saturation, value = _hsv(rgb)
    luminance = _luminance(rgb) / 255.0
    return saturation * 0.58 + value * 0.28 + luminance * 0.14


def _hsv(rgb: RGB) -> tuple[float, float, float]:
    return colorsys.rgb_to_hsv(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)


def _rgb_from_hsv(hue: float, saturation: float, value: float) -> RGB:
    red, green, blue = colorsys.hsv_to_rgb(hue, saturation, value)
    return (round(red * 255), round(green * 255), round(blue * 255))


def _luminance(rgb: RGB) -> float:
    return (0.299 * rgb[0]) + (0.587 * rgb[1]) + (0.114 * rgb[2])


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
