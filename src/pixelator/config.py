from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

from pixelator.errors import ConfigError
from pixelator.palette_io import normalize_hex_color


@dataclass(frozen=True)
class PixelConfig:
    scale: int = 4
    target_width: int | None = None


@dataclass(frozen=True)
class CropConfig:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class TrimConfig:
    start: float = 0.0
    end: float | None = None


@dataclass(frozen=True)
class PaletteConfig:
    strategy: str = "global_sampled"
    colors: int = 32
    sample_frames: int = 48
    custom_colors: list[str] | None = None
    source_colors: list[str] | None = None
    match_sort: str = "hue_brightness"


@dataclass(frozen=True)
class ImageConfig:
    brightness: float = 1.0
    sharpness: float = 1.2
    saturation: float = 1.1


@dataclass(frozen=True)
class EffectsConfig:
    crt: str = "off"
    vhs: str = "off"
    chroma_offset: int = 1
    noise_amount: float = 0.006


@dataclass(frozen=True)
class PerformanceConfig:
    workers: str | int = "auto"
    preview_seconds: float | None = None


@dataclass(frozen=True)
class OutputConfig:
    keep_audio: bool = True
    codec: str = "libx264"
    overwrite: bool = False
    audio_failure: str = "stop"


@dataclass(frozen=True)
class RenderConfig:
    mode: str = "stable"
    pixel: PixelConfig = field(default_factory=PixelConfig)
    crop: CropConfig | None = None
    trim: TrimConfig | None = None
    palette: PaletteConfig = field(default_factory=PaletteConfig)
    image: ImageConfig = field(default_factory=ImageConfig)
    effects: EffectsConfig = field(default_factory=EffectsConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    output: OutputConfig = field(default_factory=OutputConfig)


def load_config(path: str | Path) -> RenderConfig:
    config_path = Path(path)
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except OSError as exc:
        raise ConfigError(f"Could not read config file: {config_path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Could not parse YAML config: {config_path}") from exc
    config = config_from_dict(raw)
    validate_config(config)
    return config


def config_from_dict(raw: dict[str, Any]) -> RenderConfig:
    return RenderConfig(
        mode=raw.get("mode", "stable"),
        pixel=_nested(PixelConfig, raw.get("pixel", {})),
        crop=_optional_nested(CropConfig, raw.get("crop")),
        trim=_optional_nested(TrimConfig, raw.get("trim")),
        palette=_nested(PaletteConfig, raw.get("palette", {})),
        image=_nested(ImageConfig, raw.get("image", {})),
        effects=_nested(EffectsConfig, _normalize_effect_modes(raw.get("effects", {}))),
        performance=_nested(PerformanceConfig, raw.get("performance", {})),
        output=_nested(OutputConfig, raw.get("output", {})),
    )


def merge_cli_overrides(config: RenderConfig, overrides: dict[str, Any]) -> RenderConfig:
    result = config
    for key, value in overrides.items():
        if value is None:
            continue
        parts = key.split(".")
        if len(parts) == 1:
            result = replace(result, **{parts[0]: value})
            continue
        if len(parts) != 2:
            raise ConfigError(f"Unsupported override path: {key}")
        section_name, field_name = parts
        section = getattr(result, section_name)
        result = replace(result, **{section_name: replace(section, **{field_name: value})})
    validate_config(result)
    return result


def validate_config(config: RenderConfig) -> None:
    if config.mode not in {"fast", "stable"}:
        raise ConfigError("mode must be 'fast' or 'stable'")
    if config.pixel.scale < 1:
        raise ConfigError("pixel.scale must be at least 1")
    if config.pixel.target_width is not None and config.pixel.target_width < 16:
        raise ConfigError("pixel.target_width must be at least 16 when set")
    if config.crop is not None:
        if config.crop.x < 0:
            raise ConfigError("crop.x must be at least 0")
        if config.crop.y < 0:
            raise ConfigError("crop.y must be at least 0")
        if config.crop.width < 1:
            raise ConfigError("crop.width must be at least 1")
        if config.crop.height < 1:
            raise ConfigError("crop.height must be at least 1")
    if config.trim is not None:
        if config.trim.start < 0:
            raise ConfigError("trim.start must be at least 0")
        if config.trim.end is not None and config.trim.end <= config.trim.start:
            raise ConfigError("trim.end must be greater than trim.start")
    if not 2 <= config.palette.colors <= 256:
        raise ConfigError("palette.colors must be between 2 and 256")
    if config.palette.sample_frames < 1:
        raise ConfigError("palette.sample_frames must be at least 1")
    if config.palette.match_sort not in {"original", "brightness", "hue", "hue_brightness", "saturation"}:
        raise ConfigError("palette.match_sort must be original, brightness, hue, hue_brightness, or saturation")
    if config.palette.strategy not in {"per_frame", "global_sampled", "custom", "auto_match", "original"}:
        raise ConfigError(
            "palette.strategy must be 'per_frame', 'global_sampled', 'custom', 'auto_match', or 'original'"
        )
    if config.palette.strategy in {"custom", "auto_match"}:
        if config.palette.custom_colors is None:
            raise ConfigError("palette.custom_colors must contain 2 to 256 colors")
        if not 2 <= len(config.palette.custom_colors) <= 256:
            raise ConfigError("palette.custom_colors must contain 2 to 256 colors")
        for color in config.palette.custom_colors:
            try:
                normalize_hex_color(color)
            except ConfigError as exc:
                raise ConfigError("palette.custom_colors must use #RRGGBB hex values") from exc
    if config.palette.strategy == "auto_match":
        if config.palette.source_colors is None:
            raise ConfigError("palette.source_colors must contain 2 to 256 colors")
        if not 2 <= len(config.palette.source_colors) <= 256:
            raise ConfigError("palette.source_colors must contain 2 to 256 colors")
        for color in config.palette.source_colors:
            try:
                normalize_hex_color(color)
            except ConfigError as exc:
                raise ConfigError("palette.source_colors must use #RRGGBB hex values") from exc
    elif config.palette.source_colors is not None:
        raise ConfigError("palette.source_colors requires palette.strategy 'auto_match'")
    if config.palette.strategy not in {"custom", "auto_match"} and config.palette.custom_colors is not None:
        raise ConfigError("palette.custom_colors requires palette.strategy 'custom' or 'auto_match'")
    if config.effects.crt not in {"off", "subtle"}:
        raise ConfigError("effects.crt must be 'off' or 'subtle'")
    if config.effects.vhs not in {"off", "light"}:
        raise ConfigError("effects.vhs must be 'off' or 'light'")
    if config.output.audio_failure not in {"stop", "continue"}:
        raise ConfigError("output.audio_failure must be 'stop' or 'continue'")


def _nested(cls: type[Any], raw: dict[str, Any]) -> Any:
    if not isinstance(raw, dict):
        raise ConfigError(f"{cls.__name__} expects a mapping")
    try:
        return cls(**raw)
    except TypeError as exc:
        raise ConfigError(f"{cls.__name__} contains an unsupported field") from exc


def _optional_nested(cls: type[Any], raw: dict[str, Any] | None) -> Any:
    if raw is None:
        return None
    return _nested(cls, raw)


def _normalize_effect_modes(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ConfigError("EffectsConfig expects a mapping")
    normalized = dict(raw)
    for key in ("crt", "vhs"):
        value = normalized.get(key)
        if value is False:
            normalized[key] = "off"
    return normalized
