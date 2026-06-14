from pathlib import Path

import pytest

from pixelator.config import (
    ConfigError,
    RenderConfig,
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
