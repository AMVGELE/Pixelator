# Pixelator v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Pixelator v0.1 as a Python library plus CLI that converts videos into light pixel-art style outputs with `fast` and `stable` modes.

**Architecture:** Use a thin CLI over focused library modules. Keep video IO, config, image operations, palette strategies, effects, and orchestration in separate files with deterministic interfaces and focused tests.

**Tech Stack:** Python 3.11+, Pillow, NumPy, PyYAML, imageio-ffmpeg, pytest, standard-library argparse and subprocess.

---

## Scope Check

The v0.1 spec covers one subsystem: a CLI-driven video pixelation pipeline. GUI, Aseprite round-tripping, scene segmentation, and batch queues remain outside this plan.

## File Structure

Create these files:

- `pyproject.toml`: package metadata, dependencies, test configuration, console script.
- `.gitignore`: Python, virtualenv, cache, and render-output ignores.
- `README.md`: install and first-run usage.
- `presets/fast.yaml`: default fast-mode preset.
- `presets/stable.yaml`: default stable-mode preset.
- `src/pixelator/__init__.py`: package version.
- `src/pixelator/__main__.py`: `python -m pixelator` entry point.
- `src/pixelator/cli.py`: argument parsing and command dispatch.
- `src/pixelator/config.py`: dataclass config model, YAML loading, CLI override merging, validation.
- `src/pixelator/errors.py`: typed user-facing exceptions.
- `src/pixelator/image_ops.py`: deterministic per-frame image operations.
- `src/pixelator/palette.py`: fast and stable palette functions.
- `src/pixelator/effects.py`: optional CRT/VHS-style effects.
- `src/pixelator/video.py`: video probing, frame iteration, writing, audio muxing.
- `src/pixelator/pipeline.py`: render orchestration.
- `tests/test_package.py`: packaging smoke test.
- `tests/test_config.py`: config behavior.
- `tests/test_image_ops.py`: frame operation behavior.
- `tests/test_palette.py`: palette behavior.
- `tests/test_effects.py`: effect behavior.
- `tests/test_video.py`: video helper behavior with monkeypatching.
- `tests/test_pipeline.py`: pipeline orchestration with fake frame IO.
- `tests/test_cli.py`: CLI parsing and dispatch.

Modify these files:

- `docs/PROGRESS.md`: update after each milestone and validation run.

## Task 1: Project Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `README.md`
- Create: `src/pixelator/__init__.py`
- Create: `src/pixelator/__main__.py`
- Create: `tests/test_package.py`
- Modify: `docs/PROGRESS.md`

- [x] **Step 1: Write the packaging smoke test**

Create `tests/test_package.py`:

```python
from pixelator import __version__


def test_package_exposes_version():
    assert __version__ == "0.1.0"
```

- [x] **Step 2: Run the smoke test and verify it fails**

Run:

```bash
python -m pytest tests/test_package.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pixelator'`.

- [x] **Step 3: Add packaging files**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "pixelator"
version = "0.1.0"
description = "CLI video-to-light-pixel-art workflow tool."
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "imageio-ffmpeg>=0.4.9",
  "numpy>=1.26",
  "Pillow>=10.0",
  "PyYAML>=6.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
]

[project.scripts]
pixelator = "pixelator.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

Create `.gitignore`:

```gitignore
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.mypy_cache/
.venv/
venv/
dist/
build/
*.egg-info/
outputs/
tmp/
*.mp4.tmp
*.mov.tmp
```

Create `README.md`:

````markdown
# Pixelator

Pixelator converts source videos into a light pixel-art video style.

## Install

```bash
python -m pip install -e ".[dev]"
```

## First Commands

```bash
pixelator input.mp4 --mode fast --out output-fast.mp4
pixelator input.mp4 --mode stable --out output-stable.mp4
pixelator input.mp4 --config presets/stable.yaml --out output-stable.mp4
```

`fast` mode is for quick parameter previews. `stable` mode is for final renders with
reduced temporal color flicker.
````

Create `src/pixelator/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `src/pixelator/__main__.py`:

```python
from pixelator.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 4: Add a temporary CLI module so package imports are complete**

Create `src/pixelator/cli.py`:

```python
def main(argv: list[str] | None = None) -> int:
    return 0
```

- [x] **Step 5: Run the smoke test and verify it passes**

Run:

```bash
python -m pytest tests/test_package.py -v
```

Expected: PASS.

- [x] **Step 6: Update progress**

Modify `docs/PROGRESS.md`:

```markdown
- Phase: Implementation
- Active milestone: Milestone 0 - Repository Setup
```

Mark these items complete:

```markdown
- [x] Review design with user.
- [x] Create implementation plan after design approval.
- [x] Add project skeleton.
```

- [x] **Step 7: Commit**

Run:

```bash
git add pyproject.toml .gitignore README.md src tests docs/PROGRESS.md
git commit -m "chore: add project skeleton"
```

## Task 2: Config Model And Presets

**Files:**
- Create: `src/pixelator/config.py`
- Create: `src/pixelator/errors.py`
- Create: `presets/fast.yaml`
- Create: `presets/stable.yaml`
- Create: `tests/test_config.py`
- Modify: `docs/PROGRESS.md`

- [x] **Step 1: Write config tests**

Create `tests/test_config.py`:

```python
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
```

- [x] **Step 2: Run config tests and verify they fail**

Run:

```bash
python -m pytest tests/test_config.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pixelator.config'`.

- [x] **Step 3: Add typed errors**

Create `src/pixelator/errors.py`:

```python
class PixelatorError(Exception):
    """Base class for user-facing Pixelator errors."""


class ConfigError(PixelatorError):
    """Raised when configuration cannot be loaded or validated."""


class VideoError(PixelatorError):
    """Raised when video probing, decoding, encoding, or muxing fails."""


class OutputError(PixelatorError):
    """Raised when output paths are invalid or unsafe."""
```

- [x] **Step 4: Implement config model**

Create `src/pixelator/config.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

from pixelator.errors import ConfigError


@dataclass(frozen=True)
class PixelConfig:
    scale: int = 4
    target_width: int | None = None


@dataclass(frozen=True)
class PaletteConfig:
    strategy: str = "global_sampled"
    colors: int = 32
    sample_frames: int = 48


@dataclass(frozen=True)
class ImageConfig:
    brightness: float = 1.0
    sharpness: float = 1.2
    saturation: float = 1.1


@dataclass(frozen=True)
class EffectsConfig:
    crt: str = "subtle"
    vhs: str = "light"
    chroma_offset: int = 1
    noise_amount: float = 0.018


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
    pixel: PixelConfig = PixelConfig()
    palette: PaletteConfig = PaletteConfig()
    image: ImageConfig = ImageConfig()
    effects: EffectsConfig = EffectsConfig()
    performance: PerformanceConfig = PerformanceConfig()
    output: OutputConfig = OutputConfig()


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
        mode=raw.get("mode", RenderConfig.mode),
        pixel=_nested(PixelConfig, raw.get("pixel", {})),
        palette=_nested(PaletteConfig, raw.get("palette", {})),
        image=_nested(ImageConfig, raw.get("image", {})),
        effects=_nested(EffectsConfig, raw.get("effects", {})),
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
    if not 2 <= config.palette.colors <= 256:
        raise ConfigError("palette.colors must be between 2 and 256")
    if config.palette.sample_frames < 1:
        raise ConfigError("palette.sample_frames must be at least 1")
    if config.effects.crt not in {"off", "subtle"}:
        raise ConfigError("effects.crt must be 'off' or 'subtle'")
    if config.effects.vhs not in {"off", "light"}:
        raise ConfigError("effects.vhs must be 'off' or 'light'")
    if config.output.audio_failure not in {"stop", "continue"}:
        raise ConfigError("output.audio_failure must be 'stop' or 'continue'")


def _nested(cls: type[Any], raw: dict[str, Any]) -> Any:
    if not isinstance(raw, dict):
        raise ConfigError(f"{cls.__name__} expects a mapping")
    return cls(**raw)
```

- [x] **Step 5: Add presets**

Create `presets/fast.yaml`:

```yaml
mode: fast
pixel:
  scale: 4
palette:
  strategy: per_frame
  colors: 32
  sample_frames: 12
image:
  brightness: 1.0
  sharpness: 1.1
  saturation: 1.08
effects:
  crt: subtle
  vhs: light
  chroma_offset: 1
  noise_amount: 0.012
performance:
  workers: auto
  preview_seconds: 8
output:
  keep_audio: true
  codec: libx264
  overwrite: false
  audio_failure: stop
```

Create `presets/stable.yaml`:

```yaml
mode: stable
pixel:
  scale: 4
palette:
  strategy: global_sampled
  colors: 32
  sample_frames: 48
image:
  brightness: 1.0
  sharpness: 1.2
  saturation: 1.1
effects:
  crt: subtle
  vhs: light
  chroma_offset: 1
  noise_amount: 0.018
performance:
  workers: auto
  preview_seconds: null
output:
  keep_audio: true
  codec: libx264
  overwrite: false
  audio_failure: stop
```

- [x] **Step 6: Run config tests and verify they pass**

Run:

```bash
python -m pytest tests/test_config.py -v
```

Expected: PASS.

- [x] **Step 7: Commit**

Run:

```bash
git add src/pixelator/config.py src/pixelator/errors.py presets tests/test_config.py docs/PROGRESS.md
git commit -m "feat: add render configuration"
```

## Task 3: Image Operations

**Files:**
- Create: `src/pixelator/image_ops.py`
- Create: `tests/test_image_ops.py`
- Modify: `docs/PROGRESS.md`

- [x] **Step 1: Write image operation tests**

Create `tests/test_image_ops.py`:

```python
from PIL import Image

from pixelator.config import ImageConfig, PixelConfig
from pixelator.image_ops import adjust_frame, pixelate_frame, resolve_pixel_size


def test_resolve_pixel_size_uses_scale():
    assert resolve_pixel_size((320, 180), PixelConfig(scale=4)) == (80, 45)


def test_resolve_pixel_size_uses_target_width():
    assert resolve_pixel_size((320, 180), PixelConfig(scale=4, target_width=160)) == (160, 90)


def test_pixelate_frame_preserves_original_dimensions():
    image = Image.new("RGB", (32, 16), (120, 80, 40))

    result = pixelate_frame(image, PixelConfig(scale=4))

    assert result.size == (32, 16)
    assert result.mode == "RGB"


def test_adjust_frame_changes_saturation_without_changing_size():
    image = Image.new("RGB", (8, 8), (120, 80, 40))

    result = adjust_frame(image, ImageConfig(brightness=1.0, sharpness=1.0, saturation=1.5))

    assert result.size == image.size
    assert result.mode == "RGB"
```

- [x] **Step 2: Run image tests and verify they fail**

Run:

```bash
python -m pytest tests/test_image_ops.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pixelator.image_ops'`.

- [x] **Step 3: Implement image operations**

Create `src/pixelator/image_ops.py`:

```python
from __future__ import annotations

from PIL import Image, ImageEnhance

from pixelator.config import ImageConfig, PixelConfig


def resolve_pixel_size(size: tuple[int, int], config: PixelConfig) -> tuple[int, int]:
    width, height = size
    if config.target_width is not None:
        ratio = config.target_width / width
        return max(1, config.target_width), max(1, round(height * ratio))
    return max(1, width // config.scale), max(1, height // config.scale)


def pixelate_frame(image: Image.Image, config: PixelConfig) -> Image.Image:
    source = image.convert("RGB")
    low_size = resolve_pixel_size(source.size, config)
    low = source.resize(low_size, Image.Resampling.BOX)
    return low.resize(source.size, Image.Resampling.NEAREST)


def adjust_frame(image: Image.Image, config: ImageConfig) -> Image.Image:
    result = image.convert("RGB")
    result = ImageEnhance.Brightness(result).enhance(config.brightness)
    result = ImageEnhance.Sharpness(result).enhance(config.sharpness)
    result = ImageEnhance.Color(result).enhance(config.saturation)
    return result
```

- [x] **Step 4: Run image tests and verify they pass**

Run:

```bash
python -m pytest tests/test_image_ops.py -v
```

Expected: PASS.

- [x] **Step 5: Commit**

Run:

```bash
git add src/pixelator/image_ops.py tests/test_image_ops.py docs/PROGRESS.md
git commit -m "feat: add image operations"
```

## Task 4: Palette Strategies

**Files:**
- Create: `src/pixelator/palette.py`
- Create: `tests/test_palette.py`
- Modify: `docs/PROGRESS.md`

- [x] **Step 1: Write palette tests**

Create `tests/test_palette.py`:

```python
from PIL import Image

from pixelator.config import PaletteConfig
from pixelator.palette import apply_palette, build_global_palette, quantize_per_frame, unique_rgb_count


def test_quantize_per_frame_limits_unique_colors():
    image = Image.linear_gradient("L").resize((32, 32)).convert("RGB")

    result = quantize_per_frame(image, PaletteConfig(colors=8))

    assert unique_rgb_count(result) <= 8


def test_build_global_palette_returns_requested_color_count_or_less():
    frames = [
        Image.new("RGB", (8, 8), (255, 0, 0)),
        Image.new("RGB", (8, 8), (0, 255, 0)),
        Image.new("RGB", (8, 8), (0, 0, 255)),
    ]

    palette = build_global_palette(frames, PaletteConfig(colors=4))

    assert 1 <= len(palette) <= 4


def test_apply_palette_uses_palette_colors():
    image = Image.linear_gradient("L").resize((16, 16)).convert("RGB")
    palette = [(0, 0, 0), (255, 255, 255)]

    result = apply_palette(image, palette)

    assert unique_rgb_count(result) <= 2
```

- [x] **Step 2: Run palette tests and verify they fail**

Run:

```bash
python -m pytest tests/test_palette.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pixelator.palette'`.

- [x] **Step 3: Implement palette functions**

Create `src/pixelator/palette.py`:

```python
from __future__ import annotations

from collections.abc import Iterable

from PIL import Image

from pixelator.config import PaletteConfig

RGB = tuple[int, int, int]


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


def apply_palette(image: Image.Image, palette: list[RGB]) -> Image.Image:
    palette_image = Image.new("P", (1, 1))
    flat: list[int] = []
    for color in palette[:256]:
        flat.extend(color)
    flat.extend([0] * (768 - len(flat)))
    palette_image.putpalette(flat)
    return image.convert("RGB").quantize(palette=palette_image, dither=Image.Dither.NONE).convert("RGB")


def unique_rgb_count(image: Image.Image) -> int:
    return len(set(image.convert("RGB").getdata()))
```

- [x] **Step 4: Run palette tests and verify they pass**

Run:

```bash
python -m pytest tests/test_palette.py -v
```

Expected: PASS.

- [x] **Step 5: Commit**

Run:

```bash
git add src/pixelator/palette.py tests/test_palette.py docs/PROGRESS.md
git commit -m "feat: add palette strategies"
```

## Task 5: CRT And VHS Effects

**Files:**
- Create: `src/pixelator/effects.py`
- Create: `tests/test_effects.py`
- Modify: `docs/PROGRESS.md`

- [x] **Step 1: Write effect tests**

Create `tests/test_effects.py`:

```python
from PIL import Image

from pixelator.config import EffectsConfig
from pixelator.effects import apply_effects


def test_effects_off_returns_equivalent_image():
    image = Image.new("RGB", (8, 8), (100, 120, 140))

    result = apply_effects(image, EffectsConfig(crt="off", vhs="off"))

    assert list(result.getdata()) == list(image.getdata())


def test_subtle_crt_darkens_every_other_row():
    image = Image.new("RGB", (4, 4), (100, 100, 100))

    result = apply_effects(image, EffectsConfig(crt="subtle", vhs="off"))

    assert result.getpixel((0, 1))[0] < result.getpixel((0, 0))[0]


def test_light_vhs_is_deterministic_for_frame_index():
    image = Image.new("RGB", (8, 8), (100, 120, 140))
    config = EffectsConfig(crt="off", vhs="light", noise_amount=0.02)

    first = apply_effects(image, config, frame_index=7)
    second = apply_effects(image, config, frame_index=7)

    assert list(first.getdata()) == list(second.getdata())
```

- [x] **Step 2: Run effect tests and verify they fail**

Run:

```bash
python -m pytest tests/test_effects.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pixelator.effects'`.

- [x] **Step 3: Implement effects**

Create `src/pixelator/effects.py`:

```python
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
    return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), "RGB")


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
    return Image.fromarray(np.clip(array + noise, 0, 255).astype(np.uint8), "RGB")
```

- [x] **Step 4: Run effect tests and verify they pass**

Run:

```bash
python -m pytest tests/test_effects.py -v
```

Expected: PASS.

- [x] **Step 5: Commit**

Run:

```bash
git add src/pixelator/effects.py tests/test_effects.py docs/PROGRESS.md
git commit -m "feat: add video style effects"
```

## Task 6: Video IO Helpers

**Files:**
- Create: `src/pixelator/video.py`
- Create: `tests/test_video.py`
- Modify: `docs/PROGRESS.md`

- [x] **Step 1: Write video helper tests**

Create `tests/test_video.py`:

```python
from pathlib import Path

import pytest
from PIL import Image

from pixelator.errors import OutputError
from pixelator.video import VideoMetadata, ensure_output_path, sample_frames


def test_ensure_output_path_rejects_existing_file_without_overwrite(tmp_path: Path):
    output = tmp_path / "out.mp4"
    output.write_bytes(b"existing")

    with pytest.raises(OutputError, match="already exists"):
        ensure_output_path(output, overwrite=False)


def test_ensure_output_path_allows_existing_file_with_overwrite(tmp_path: Path):
    output = tmp_path / "out.mp4"
    output.write_bytes(b"existing")

    assert ensure_output_path(output, overwrite=True) == output


def test_sample_frames_evenly_samples_sequence():
    frames = [Image.new("RGB", (2, 2), (index, index, index)) for index in range(10)]

    result = sample_frames(frames, sample_count=4)

    assert len(result) == 4
    assert result[0].getpixel((0, 0)) == (0, 0, 0)
    assert result[-1].getpixel((0, 0)) == (9, 9, 9)


def test_video_metadata_frame_size():
    metadata = VideoMetadata(width=320, height=180, fps=24.0, duration=None)

    assert metadata.size == (320, 180)
```

- [x] **Step 2: Run video tests and verify they fail**

Run:

```bash
python -m pytest tests/test_video.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pixelator.video'`.

- [x] **Step 3: Implement video helpers**

Create `src/pixelator/video.py`:

```python
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import imageio_ffmpeg
import numpy as np
from PIL import Image

from pixelator.errors import OutputError, VideoError


@dataclass(frozen=True)
class VideoMetadata:
    width: int
    height: int
    fps: float
    duration: float | None = None

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height


def ensure_output_path(path: str | Path, overwrite: bool) -> Path:
    output = Path(path)
    if output.exists() and not overwrite:
        raise OutputError(f"Output file already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    return output


def probe_video(path: str | Path) -> VideoMetadata:
    reader = imageio_ffmpeg.read_frames(str(path), pix_fmt="rgb24")
    try:
        metadata = next(reader)
    except Exception as exc:
        raise VideoError(f"Could not probe video: {path}") from exc
    finally:
        reader.close()
    size = metadata.get("size")
    fps = metadata.get("fps")
    duration = metadata.get("duration")
    if not size or not fps:
        raise VideoError(f"Video metadata is incomplete: {path}")
    return VideoMetadata(width=int(size[0]), height=int(size[1]), fps=float(fps), duration=duration)


def iter_frames(path: str | Path) -> Iterator[Image.Image]:
    reader = imageio_ffmpeg.read_frames(str(path), pix_fmt="rgb24")
    try:
        metadata = next(reader)
        width, height = metadata["size"]
        for frame_bytes in reader:
            yield Image.frombytes("RGB", (width, height), frame_bytes)
    except Exception as exc:
        raise VideoError(f"Could not decode frames: {path}") from exc
    finally:
        reader.close()


def write_video(frames: Iterable[Image.Image], output: str | Path, metadata: VideoMetadata, codec: str) -> None:
    writer = imageio_ffmpeg.write_frames(
        str(output),
        size=metadata.size,
        fps=metadata.fps,
        codec=codec,
        pix_fmt_in="rgb24",
        pix_fmt_out="yuv420p",
    )
    try:
        writer.send(None)
        for frame in frames:
            array = np.asarray(frame.convert("RGB"), dtype=np.uint8)
            writer.send(array.tobytes())
    except Exception as exc:
        raise VideoError(f"Could not encode video: {output}") from exc
    finally:
        writer.close()


def mux_audio(source_video: str | Path, silent_video: str | Path, output: str | Path) -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(silent_video),
        "-i",
        str(source_video),
        "-map",
        "0:v:0",
        "-map",
        "1:a?",
        "-c:v",
        "copy",
        "-c:a",
        "copy",
        "-shortest",
        str(output),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise VideoError(f"Could not mux audio into output: {completed.stderr.strip()}")


def sample_frames(frames: list[Image.Image], sample_count: int) -> list[Image.Image]:
    if not frames:
        return []
    if sample_count >= len(frames):
        return list(frames)
    indices = np.linspace(0, len(frames) - 1, sample_count).round().astype(int)
    return [frames[index] for index in indices]
```

- [x] **Step 4: Run video tests and verify they pass**

Run:

```bash
python -m pytest tests/test_video.py -v
```

Expected: PASS.

- [x] **Step 5: Commit**

Run:

```bash
git add src/pixelator/video.py tests/test_video.py docs/PROGRESS.md
git commit -m "feat: add video io helpers"
```

## Task 7: Render Pipeline

**Files:**
- Create: `src/pixelator/pipeline.py`
- Create: `tests/test_pipeline.py`
- Modify: `docs/PROGRESS.md`

- [x] **Step 1: Write pipeline tests**

Create `tests/test_pipeline.py`:

```python
from pathlib import Path

from PIL import Image

from pixelator.config import RenderConfig
from pixelator.pipeline import process_frames
from pixelator.video import VideoMetadata


def test_process_frames_fast_limits_colors_and_preserves_size():
    frames = [Image.linear_gradient("L").resize((16, 16)).convert("RGB") for _ in range(2)]
    config = RenderConfig(mode="fast")
    metadata = VideoMetadata(width=16, height=16, fps=24.0)

    result = list(process_frames(frames, config, metadata))

    assert len(result) == 2
    assert result[0].size == (16, 16)


def test_process_frames_stable_uses_shared_palette():
    frames = [
        Image.new("RGB", (8, 8), (255, 0, 0)),
        Image.new("RGB", (8, 8), (250, 0, 0)),
    ]
    config = RenderConfig(mode="stable")
    metadata = VideoMetadata(width=8, height=8, fps=24.0)

    result = list(process_frames(frames, config, metadata))

    assert len(result) == 2
    assert result[0].size == (8, 8)
    assert result[1].size == (8, 8)
```

- [x] **Step 2: Run pipeline tests and verify they fail**

Run:

```bash
python -m pytest tests/test_pipeline.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pixelator.pipeline'`.

- [x] **Step 3: Implement pipeline**

Create `src/pixelator/pipeline.py`:

```python
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable, Iterator

from PIL import Image

from pixelator.config import RenderConfig
from pixelator.effects import apply_effects
from pixelator.errors import VideoError
from pixelator.image_ops import adjust_frame, pixelate_frame
from pixelator.palette import apply_palette, build_global_palette, quantize_per_frame
from pixelator.video import (
    VideoMetadata,
    ensure_output_path,
    iter_frames,
    mux_audio,
    probe_video,
    sample_frames,
    write_video,
)


def process_frames(
    frames: Iterable[Image.Image],
    config: RenderConfig,
    metadata: VideoMetadata,
) -> Iterator[Image.Image]:
    frame_list = list(frames)
    palette = None
    if config.mode == "stable":
        samples = sample_frames(frame_list, config.palette.sample_frames)
        adjusted_samples = [adjust_frame(pixelate_frame(frame, config.pixel), config.image) for frame in samples]
        palette = build_global_palette(adjusted_samples, config.palette)

    for index, frame in enumerate(frame_list):
        result = pixelate_frame(frame, config.pixel)
        result = adjust_frame(result, config.image)
        if config.mode == "stable" and palette is not None:
            result = apply_palette(result, palette)
        else:
            result = quantize_per_frame(result, config.palette)
        result = apply_effects(result, config.effects, frame_index=index)
        if result.size != metadata.size:
            result = result.resize(metadata.size, Image.Resampling.NEAREST)
        yield result


def render_video(input_path: str | Path, output_path: str | Path, config: RenderConfig) -> Path:
    input_file = Path(input_path)
    if not input_file.exists():
        raise VideoError(f"Input video does not exist: {input_file}")

    final_output = ensure_output_path(output_path, overwrite=config.output.overwrite)
    metadata = probe_video(input_file)
    frames = list(iter_frames(input_file))

    with TemporaryDirectory(prefix="pixelator-") as temp_dir:
        silent_output = Path(temp_dir) / f"{final_output.stem}.silent.mp4"
        processed = process_frames(frames, config, metadata)
        write_video(processed, silent_output, metadata, codec=config.output.codec)
        if config.output.keep_audio:
            try:
                mux_audio(input_file, silent_output, final_output)
            except VideoError:
                if config.output.audio_failure == "stop":
                    raise
                final_output.write_bytes(silent_output.read_bytes())
        else:
            final_output.write_bytes(silent_output.read_bytes())

    return final_output
```

- [x] **Step 4: Run pipeline tests and verify they pass**

Run:

```bash
python -m pytest tests/test_pipeline.py -v
```

Expected: PASS.

- [x] **Step 5: Run all unit tests so far**

Run:

```bash
python -m pytest -v
```

Expected: PASS.

- [x] **Step 6: Update progress**

Modify `docs/PROGRESS.md` and mark these items complete:

```markdown
- [x] Probe input video metadata.
- [x] Decode frames.
- [x] Apply basic pixelation.
- [x] Encode output video.
- [x] Preserve source audio.
- [x] Add `fast` strategy.
- [x] Add `stable` strategy.
- [x] Add global sampled palette support.
```

- [x] **Step 7: Commit**

Run:

```bash
git add src/pixelator/pipeline.py tests/test_pipeline.py docs/PROGRESS.md
git commit -m "feat: add render pipeline"
```

## Task 8: CLI

**Files:**
- Modify: `src/pixelator/cli.py`
- Create: `tests/test_cli.py`
- Modify: `docs/PROGRESS.md`

- [x] **Step 1: Write CLI tests**

Create `tests/test_cli.py`:

```python
from pathlib import Path

from pixelator import cli


def test_cli_requires_input(capsys):
    exit_code = cli.main([])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "usage:" in captured.err


def test_cli_dispatches_render(monkeypatch, tmp_path: Path):
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "output.mp4"
    input_path.write_bytes(b"fake")
    calls = {}

    def fake_render_video(input_file, output_file, config):
        calls["input"] = input_file
        calls["output"] = output_file
        calls["mode"] = config.mode
        output_path.write_bytes(b"rendered")
        return output_path

    monkeypatch.setattr(cli, "render_video", fake_render_video)

    exit_code = cli.main([str(input_path), "--mode", "fast", "--out", str(output_path), "--overwrite"])

    assert exit_code == 0
    assert calls["input"] == input_path
    assert calls["output"] == output_path
    assert calls["mode"] == "fast"
```

- [x] **Step 2: Run CLI tests and verify the dispatch test fails**

Run:

```bash
python -m pytest tests/test_cli.py -v
```

Expected: FAIL because the temporary CLI does not parse arguments or dispatch rendering.

- [x] **Step 3: Implement CLI**

Replace `src/pixelator/cli.py` with:

```python
from __future__ import annotations

import argparse
from pathlib import Path

from pixelator.config import ConfigError, RenderConfig, load_config, merge_cli_overrides
from pixelator.errors import PixelatorError
from pixelator.pipeline import render_video


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pixelator",
        description="Convert videos into a light pixel-art style.",
    )
    parser.add_argument("input", type=Path, help="Input video path.")
    parser.add_argument("--out", type=Path, required=True, help="Output video path.")
    parser.add_argument("--config", type=Path, help="YAML config path.")
    parser.add_argument("--mode", choices=["fast", "stable"], help="Render mode.")
    parser.add_argument("--pixel-scale", type=int, help="Pixel scale factor.")
    parser.add_argument("--colors", type=int, help="Palette color count.")
    parser.add_argument("--no-audio", action="store_true", help="Do not preserve source audio.")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing an existing output file.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        config = load_config(args.config) if args.config else RenderConfig()
        overrides = {
            "mode": args.mode,
            "pixel.scale": args.pixel_scale,
            "palette.colors": args.colors,
            "output.keep_audio": False if args.no_audio else None,
            "output.overwrite": True if args.overwrite else None,
        }
        config = merge_cli_overrides(config, overrides)
        output = render_video(args.input, args.out, config)
    except SystemExit as exc:
        return int(exc.code)
    except (PixelatorError, ConfigError) as exc:
        parser.exit(1, f"pixelator: error: {exc}\n")

    print(f"Wrote {output}")
    return 0
```

- [x] **Step 4: Run CLI tests and verify they pass**

Run:

```bash
python -m pytest tests/test_cli.py -v
```

Expected: PASS.

- [x] **Step 5: Run CLI help manually**

Run:

```bash
python -m pixelator --help
```

Expected: exit code 0 and output containing `Convert videos into a light pixel-art style.`

- [x] **Step 6: Update progress**

Modify `docs/PROGRESS.md` and mark these items complete:

```markdown
- [x] Add CLI entry point.
- [x] Add preset configs.
- [x] Add CRT scanline effect.
- [x] Add light VHS noise effect.
- [x] Add chroma offset or color bleed effect.
- [x] Make effects optional and subtle by default.
```

- [x] **Step 7: Commit**

Run:

```bash
git add src/pixelator/cli.py tests/test_cli.py docs/PROGRESS.md
git commit -m "feat: add pixelator cli"
```

## Task 9: Verification, Docs, And Progress Closure

**Files:**
- Modify: `README.md`
- Modify: `docs/PROGRESS.md`

- [x] **Step 1: Run full test suite**

Run:

```bash
python -m pytest -v
```

Expected: PASS.

- [x] **Step 2: Install editable package**

Run:

```bash
python -m pip install -e ".[dev]"
```

Expected: installation completes successfully and `pixelator` command is available.

- [x] **Step 3: Create a tiny synthetic sample video**

Run:

```bash
python - <<'PY'
from pathlib import Path
from PIL import Image, ImageDraw
from pixelator.video import VideoMetadata, write_video

Path("outputs").mkdir(exist_ok=True)
frames = []
for index in range(24):
    image = Image.new("RGB", (96, 64), (20 + index * 4, 30, 80))
    draw = ImageDraw.Draw(image)
    draw.rectangle((index * 2, 16, index * 2 + 24, 40), fill=(220, 80, 40))
    frames.append(image)

write_video(frames, "outputs/sample.mp4", VideoMetadata(width=96, height=64, fps=12.0), "libx264")
PY
```

Expected: `outputs/sample.mp4` exists.

- [x] **Step 4: Verify fast render**

Run:

```bash
pixelator outputs/sample.mp4 --mode fast --out outputs/sample-fast.mp4 --overwrite --no-audio
```

Expected: exit code 0 and `outputs/sample-fast.mp4` exists.

- [x] **Step 5: Verify stable render**

Run:

```bash
pixelator outputs/sample.mp4 --mode stable --out outputs/sample-stable.mp4 --overwrite --no-audio
```

Expected: exit code 0 and `outputs/sample-stable.mp4` exists.

- [x] **Step 6: Update README usage**

Update `README.md` to include:

````markdown
## Verification

After installation, run:

```bash
python -m pytest -v
pixelator outputs/sample.mp4 --mode fast --out outputs/sample-fast.mp4 --overwrite --no-audio
pixelator outputs/sample.mp4 --mode stable --out outputs/sample-stable.mp4 --overwrite --no-audio
```

Use `fast` while tuning parameters, then render `stable` for final output.
````

- [x] **Step 7: Update progress**

Modify `docs/PROGRESS.md`:

```markdown
- Phase: v0.1 implemented
- Active milestone: Milestone 4 - Reliability Pass
```

Mark these items complete:

```markdown
- [x] Add unit tests.
- [x] Add sample verification commands.
- [x] Improve user-facing errors.
- [x] Update usage docs.
```

Append validation results:

```markdown
## Validation Log

- `python -m pytest -v` passed.
- `pixelator outputs/sample.mp4 --mode fast --out outputs/sample-fast.mp4 --overwrite --no-audio` passed.
- `pixelator outputs/sample.mp4 --mode stable --out outputs/sample-stable.mp4 --overwrite --no-audio` passed.
```

Set blockers:

```markdown
## Blockers

- None for v0.1 implementation.
```

- [x] **Step 8: Commit**

Run:

```bash
git add README.md docs/PROGRESS.md
git commit -m "docs: add verification workflow"
```

- [x] **Step 9: Push**

Run:

```bash
git push
```

Expected: commits are pushed to `origin/main`.

## Self-Review Checklist

- Spec goal "video to light pixel-art style" maps to Tasks 3, 4, 5, 6, 7, and 8.
- Audio preservation maps to Tasks 6 and 7.
- Reproducible CLI and config maps to Tasks 2 and 8.
- Fast and stable workflows map to Tasks 4, 7, 8, and 9.
- Modular image-processing stages map to Tasks 3, 4, and 5.
- `docs/PROGRESS.md` tracking maps to every task.
- GUI, Aseprite round-trip, scene segmentation, and batch queues are excluded from v0.1 as required by the design spec.
