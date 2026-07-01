# GUI Timeline Crop Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix GUI timeline preview and default-duration behavior, add numeric crop controls with visible output dimensions, and produce a reproducible Windows portable package.

**Architecture:** Keep the PySide6 workstation layout intact and make this an incremental polish pass over `MainWindow` and `PreviewWidget`. Add pure helper behavior where possible, prove the GUI wiring with offscreen Qt tests, and package through a PowerShell script that calls PyInstaller from the existing virtual environment.

**Tech Stack:** Python 3.11+, PySide6, Pillow, imageio-ffmpeg, PyInstaller, pytest, PowerShell, pathlib, dataclasses.

---

## Scope Check

This plan is one GUI polish and packaging milestone. It does not add processed live preview, multi-track editing, aspect-ratio locks, installer creation, code signing, or Aseprite round-tripping.

## File Structure

Modify:

- `src/pixelator/gui/main_window.py`: timeline placement, scrubber preview refresh, numeric crop controls, crop dimension label, full-duration trim handling.
- `src/pixelator/gui/preview.py`: expose crop clamping/source-size helpers needed by the main window and tests.
- `tests/test_gui_main_window.py`: offscreen Qt regression tests for scrubber preview and full-duration export behavior.
- `tests/test_gui_preview.py`: crop clamping helper tests.
- `tests/test_packaging.py`: packaging script presence and required behavior checks.
- `pyproject.toml`: add PyInstaller to dev dependencies.
- `README.md`: document Windows portable packaging and GUI crop/timeline controls.
- `docs/PROGRESS.md`: track GUI-6 progress and validation.

Create:

- `scripts/pixelator_gui_entry.py`: stable PyInstaller entry script.
- `scripts/package_windows.ps1`: reproducible Windows portable package script.

## Task 1: Documentation And Progress Setup

- [ ] **Step 1: Update GUI design spec**

Add GUI-6 requirements to `docs/superpowers/specs/2026-06-14-desktop-gui-design.md`: timeline above preview, scrubber refresh, numeric crop controls, visible output dimensions, full-duration default export, and Windows portable package.

- [ ] **Step 2: Save this implementation plan**

Create `docs/superpowers/plans/2026-06-14-gui-timeline-crop-packaging.md` with this content.

- [ ] **Step 3: Update progress**

In `docs/PROGRESS.md`, set:

```markdown
- Active milestone: GUI-6 - Timeline Numeric Crop And Portable Package
```

Add GUI-6 checklist items matching the scope above.

- [ ] **Step 4: Verify docs diff**

Run:

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors; docs only.

## Task 2: Failing Regression Tests

- [ ] **Step 1: Add main-window tests**

Create `tests/test_gui_main_window.py` with offscreen Qt tests:

```python
import os
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from pixelator.gui.main_window import MainWindow
from pixelator.video import VideoMetadata

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_scrubber_refreshes_preview_frame(monkeypatch, tmp_path: Path, qapp):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fake")
    requested_seconds = []

    monkeypatch.setattr(
        "pixelator.gui.main_window.probe_video",
        lambda path: VideoMetadata(width=64, height=48, fps=10.0, duration=10.0),
    )

    def fake_extract_frame(path, seconds=0.0):
        requested_seconds.append(seconds)
        return Image.new("RGB", (64, 48), (int(seconds) % 255, 0, 0))

    monkeypatch.setattr("pixelator.gui.main_window.extract_frame", fake_extract_frame)

    window = MainWindow()
    window.add_video_paths([source])
    window.scrubber_slider.setValue(500)

    assert requested_seconds[-1] == pytest.approx(5.0)
    window.close()


def test_default_gui_settings_export_full_duration(monkeypatch, tmp_path: Path, qapp):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fake")

    monkeypatch.setattr(
        "pixelator.gui.main_window.probe_video",
        lambda path: VideoMetadata(width=64, height=48, fps=10.0, duration=10.0),
    )
    monkeypatch.setattr(
        "pixelator.gui.main_window.extract_frame",
        lambda path, seconds=0.0: Image.new("RGB", (64, 48), (0, 0, 0)),
    )

    window = MainWindow()
    window.add_video_paths([source])
    job = window.queue.jobs[0]

    assert job.trim is None
    assert window._settings_for_job(job).trim is None
    assert window.trim_end_spin.value() == pytest.approx(10.0)
    window.close()
```

- [ ] **Step 2: Add crop helper test**

In `tests/test_gui_preview.py`, add:

```python
def test_clamp_crop_keeps_rectangle_inside_source():
    result = clamp_crop(CropConfig(x=90, y=40, width=30, height=20), (100, 50))

    assert result == CropConfig(x=90, y=40, width=10, height=10)
```

Update import:

```python
from pixelator.gui.preview import clamp_crop, fit_rect, preview_to_source_crop, source_to_preview_crop
```

- [ ] **Step 3: Add packaging script test**

In `tests/test_packaging.py`, add:

```python
from pathlib import Path


def test_windows_package_script_exists_and_uses_pyinstaller():
    script = Path("scripts/package_windows.ps1")

    assert script.exists()
    text = script.read_text(encoding="utf-8")
    assert "PyInstaller" in text
    assert "Pixelator.exe" in text
    assert "scripts/pixelator_gui_entry.py" in text.replace("\\", "/")
```

- [ ] **Step 4: Run targeted tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gui_main_window.py tests\test_gui_preview.py tests\test_packaging.py -v
```

Expected: FAIL because scrubber is not wired, `clamp_crop` is private, and packaging files do not exist.

## Task 3: Implement Timeline Preview And Trim Defaults

- [ ] **Step 1: Move timeline controls above preview**

In `MainWindow._build_layout()`, place a compact timeline row and `scrubber_slider` before `preview_widget`.

- [ ] **Step 2: Wire scrubber preview refresh**

Connect:

```python
self.scrubber_slider.valueChanged.connect(self._on_scrubber_changed)
```

Implement `_scrubber_seconds(job)` and `_on_scrubber_changed()` so slider value `0..1000` maps to `0..duration` and calls a shared `_load_preview_frame(job, seconds)`.

- [ ] **Step 3: Preserve full-duration default export**

Keep `job.trim is None` until the user edits start or end spin boxes. `_settings_for_job()` must pass `None` for trim in that state, while the UI still displays full duration in the end control.

- [ ] **Step 4: Run targeted GUI tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gui_main_window.py -v
```

Expected: pass.

## Task 4: Implement Numeric Crop Controls

- [ ] **Step 1: Promote crop clamping helper**

Rename `_clamp_crop()` to public `clamp_crop()` in `src/pixelator/gui/preview.py` and update `PreviewWidget.set_crop()`.

- [ ] **Step 2: Add crop controls**

In `MainWindow.__init__()`, add `QSpinBox` controls:

```python
self.crop_x_spin
self.crop_y_spin
self.crop_width_spin
self.crop_height_spin
self.crop_dimensions_label
```

Use a `_syncing_crop_controls` guard to avoid recursive updates.

- [ ] **Step 3: Synchronize drag and numeric edits**

Implement:

```python
_set_crop_controls_enabled(enabled)
_set_crop_controls_range(width, height)
_set_crop_controls_from_crop(crop)
_on_crop_spin_changed()
_update_crop_dimensions(crop)
```

Drag changes update the spins and label. Spin changes clamp the crop, update the preview rectangle, update the job, and refresh the queue row.

- [ ] **Step 4: Run targeted crop tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gui_preview.py tests\test_gui_main_window.py -v
```

Expected: pass.

## Task 5: Add Windows Portable Packaging

- [ ] **Step 1: Add dev dependency**

In `pyproject.toml`, add:

```toml
  "pyinstaller>=6.0",
```

- [ ] **Step 2: Add PyInstaller entry script**

Create `scripts/pixelator_gui_entry.py`:

```python
from pixelator.gui.app import main

raise SystemExit(main())
```

- [ ] **Step 3: Add PowerShell packaging script**

Create `scripts/package_windows.ps1` that:

- Resolves the repository root.
- Verifies recursive cleanup paths stay inside the repository.
- Installs `.[dev]`.
- Runs `python -m PyInstaller` with `--windowed`, `--name Pixelator`, `--distpath dist`, `--workpath build/pyinstaller`, `--specpath build/spec`, `--collect-all PySide6`, and `--collect-all imageio_ffmpeg`.
- Verifies `dist/Pixelator/Pixelator.exe` exists.

- [ ] **Step 4: Run packaging tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_packaging.py -v
```

Expected: pass.

## Task 6: Documentation, Build, And Verification

- [ ] **Step 1: Update README**

Add GUI notes for timeline scrub preview, crop numeric controls, and:

```powershell
.\scripts\package_windows.ps1
.\dist\Pixelator\Pixelator.exe
```

- [ ] **Step 2: Build package**

Run:

```powershell
.\scripts\package_windows.ps1
```

Expected: `dist\Pixelator\Pixelator.exe` exists.

- [ ] **Step 3: Smoke-check packaged GUI**

Run the packaged executable with `QT_QPA_PLATFORM=offscreen`, confirm the process stays alive briefly, then stop only that process.

- [ ] **Step 4: Full test suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 5: Manual render duration check**

Render from the GUI/offscreen harness with the test video and no explicit trim. Probe the output duration and confirm it is longer than one second for a longer source.

- [ ] **Step 6: Update progress**

Append exact validation commands and outcomes to `docs/PROGRESS.md`; mark GUI-6 complete.

- [ ] **Step 7: Commit and push**

Run:

```powershell
git add .
git commit -m "feat: polish gui timeline crop and packaging"
git push -u origin feature/gui-timeline-crop-package
```

## Self-Review Checklist

- Timeline controls above preview: Task 3.
- Scrubber refreshes preview: Task 2 regression plus Task 3 implementation.
- Full-duration default export: Task 2 regression plus Task 3 implementation.
- Numeric crop controls and output dimensions: Task 4.
- Windows portable package and script: Task 5 and Task 6.
- Progress tracking: Task 1 and Task 6.
