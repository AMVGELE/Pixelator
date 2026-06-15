from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from pixelator.errors import ConfigError

RGB = tuple[int, int, int]

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True)
class PaletteFile:
    colors: list[str]
    name: str | None = None


def normalize_hex_color(value: str) -> str:
    if not isinstance(value, str) or _HEX_COLOR.fullmatch(value) is None:
        raise ConfigError("custom palette colors must use #RRGGBB hex values")
    return value.lower()


def normalize_hex_colors(values: list[str]) -> list[str]:
    return [normalize_hex_color(value) for value in values]


def parse_hex_color(value: str) -> RGB:
    normalized = normalize_hex_color(value)
    return (
        int(normalized[1:3], 16),
        int(normalized[3:5], 16),
        int(normalized[5:7], 16),
    )


def parse_palette_colors(values: list[str]) -> list[RGB]:
    return [parse_hex_color(value) for value in values]


def load_palette_file(path: str | Path) -> PaletteFile:
    palette_path = Path(path)
    try:
        raw = yaml.safe_load(palette_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"Could not read palette file: {palette_path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Could not parse palette YAML: {palette_path}") from exc

    if isinstance(raw, list):
        return PaletteFile(colors=normalize_hex_colors(_require_color_list(raw)))
    if isinstance(raw, dict):
        colors = _require_color_list(raw.get("colors"))
        name = raw.get("name")
        if name is not None and not isinstance(name, str):
            raise ConfigError("palette file name must be a string")
        return PaletteFile(colors=normalize_hex_colors(colors), name=name)
    raise ConfigError("palette file must contain a color list or a mapping with colors")


def save_palette_file(path: str | Path, colors: list[str], name: str | None = None) -> None:
    palette_path = Path(path)
    palette_path.parent.mkdir(parents=True, exist_ok=True)
    raw: dict[str, Any] = {"colors": normalize_hex_colors(colors)}
    if name:
        raw = {"name": name, **raw}
    palette_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def _require_color_list(raw: object) -> list[str]:
    if not isinstance(raw, list) or not all(isinstance(value, str) for value in raw):
        raise ConfigError("palette colors must be a list of #RRGGBB strings")
    return list(raw)
