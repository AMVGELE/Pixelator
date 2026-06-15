from pathlib import Path

import pytest

from pixelator.config import (
    ConfigError,
    CropConfig,
    RenderConfig,
    TrimConfig,
    config_from_dict,
    load_config,
    merge_cli_overrides,
    validate_config,
)


def test_default_config_uses_stable_mode():
    config = RenderConfig()
    assert config.mode == "stable"
    assert config.pixel.scale == 4
    assert config.palette.colors == 32
    assert config.effects.crt == "off"
    assert config.effects.vhs == "off"
    assert config.output.keep_audio is True


def test_load_config_from_yaml(tmp_path: Path):
    path = tmp_path / "pixelator.yaml"
    path.write_text(
        """
mode: fast
pixel:
  scale: 6
palette:
  colors: 16
effects:
  crt: off
  vhs: light
""".strip(),
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.mode == "fast"
    assert config.pixel.scale == 6
    assert config.palette.colors == 16
    assert config.effects.crt == "off"
    assert config.effects.vhs == "light"


def test_load_config_accepts_custom_palette_colors(tmp_path: Path):
    path = tmp_path / "pixelator.yaml"
    path.write_text(
        """
palette:
  strategy: custom
  custom_colors:
    - "#000000"
    - "#ffcc00"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.palette.strategy == "custom"
    assert config.palette.custom_colors == ["#000000", "#ffcc00"]


def test_load_config_accepts_auto_match_palette_colors(tmp_path: Path):
    path = tmp_path / "pixelator.yaml"
    path.write_text(
        """
palette:
  strategy: auto_match
  match_sort: original
  source_colors:
    - "#ff0000"
    - "#0000ff"
  custom_colors:
    - "#00ff00"
    - "#ffff00"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.palette.strategy == "auto_match"
    assert config.palette.source_colors == ["#ff0000", "#0000ff"]
    assert config.palette.custom_colors == ["#00ff00", "#ffff00"]
    assert config.palette.match_sort == "original"


def test_cli_overrides_replace_nested_values():
    base = RenderConfig()

    result = merge_cli_overrides(
        base,
        {
            "mode": "fast",
            "pixel.scale": 8,
            "palette.colors": 24,
            "output.keep_audio": False,
        },
    )

    assert result.mode == "fast"
    assert result.pixel.scale == 8
    assert result.palette.colors == 24
    assert result.output.keep_audio is False


def test_invalid_mode_is_rejected():
    config = config_from_dict({"mode": "preview"})

    with pytest.raises(ConfigError, match="mode"):
        validate_config(config)


def test_invalid_palette_size_is_rejected():
    config = config_from_dict({"palette": {"colors": 1}})

    with pytest.raises(ConfigError, match="palette.colors"):
        validate_config(config)


def test_custom_palette_requires_at_least_two_colors():
    config = config_from_dict({"palette": {"strategy": "custom", "custom_colors": ["#000000"]}})

    with pytest.raises(ConfigError, match="custom_colors"):
        validate_config(config)


def test_custom_palette_rejects_invalid_hex():
    config = config_from_dict({"palette": {"strategy": "custom", "custom_colors": ["#000000", "#fff"]}})

    with pytest.raises(ConfigError, match="#RRGGBB"):
        validate_config(config)


def test_custom_palette_rejects_too_many_colors():
    config = config_from_dict(
        {
            "palette": {
                "strategy": "custom",
                "custom_colors": ["#000000", "#ffffff"] * 129,
            }
        }
    )

    with pytest.raises(ConfigError, match="custom_colors"):
        validate_config(config)


def test_source_palette_requires_auto_match_strategy():
    config = config_from_dict({"palette": {"source_colors": ["#000000", "#ffffff"]}})

    with pytest.raises(ConfigError, match="source_colors"):
        validate_config(config)


def test_auto_match_palette_requires_source_colors():
    config = config_from_dict(
        {
            "palette": {
                "strategy": "auto_match",
                "custom_colors": ["#000000", "#ffffff"],
            }
        }
    )

    with pytest.raises(ConfigError, match="source_colors"):
        validate_config(config)


def test_auto_match_rejects_invalid_match_sort():
    config = config_from_dict(
        {
            "palette": {
                "strategy": "auto_match",
                "match_sort": "temperature",
                "source_colors": ["#000000", "#ffffff"],
                "custom_colors": ["#000000", "#ffffff"],
            }
        }
    )

    with pytest.raises(ConfigError, match="match_sort"):
        validate_config(config)


def test_config_accepts_crop_and_trim_from_mapping():
    config = config_from_dict(
        {
            "crop": {"x": 10, "y": 12, "width": 100, "height": 80},
            "trim": {"start": 1.5, "end": 4.0},
        }
    )

    validate_config(config)

    assert config.crop is not None
    assert config.crop.x == 10
    assert config.crop.y == 12
    assert config.crop.width == 100
    assert config.crop.height == 80
    assert config.trim is not None
    assert config.trim.start == 1.5
    assert config.trim.end == 4.0


def test_invalid_crop_dimensions_are_rejected():
    config = config_from_dict({"crop": {"x": 0, "y": 0, "width": 0, "height": 10}})

    with pytest.raises(ConfigError, match="crop.width"):
        validate_config(config)


def test_invalid_trim_order_is_rejected():
    config = config_from_dict({"trim": {"start": 3.0, "end": 2.0}})

    with pytest.raises(ConfigError, match="trim.end"):
        validate_config(config)


def test_cli_overrides_replace_crop_and_trim():
    base = RenderConfig()

    result = merge_cli_overrides(
        base,
        {
            "crop": CropConfig(x=1, y=2, width=30, height=40),
            "trim": TrimConfig(start=0.5, end=2.5),
        },
    )

    assert result.crop == CropConfig(x=1, y=2, width=30, height=40)
    assert result.trim == TrimConfig(start=0.5, end=2.5)
