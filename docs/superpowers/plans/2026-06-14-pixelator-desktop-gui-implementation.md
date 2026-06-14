# Pixelator Desktop GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first PySide6 desktop GUI for Pixelator, including queue rendering, source preview, draggable crop selection, time trimming, and access to the existing render settings.

**Architecture:** Extend the shared Python pipeline first so crop and trim are testable through the CLI, then build a PySide6 desktop layer over the same library API. Keep GUI state in small dataclasses, widget code in focused modules, and rendering in background workers so the main window remains responsive.

**Tech Stack:** Python 3.11+, PySide6, Pillow, NumPy, PyYAML, imageio-ffmpeg, pytest, argparse, dataclasses, pathlib, subprocess.

---

## Scope Check

The GUI spec covers one product milestone: a restrained desktop video-processing workstation over the existing Pixelator pipeline. The milestone includes crop, trim, queue rendering, preview frames, settings controls, logs, docs, and local Windows verification. It excludes Web UI, Tauri, Electron, Aseprite round-tripping, frame-by-frame editing, and multi-track timeline editing.

## File Structure

Create these files:

- `docs/superpowers/plans/2026-06-14-pixelator-desktop-gui-implementation.md`: this implementation plan.
- `src/pixelator/gui/__init__.py`: GUI package marker.
- `src/pixelator/gui/app.py`: Qt application entry point and `main()` function.
- `src/pixelator/gui/main_window.py`: main window layout and high-level signal wiring.
- `src/pixelator/gui/models.py`: GUI dataclasses and queue state transitions.
- `src/pixelator/gui/preview.py`: preview frame widget, crop overlay, and coordinate conversion.
- `src/pixelator/gui/queue_panel.py`: queue list and job action widgets.
- `src/pixelator/gui/settings_panel.py`: render settings controls and conversion to config.
- `src/pixelator/gui/worker.py`: background render worker and progress events.
- `tests/test_gui_models.py`: Qt-free GUI model tests.
- `tests/test_gui_preview.py`: crop coordinate conversion tests.

Modify these files:

- `pyproject.toml`: add PySide6 dependency and `pixelator-gui` console script.
- `README.md`: document GUI launch, CLI crop/trim examples, and verification.
- `docs/PROGRESS.md`: track each GUI milestone and validation run.
- `src/pixelator/config.py`: add crop and trim dataclasses to `RenderConfig`.
- `src/pixelator/cli.py`: add `--crop` and `--trim` parsing.
- `src/pixelator/pipeline.py`: apply crop and trim before processing.
- `src/pixelator/video.py`: add frame-range iteration, preview-frame extraction, metadata helpers, and audio trimming/mux support.
- `tests/test_config.py`: cover crop and trim validation.
- `tests/test_cli.py`: cover CLI crop/trim dispatch.
- `tests/test_pipeline.py`: cover frame crop behavior and render orchestration.
- `tests/test_video.py`: cover frame-range math and audio mux command construction.

## Task 1: Plan And Progress Tracking

**Files:**
- Create: `docs/superpowers/plans/2026-06-14-pixelator-desktop-gui-implementation.md`
- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: Save this plan**

Create `docs/superpowers/plans/2026-06-14-pixelator-desktop-gui-implementation.md` with this content.

- [ ] **Step 2: Mark GUI plan status**

Update `docs/PROGRESS.md`:

```markdown
- Active milestone: GUI-1 - Pipeline Crop And Trim
- GUI implementation plan: `docs/superpowers/plans/2026-06-14-pixelator-desktop-gui-implementation.md`
```

Under `GUI-0 - Desktop GUI Design`, mark:

```markdown
- [x] Review GUI design spec with user.
- [x] Create GUI implementation plan after design approval.
```

Add milestone checklists for `GUI-1` through `GUI-5` using the milestone names from the design spec.

- [ ] **Step 3: Verify docs-only diff**

Run:

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors; only the plan and progress documents are modified.

- [ ] **Step 4: Commit**

Run:

```powershell
git add docs\superpowers\plans\2026-06-14-pixelator-desktop-gui-implementation.md docs\PROGRESS.md
git commit -m "docs: add desktop gui implementation plan"
```

## Task 2: Crop And Trim Configuration

**Files:**
- Modify: `src/pixelator/config.py`
- Modify: `tests/test_config.py`
- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: Write failing config tests**

Add to `tests/test_config.py`:

```python
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
```

Update the imports in `tests/test_config.py`:

```python
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
```

- [ ] **Step 2: Run config tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_config.py -v
```

Expected: FAIL because `CropConfig` and `TrimConfig` are not defined.

- [ ] **Step 3: Implement config dataclasses**

In `src/pixelator/config.py`, add:

```python
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
```

Add fields to `RenderConfig`:

```python
    crop: CropConfig | None = None
    trim: TrimConfig | None = None
```

In `config_from_dict()`, construct those fields:

```python
        crop=_optional_nested(CropConfig, raw.get("crop")),
        trim=_optional_nested(TrimConfig, raw.get("trim")),
```

Add helper:

```python
def _optional_nested(cls: type[Any], raw: dict[str, Any] | None) -> Any:
    if raw is None:
        return None
    return _nested(cls, raw)
```

Extend `validate_config()`:

```python
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
```

- [ ] **Step 4: Run config tests and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_config.py -v
```

Expected: all config tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src\pixelator\config.py tests\test_config.py docs\PROGRESS.md
git commit -m "feat: add crop and trim config"
```

## Task 3: CLI Crop And Trim Arguments

**Files:**
- Modify: `src/pixelator/cli.py`
- Modify: `tests/test_cli.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing CLI tests**

Add to `tests/test_cli.py`:

```python
def test_cli_dispatches_crop_and_trim(monkeypatch, tmp_path: Path):
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "output.mp4"
    input_path.write_bytes(b"fake")
    calls = {}

    def fake_render_video(input_file, output_file, config):
        calls["config"] = config
        output_path.write_bytes(b"rendered")
        return output_path

    monkeypatch.setattr(cli, "render_video", fake_render_video)

    exit_code = cli.main(
        [
            str(input_path),
            "--out",
            str(output_path),
            "--crop",
            "10,20,320,240",
            "--trim",
            "1.5,6.25",
            "--overwrite",
        ]
    )

    assert exit_code == 0
    assert calls["config"].crop.x == 10
    assert calls["config"].crop.y == 20
    assert calls["config"].crop.width == 320
    assert calls["config"].crop.height == 240
    assert calls["config"].trim.start == 1.5
    assert calls["config"].trim.end == 6.25


def test_cli_rejects_invalid_crop(capsys, tmp_path: Path):
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "output.mp4"
    input_path.write_bytes(b"fake")

    exit_code = cli.main([str(input_path), "--out", str(output_path), "--crop", "1,2,3"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--crop" in captured.err
```

- [ ] **Step 2: Run CLI tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_cli.py -v
```

Expected: FAIL because `--crop` and `--trim` do not exist.

- [ ] **Step 3: Implement CLI parsers**

In `src/pixelator/cli.py`, import crop and trim config:

```python
from pixelator.config import ConfigError, CropConfig, RenderConfig, TrimConfig, load_config, merge_cli_overrides
```

Add parser arguments:

```python
    parser.add_argument("--crop", type=_parse_crop, help="Crop rectangle as x,y,width,height in source pixels.")
    parser.add_argument("--trim", type=_parse_trim, help="Trim range as start,end seconds.")
```

Add overrides:

```python
            "crop": args.crop,
            "trim": args.trim,
```

Add parser helpers:

```python
def _parse_crop(value: str) -> CropConfig:
    parts = value.split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("--crop must use x,y,width,height")
    try:
        x, y, width, height = [int(part.strip()) for part in parts]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--crop values must be integers") from exc
    return CropConfig(x=x, y=y, width=width, height=height)


def _parse_trim(value: str) -> TrimConfig:
    parts = value.split(",")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("--trim must use start,end")
    try:
        start = float(parts[0].strip())
        end_text = parts[1].strip()
        end = None if end_text == "" else float(end_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--trim values must be seconds") from exc
    return TrimConfig(start=start, end=end)
```

- [ ] **Step 4: Run CLI tests and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_cli.py -v
```

Expected: all CLI tests pass.

- [ ] **Step 5: Update README**

Add:

```markdown
## Crop And Trim

```bash
pixelator input.mp4 --crop 80,40,480,360 --trim 1.5,8.0 --out output.mp4
```

Crop uses source-video pixel coordinates. Trim uses source-video seconds.
```

- [ ] **Step 6: Commit**

Run:

```powershell
git add src\pixelator\cli.py tests\test_cli.py README.md
git commit -m "feat: add cli crop and trim options"
```

## Task 4: Pipeline Crop And Trim Behavior

**Files:**
- Modify: `src/pixelator/pipeline.py`
- Modify: `src/pixelator/video.py`
- Modify: `tests/test_pipeline.py`
- Modify: `tests/test_video.py`
- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: Write failing video helper tests**

Add to `tests/test_video.py`:

```python
from pixelator.video import (
    VideoMetadata,
    ensure_output_path,
    frame_window,
    mux_audio,
    sample_frames,
)


def test_frame_window_uses_trim_bounds():
    metadata = VideoMetadata(width=320, height=180, fps=10.0, duration=5.0)

    start, end = frame_window(metadata, start_seconds=1.2, end_seconds=3.7, frame_count=50)

    assert start == 12
    assert end == 37


def test_frame_window_clamps_to_available_frames():
    metadata = VideoMetadata(width=320, height=180, fps=10.0, duration=5.0)

    start, end = frame_window(metadata, start_seconds=4.5, end_seconds=None, frame_count=50)

    assert start == 45
    assert end == 50
```

- [ ] **Step 2: Write failing pipeline crop tests**

Add to `tests/test_pipeline.py`:

```python
from pixelator.config import CropConfig, RenderConfig, TrimConfig
from pixelator.pipeline import prepare_source_frames, process_frames


def test_prepare_source_frames_applies_crop():
    frames = [Image.new("RGB", (10, 8), (255, 0, 0))]
    frames[0].putpixel((7, 5), (0, 255, 0))
    config = RenderConfig(crop=CropConfig(x=5, y=4, width=3, height=2))
    metadata = VideoMetadata(width=10, height=8, fps=24.0)

    prepared, prepared_metadata = prepare_source_frames(frames, config, metadata)

    assert prepared_metadata.size == (3, 2)
    assert prepared[0].size == (3, 2)
    assert prepared[0].getpixel((2, 1)) == (0, 255, 0)


def test_prepare_source_frames_applies_trim_by_frame_range():
    frames = [Image.new("RGB", (4, 4), (index, 0, 0)) for index in range(10)]
    config = RenderConfig(trim=TrimConfig(start=0.2, end=0.5))
    metadata = VideoMetadata(width=4, height=4, fps=10.0, duration=1.0)

    prepared, prepared_metadata = prepare_source_frames(frames, config, metadata)

    assert prepared_metadata.duration == 0.3
    assert [frame.getpixel((0, 0))[0] for frame in prepared] == [2, 3, 4]
```

- [ ] **Step 3: Run helper and pipeline tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_video.py tests\test_pipeline.py -v
```

Expected: FAIL because `frame_window` and `prepare_source_frames` do not exist.

- [ ] **Step 4: Implement frame window helper**

Add to `src/pixelator/video.py`:

```python
def frame_window(
    metadata: VideoMetadata,
    start_seconds: float = 0.0,
    end_seconds: float | None = None,
    frame_count: int | None = None,
) -> tuple[int, int]:
    total = frame_count
    if total is None and metadata.duration is not None:
        total = max(0, round(metadata.duration * metadata.fps))
    start_index = max(0, int(start_seconds * metadata.fps))
    if end_seconds is None:
        end_index = total if total is not None else start_index
    else:
        end_index = max(start_index, int(end_seconds * metadata.fps))
    if total is not None:
        start_index = min(start_index, total)
        end_index = min(end_index, total)
    return start_index, end_index
```

- [ ] **Step 5: Implement source preparation**

Add to `src/pixelator/pipeline.py`:

```python
def prepare_source_frames(
    frames: Iterable[Image.Image],
    config: RenderConfig,
    metadata: VideoMetadata,
) -> tuple[list[Image.Image], VideoMetadata]:
    frame_list = list(frames)
    if config.trim is not None:
        start_index, end_index = frame_window(
            metadata,
            start_seconds=config.trim.start,
            end_seconds=config.trim.end,
            frame_count=len(frame_list),
        )
        frame_list = frame_list[start_index:end_index]
        duration = len(frame_list) / metadata.fps if metadata.fps else None
        metadata = VideoMetadata(width=metadata.width, height=metadata.height, fps=metadata.fps, duration=duration)
    if config.crop is not None:
        left = config.crop.x
        upper = config.crop.y
        right = min(metadata.width, left + config.crop.width)
        lower = min(metadata.height, upper + config.crop.height)
        if right <= left or lower <= upper:
            raise VideoError("Crop rectangle is outside the source frame")
        frame_list = [frame.crop((left, upper, right, lower)) for frame in frame_list]
        metadata = VideoMetadata(width=right - left, height=lower - upper, fps=metadata.fps, duration=metadata.duration)
    return frame_list, metadata
```

Import `frame_window` in `src/pixelator/pipeline.py`:

```python
    frame_window,
```

Change `render_video()`:

```python
    frames = list(iter_frames(input_file))
    frames, metadata = prepare_source_frames(frames, config, metadata)
```

- [ ] **Step 6: Run helper and pipeline tests and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_video.py tests\test_pipeline.py -v
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add src\pixelator\pipeline.py src\pixelator\video.py tests\test_pipeline.py tests\test_video.py docs\PROGRESS.md
git commit -m "feat: apply crop and trim in pipeline"
```

## Task 5: Audio Trim Muxing

**Files:**
- Modify: `src/pixelator/video.py`
- Modify: `src/pixelator/pipeline.py`
- Modify: `tests/test_video.py`

- [ ] **Step 1: Write failing audio command test**

Add to `tests/test_video.py`:

```python
def test_mux_audio_applies_trim_arguments(monkeypatch, tmp_path: Path):
    calls = {}

    def fake_run(command, **kwargs):
        calls["command"] = command
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("pixelator.video.imageio_ffmpeg.get_ffmpeg_exe", lambda: "ffmpeg")
    monkeypatch.setattr("pixelator.video.subprocess.run", fake_run)

    mux_audio(
        tmp_path / "source.mp4",
        tmp_path / "silent.mp4",
        tmp_path / "output.mp4",
        start_seconds=1.25,
        duration_seconds=3.5,
    )

    command = calls["command"]
    assert "-ss" in command
    assert "1.25" in command
    assert "-t" in command
    assert "3.5" in command
```

- [ ] **Step 2: Run video tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_video.py -v
```

Expected: FAIL because `mux_audio()` does not accept trim arguments.

- [ ] **Step 3: Add optional trim arguments to mux_audio**

Change the signature in `src/pixelator/video.py`:

```python
def mux_audio(
    source_video: str | Path,
    silent_video: str | Path,
    output: str | Path,
    start_seconds: float = 0.0,
    duration_seconds: float | None = None,
) -> None:
```

Build the source input portion:

```python
    source_input: list[str] = []
    if start_seconds > 0:
        source_input.extend(["-ss", str(start_seconds)])
    if duration_seconds is not None:
        source_input.extend(["-t", str(duration_seconds)])
    source_input.extend(["-i", str(source_video)])
```

Replace the second input in `command` with:

```python
        "-i",
        str(silent_video),
        *source_input,
```

- [ ] **Step 4: Pass trim details from pipeline**

In `src/pixelator/pipeline.py`, before `mux_audio()`:

```python
                trim_start = config.trim.start if config.trim is not None else 0.0
                trim_duration = metadata.duration if config.trim is not None else None
                mux_audio(input_file, silent_output, final_output, trim_start, trim_duration)
```

- [ ] **Step 5: Run video tests and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_video.py -v
```

Expected: all video tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add src\pixelator\video.py src\pixelator\pipeline.py tests\test_video.py
git commit -m "feat: trim audio during mux"
```

## Task 6: GUI Models

**Files:**
- Create: `src/pixelator/gui/__init__.py`
- Create: `src/pixelator/gui/models.py`
- Create: `tests/test_gui_models.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add PySide6 dependency and GUI script**

In `pyproject.toml`, add dependency:

```toml
  "PySide6>=6.7",
```

Add script:

```toml
pixelator-gui = "pixelator.gui.app:main"
```

- [ ] **Step 2: Write failing model tests**

Create `tests/test_gui_models.py`:

```python
from pathlib import Path

from pixelator.config import CropConfig, TrimConfig
from pixelator.gui.models import JobQueue, JobStatus, RenderSettings, VideoJob


def test_video_job_defaults_to_full_frame_and_full_trim(tmp_path: Path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fake")

    job = VideoJob(source_path=source)

    assert job.status == JobStatus.QUEUED
    assert job.crop is None
    assert job.trim is None
    assert job.progress == 0


def test_job_queue_tracks_status_transitions(tmp_path: Path):
    queue = JobQueue()
    job = VideoJob(source_path=tmp_path / "clip.mp4")

    queue.add(job)
    queue.mark_running(job.id)
    queue.mark_completed(job.id, tmp_path / "out.mp4")

    assert queue.jobs[0].status == JobStatus.COMPLETED
    assert queue.jobs[0].progress == 100
    assert queue.jobs[0].output_path == tmp_path / "out.mp4"


def test_render_settings_create_config_with_crop_and_trim():
    settings = RenderSettings(
        mode="fast",
        pixel_scale=8,
        colors=16,
        keep_audio=False,
        overwrite=True,
        crop=CropConfig(x=1, y=2, width=30, height=40),
        trim=TrimConfig(start=0.5, end=2.0),
    )

    config = settings.to_config()

    assert config.mode == "fast"
    assert config.pixel.scale == 8
    assert config.palette.colors == 16
    assert config.output.keep_audio is False
    assert config.output.overwrite is True
    assert config.crop == settings.crop
    assert config.trim == settings.trim
```

- [ ] **Step 3: Run model tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gui_models.py -v
```

Expected: FAIL because `pixelator.gui.models` does not exist.

- [ ] **Step 4: Implement models**

Create `src/pixelator/gui/__init__.py`:

```python
"""Desktop GUI package for Pixelator."""
```

Create `src/pixelator/gui/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from pixelator.config import (
    CropConfig,
    EffectsConfig,
    ImageConfig,
    OutputConfig,
    PaletteConfig,
    PixelConfig,
    RenderConfig,
    TrimConfig,
)


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class VideoJob:
    source_path: Path
    id: str = ""
    output_path: Path | None = None
    status: JobStatus = JobStatus.QUEUED
    progress: int = 0
    error: str | None = None
    crop: CropConfig | None = None
    trim: TrimConfig | None = None
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None

    def __post_init__(self) -> None:
        if not self.id:
            object.__setattr__(self, "id", uuid4().hex)


@dataclass(frozen=True)
class RenderSettings:
    mode: str = "stable"
    pixel_scale: int = 4
    colors: int = 32
    brightness: float = 1.0
    sharpness: float = 1.2
    saturation: float = 1.1
    crt: str = "subtle"
    vhs: str = "light"
    keep_audio: bool = True
    overwrite: bool = False
    crop: CropConfig | None = None
    trim: TrimConfig | None = None

    def to_config(self) -> RenderConfig:
        return RenderConfig(
            mode=self.mode,
            pixel=PixelConfig(scale=self.pixel_scale),
            palette=PaletteConfig(colors=self.colors),
            image=ImageConfig(
                brightness=self.brightness,
                sharpness=self.sharpness,
                saturation=self.saturation,
            ),
            effects=EffectsConfig(crt=self.crt, vhs=self.vhs),
            output=OutputConfig(keep_audio=self.keep_audio, overwrite=self.overwrite),
            crop=self.crop,
            trim=self.trim,
        )


class JobQueue:
    def __init__(self) -> None:
        self.jobs: list[VideoJob] = []

    def add(self, job: VideoJob) -> None:
        self.jobs.append(job)

    def update(self, job_id: str, **changes: object) -> VideoJob:
        for index, job in enumerate(self.jobs):
            if job.id == job_id:
                updated = replace(job, **changes)
                self.jobs[index] = updated
                return updated
        raise KeyError(job_id)

    def mark_running(self, job_id: str) -> VideoJob:
        return self.update(job_id, status=JobStatus.RUNNING, progress=0, error=None)

    def mark_completed(self, job_id: str, output_path: Path) -> VideoJob:
        return self.update(job_id, status=JobStatus.COMPLETED, progress=100, output_path=output_path, error=None)

    def mark_failed(self, job_id: str, error: str) -> VideoJob:
        return self.update(job_id, status=JobStatus.FAILED, error=error)
```

- [ ] **Step 5: Run model tests and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gui_models.py -v
```

Expected: all model tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add pyproject.toml src\pixelator\gui\__init__.py src\pixelator\gui\models.py tests\test_gui_models.py
git commit -m "feat: add gui models"
```

## Task 7: Preview Crop Coordinate Model

**Files:**
- Create: `src/pixelator/gui/preview.py`
- Create: `tests/test_gui_preview.py`

- [ ] **Step 1: Write failing preview tests**

Create `tests/test_gui_preview.py`:

```python
from pixelator.config import CropConfig
from pixelator.gui.preview import fit_rect, preview_to_source_crop, source_to_preview_crop


def test_fit_rect_letterboxes_source_inside_widget():
    rect = fit_rect(source_size=(1920, 1080), widget_size=(800, 600))

    assert rect == (0, 75, 800, 450)


def test_source_to_preview_crop_maps_coordinates():
    crop = CropConfig(x=100, y=50, width=400, height=300)

    result = source_to_preview_crop(crop, source_size=(1000, 500), widget_size=(500, 500))

    assert result == (50, 150, 200, 150)


def test_preview_to_source_crop_clamps_to_source():
    result = preview_to_source_crop(
        preview_rect=(-20, 100, 700, 500),
        source_size=(1000, 500),
        widget_size=(500, 500),
    )

    assert result == CropConfig(x=0, y=0, width=1000, height=500)
```

- [ ] **Step 2: Run preview tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gui_preview.py -v
```

Expected: FAIL because preview mapping functions do not exist.

- [ ] **Step 3: Implement preview mapping helpers**

Create `src/pixelator/gui/preview.py`:

```python
from __future__ import annotations

from pixelator.config import CropConfig


def fit_rect(source_size: tuple[int, int], widget_size: tuple[int, int]) -> tuple[int, int, int, int]:
    source_width, source_height = source_size
    widget_width, widget_height = widget_size
    scale = min(widget_width / source_width, widget_height / source_height)
    width = round(source_width * scale)
    height = round(source_height * scale)
    x = round((widget_width - width) / 2)
    y = round((widget_height - height) / 2)
    return x, y, width, height


def source_to_preview_crop(
    crop: CropConfig,
    source_size: tuple[int, int],
    widget_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    x, y, width, height = fit_rect(source_size, widget_size)
    scale = width / source_size[0]
    return (
        round(x + crop.x * scale),
        round(y + crop.y * scale),
        round(crop.width * scale),
        round(crop.height * scale),
    )


def preview_to_source_crop(
    preview_rect: tuple[int, int, int, int],
    source_size: tuple[int, int],
    widget_size: tuple[int, int],
) -> CropConfig:
    fit_x, fit_y, fit_width, fit_height = fit_rect(source_size, widget_size)
    x, y, width, height = preview_rect
    left = max(fit_x, x)
    top = max(fit_y, y)
    right = min(fit_x + fit_width, x + width)
    bottom = min(fit_y + fit_height, y + height)
    scale = source_size[0] / fit_width
    source_x = round((left - fit_x) * scale)
    source_y = round((top - fit_y) * scale)
    source_right = round((right - fit_x) * scale)
    source_bottom = round((bottom - fit_y) * scale)
    return CropConfig(
        x=max(0, source_x),
        y=max(0, source_y),
        width=max(1, min(source_size[0], source_right) - max(0, source_x)),
        height=max(1, min(source_size[1], source_bottom) - max(0, source_y)),
    )
```

- [ ] **Step 4: Run preview tests and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gui_preview.py -v
```

Expected: all preview mapping tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src\pixelator\gui\preview.py tests\test_gui_preview.py
git commit -m "feat: add preview crop mapping"
```

## Task 8: Desktop Skeleton

**Files:**
- Create: `src/pixelator/gui/app.py`
- Create: `src/pixelator/gui/main_window.py`
- Create: `src/pixelator/gui/queue_panel.py`
- Create: `src/pixelator/gui/settings_panel.py`
- Modify: `README.md`
- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: Implement GUI application entry point**

Create `src/pixelator/gui/app.py`:

```python
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from pixelator.gui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    app = QApplication(argv if argv is not None else sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
```

- [ ] **Step 2: Implement settings panel**

Create `src/pixelator/gui/settings_panel.py` with a `SettingsPanel` widget containing mode, pixel scale, colors, brightness, sharpness, saturation, CRT, VHS, keep-audio, overwrite, output-folder fields, and a `settings()` method returning `RenderSettings`.

Use these widget names so later wiring is direct:

```python
self.mode_combo
self.pixel_scale_spin
self.colors_spin
self.brightness_spin
self.sharpness_spin
self.saturation_spin
self.crt_combo
self.vhs_combo
self.keep_audio_check
self.overwrite_check
self.output_folder_edit
```

- [ ] **Step 3: Implement queue panel**

Create `src/pixelator/gui/queue_panel.py` with a `QueuePanel` widget containing:

```python
self.add_button
self.remove_button
self.start_button
self.cancel_button
self.list_widget
```

Expose methods:

```python
def set_jobs(self, jobs: list[VideoJob]) -> None
def selected_job_id(self) -> str | None
```

- [ ] **Step 4: Implement main window layout**

Create `src/pixelator/gui/main_window.py` with a `MainWindow` using:

- Left `QueuePanel`.
- Center preview placeholder with crop and trim controls.
- Right `SettingsPanel`.
- Bottom `QPlainTextEdit` log area.

Set title to `Pixelator Desktop` and minimum size to `1280x720`.

- [ ] **Step 5: Smoke launch**

Run:

```powershell
.\.venv\Scripts\python.exe -m pixelator.gui.app
```

Expected: the desktop window opens. Close the window manually and record the result in `docs/PROGRESS.md`.

- [ ] **Step 6: Commit**

Run:

```powershell
git add src\pixelator\gui\app.py src\pixelator\gui\main_window.py src\pixelator\gui\queue_panel.py src\pixelator\gui\settings_panel.py README.md docs\PROGRESS.md
git commit -m "feat: add desktop gui skeleton"
```

## Task 9: Preview Frames, Crop Interaction, And Trim Controls

**Files:**
- Modify: `src/pixelator/video.py`
- Modify: `src/pixelator/gui/preview.py`
- Modify: `src/pixelator/gui/main_window.py`
- Modify: `tests/test_video.py`
- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: Add preview frame extraction test**

Add to `tests/test_video.py` a monkeypatched test that verifies `extract_frame(path, seconds)` calls the video reader and returns a `PIL.Image.Image`.

- [ ] **Step 2: Implement `extract_frame()`**

Add to `src/pixelator/video.py`:

```python
def extract_frame(path: str | Path, seconds: float = 0.0) -> Image.Image:
    metadata = probe_video(path)
    target_index = max(0, int(seconds * metadata.fps))
    for index, frame in enumerate(iter_frames(path)):
        if index >= target_index:
            return frame
    raise VideoError(f"Could not extract preview frame: {path}")
```

- [ ] **Step 3: Replace preview placeholder with crop widget**

Extend `src/pixelator/gui/preview.py` with a `PreviewWidget` subclass of `QWidget` that:

- Stores the current `QPixmap`.
- Stores source size and crop rectangle.
- Draws the frame letterboxed.
- Draws a crop rectangle with eight handles.
- Updates crop during mouse drag.
- Emits `cropChanged(CropConfig)`.

- [ ] **Step 4: Wire trim controls**

In `src/pixelator/gui/main_window.py`, add:

```python
self.trim_start_spin
self.trim_end_spin
self.scrubber_slider
```

When the selected job changes, set trim bounds from metadata duration. When a render starts, build `TrimConfig(start=..., end=...)` from these controls.

- [ ] **Step 5: Manual interaction check**

Run:

```powershell
.\.venv\Scripts\python.exe -m pixelator.gui.app
```

Expected: adding `D:\GameJamTools\章鱼哥.mp4` shows a preview frame, the crop rectangle drags and resizes, and trim controls accept start/end values.

- [ ] **Step 6: Commit**

Run:

```powershell
git add src\pixelator\video.py src\pixelator\gui\preview.py src\pixelator\gui\main_window.py tests\test_video.py docs\PROGRESS.md
git commit -m "feat: add gui preview crop and trim controls"
```

## Task 10: Background Queue Rendering

**Files:**
- Create: `src/pixelator/gui/worker.py`
- Modify: `src/pixelator/gui/main_window.py`
- Modify: `src/pixelator/gui/models.py`
- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: Implement render worker**

Create `src/pixelator/gui/worker.py` with a `RenderWorker(QObject)` that exposes:

```python
progressChanged = Signal(str, int)
logMessage = Signal(str)
jobCompleted = Signal(str, Path)
jobFailed = Signal(str, str)
```

Its `run()` method calls:

```python
output = render_video(job.source_path, output_path, settings.to_config())
```

- [ ] **Step 2: Wire start queue**

In `MainWindow`, connect `QueuePanel.start_button` to a method that:

- Picks queued jobs in order.
- Merges current crop and trim into `RenderSettings`.
- Creates output names in the selected output folder.
- Runs each job in a `QThread`.
- Updates queue rows and log area from worker signals.

- [ ] **Step 3: Wire add files**

In `MainWindow`, connect `QueuePanel.add_button` to `QFileDialog.getOpenFileNames()`, probe each file with `probe_video()`, and add `VideoJob` entries with width, height, fps, and duration.

- [ ] **Step 4: Wire cancellation state**

Support cancelling queued jobs immediately. For running jobs, set a cancellation request and mark cancellation after the worker returns if process interruption is not yet available.

- [ ] **Step 5: Manual queue check**

Run:

```powershell
.\.venv\Scripts\python.exe -m pixelator.gui.app
```

Expected: adding the test video, choosing output folder, and starting the queue generates an output video.

- [ ] **Step 6: Commit**

Run:

```powershell
git add src\pixelator\gui\worker.py src\pixelator\gui\main_window.py src\pixelator\gui\models.py docs\PROGRESS.md
git commit -m "feat: render gui queue in background"
```

## Task 11: Final Verification And Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: Install editable dependencies**

Run:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Expected: install succeeds and PySide6 is available.

- [ ] **Step 2: Run automated tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 3: Verify CLI crop and trim with Chinese-path source**

Run:

```powershell
.\.venv\Scripts\pixelator.exe "D:\GameJamTools\章鱼哥.mp4" --mode fast --pixel-scale 8 --colors 16 --crop 80,120,560,720 --trim 1.0,4.0 --out "outputs\章鱼哥-gui-pipeline-check.mp4" --overwrite
```

Expected: command exits 0 and writes a playable output.

- [ ] **Step 4: Verify GUI launch**

Run:

```powershell
.\.venv\Scripts\python.exe -m pixelator.gui.app
```

Expected: GUI opens locally.

- [ ] **Step 5: Verify GUI render manually**

In the GUI:

1. Add `D:\GameJamTools\章鱼哥.mp4`.
2. Drag crop rectangle.
3. Set trim start to `1.0` and trim end to `4.0`.
4. Set mode to `fast`, pixel scale to `8`, colors to `16`.
5. Choose `D:\GameJamTools\Pixelator\outputs` as output folder.
6. Start queue.

Expected: queue completes and writes a playable output video preserving audio when keep-audio is enabled.

- [ ] **Step 6: Update README**

Add GUI usage:

```markdown
## Desktop GUI

```bash
pixelator-gui
```

The desktop GUI supports adding videos to a queue, selecting a crop rectangle from
the source preview, setting trim start/end times, adjusting render settings, and
rendering through the same Pixelator pipeline used by the CLI.
```

- [ ] **Step 7: Update progress**

Update `docs/PROGRESS.md`:

```markdown
- Phase: GUI implemented
- Active milestone: GUI-5 - Packaging And Polish
```

Mark GUI milestone checklist items complete and append the exact validation commands
and outcomes.

- [ ] **Step 8: Commit and push**

Run:

```powershell
git add README.md docs\PROGRESS.md
git commit -m "docs: document desktop gui workflow"
git status --short
git push origin main
```

Expected: working tree is clean and commits are pushed to `origin/main`.

## Self-Review Checklist

- Spec goal "desktop video-processing workstation" maps to Tasks 8 through 10.
- Job queue maps to Tasks 6, 8, and 10.
- Parameter tuning maps to Tasks 6 and 8.
- Draggable crop maps to Tasks 7 and 9.
- Time trimming maps to Tasks 2, 3, 4, 5, and 9.
- Reuse of existing pipeline maps to Tasks 4, 5, and 10.
- Restrained desktop visual direction maps to Task 8.
- Progress tracking maps to Tasks 1, 4, 8, 9, 10, and 11.
- CLI crop/trim verification maps to Tasks 3, 4, 5, and 11.
- Non-goals remain excluded: no Web UI, no Tauri/Electron, no Aseprite round-trip, no multi-track editor.
