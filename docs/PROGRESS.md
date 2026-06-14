# Pixelator Progress

This document tracks development status, decisions, validation commands, and blockers.
It should be updated throughout development.

## Current Status

- Phase: GUI implemented
- Active milestone: GUI-5 - Packaging And Polish
- Repository: https://github.com/AMVGELE/Pixelator.git
- Design spec: `docs/superpowers/specs/2026-06-14-pixelator-v0.1-design.md`
- GUI design spec: `docs/superpowers/specs/2026-06-14-desktop-gui-design.md`
- Implementation plan: `docs/superpowers/plans/2026-06-14-pixelator-v0.1-implementation.md`
- GUI implementation plan: `docs/superpowers/plans/2026-06-14-pixelator-desktop-gui-implementation.md`

## Decisions

- Build Pixelator as a Python library plus CLI first.
- Keep GUI work out of v0.1.
- Support both `fast` and `stable` modes from the beginning.
- Treat PAC Pixel Art Converter as an algorithm reference, not as source architecture.
- Use `docs/PROGRESS.md` as the live development tracker.
- Defer Aseprite or sprite-sheet round-tripping to v0.2.
- Build the next GUI milestone as a PySide6 desktop application with a restrained
  video-processing workstation style.
- Include draggable crop selection and source time trimming in the first GUI scope.

## Milestone Checklist

### Milestone 0 - Repository Setup

- [x] Clone empty Pixelator repository.
- [x] Add v0.1 design spec.
- [x] Add progress tracking document.
- [x] Review design with user.
- [x] Create implementation plan after design approval.
- [x] Review implementation plan with user.
- [x] Add project skeleton.
- [x] Add dependency and environment documentation.

### Milestone 1 - Minimal Video Loop

- [x] Add project skeleton.
- [x] Add CLI entry point.
- [x] Probe input video metadata.
- [x] Decode frames.
- [x] Apply basic pixelation.
- [x] Encode output video.
- [x] Preserve source audio.

### Milestone 2 - Fast And Stable Modes

- [x] Add `fast` strategy.
- [x] Add `stable` strategy.
- [x] Add global sampled palette support.
- [x] Add preset configs.
- [x] Add comparison workflow.

### Milestone 3 - Effects And Presets

- [x] Add CRT scanline effect.
- [x] Add light VHS noise effect.
- [x] Add chroma offset or color bleed effect.
- [x] Make effects optional and subtle by default.

### Milestone 4 - Reliability Pass

- [x] Add unit tests.
- [x] Add sample verification commands.
- [x] Improve user-facing errors.
- [x] Update usage docs.

### GUI-0 - Desktop GUI Design

- [x] Confirm desktop window GUI direction.
- [x] Confirm restrained video-processing workstation visual direction.
- [x] Include queue, preview, draggable crop selection, and source time trimming in scope.
- [x] Add GUI design spec.
- [x] Review GUI design spec with user.
- [x] Create GUI implementation plan after design approval.

### GUI-1 - Pipeline Crop And Trim

- [x] Add crop and trim config models.
- [x] Add CLI crop and trim flags.
- [x] Apply crop and trim in the shared render pipeline.
- [x] Trim source audio during mux when possible.
- [x] Add automated tests for config, CLI, pipeline, and video helpers.

### GUI-2 - Desktop Skeleton

- [x] Add PySide6 dependency and `pixelator-gui` entry point.
- [x] Add main window layout.
- [x] Add queue panel.
- [x] Add settings panel.
- [x] Add preview and log panel placeholders.

### GUI-3 - Preview, Crop, And Trim Interaction

- [x] Load source metadata and preview frames.
- [x] Implement draggable crop rectangle.
- [x] Implement trim start/end controls.
- [x] Bind preview state to render settings.

### GUI-4 - Queue Rendering

- [x] Add background render worker.
- [x] Render queued jobs through the shared pipeline.
- [x] Update queue progress, completion, failure, and cancellation states.
- [x] Keep the window responsive during rendering.

### GUI-5 - Packaging And Polish

- [x] Document GUI launch and usage.
- [x] Run full automated tests.
- [x] Verify CLI crop and trim against the Chinese-path test video.
- [x] Verify GUI launch and manual render.
- [x] Commit and push final GUI milestone.

## Validation Log

- Implementation plan self-review completed on 2026-06-14.
- Implementation plan approved by user on 2026-06-14.
- `py -3.11 -m pytest tests/test_package.py -v` passed.
- `py -3.11 -m pytest tests/test_config.py -v` passed.
- `py -3.11 -m pytest tests/test_image_ops.py -v` passed.
- `py -3.11 -m pytest tests/test_palette.py -v` passed.
- `py -3.11 -m pytest tests/test_effects.py -v` passed.
- `py -3.11 -m pytest tests/test_video.py -v` passed.
- `py -3.11 -m pytest tests/test_pipeline.py -v` passed.
- `py -3.11 -m pytest -v` passed with 22 tests.
- `py -3.11 -m pytest tests/test_cli.py -v` passed.
- `py -3.11 -m pixelator --help` passed.
- `py -3.11 -m pytest -v` passed with 24 tests.
- `py -3.11 -m pip install -e ".[dev]"` passed.
- Synthetic sample video created at `outputs/sample.mp4`.
- `pixelator outputs/sample.mp4 --mode fast --out outputs/sample-fast.mp4 --overwrite --no-audio` passed.
- `pixelator outputs/sample.mp4 --mode stable --out outputs/sample-stable.mp4 --overwrite --no-audio` passed.
- Output probe passed for `outputs/sample.mp4`, `outputs/sample-fast.mp4`, and `outputs/sample-stable.mp4` at `96x64 @ 12fps`.
- Audio preservation probe passed for `outputs/sample-audio-fast.mp4`; FFmpeg reported an AAC audio stream in the rendered output.
- Desktop GUI design started on 2026-06-14.
- Baseline before GUI implementation: `.\.venv\Scripts\python.exe -m pytest -q` passed with 25 tests and 8 Pillow deprecation warnings.
- Desktop GUI implementation plan added on 2026-06-14.
- `.\.venv\Scripts\python.exe -m pytest tests\test_config.py -v` passed with 9 tests after adding crop and trim config models.
- `.\.venv\Scripts\python.exe -m pytest tests\test_cli.py -v` passed with 4 tests after adding CLI crop and trim flags.
- `.\.venv\Scripts\python.exe -m pytest tests\test_video.py tests\test_pipeline.py -v` passed with 11 tests after applying crop and trim to source frames.
- `.\.venv\Scripts\python.exe -m pytest tests\test_config.py tests\test_cli.py tests\test_video.py tests\test_pipeline.py -v` passed with 25 tests after adding audio trim mux arguments.
- `.\.venv\Scripts\python.exe -m pytest tests\test_gui_models.py -v` passed with 3 tests after adding GUI queue and render settings models.
- `.\.venv\Scripts\python.exe -m pytest tests\test_gui_preview.py -v` passed with 3 tests after adding crop coordinate mapping helpers.
- `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"` installed PySide6 6.11.1 successfully.
- `QT_QPA_PLATFORM=offscreen` PySide6 smoke instantiated `MainWindow` with title `Pixelator Desktop` and minimum size `1280x720`.
- `.\.venv\Scripts\python.exe -m pytest -q` passed with 42 tests after adding the desktop GUI skeleton.
- `.\.venv\Scripts\python.exe -m pytest tests\test_video.py tests\test_gui_preview.py -v` passed with 12 tests after adding preview frame extraction and `PreviewWidget`.
- Offscreen GUI loaded `D:\GameJamTools\章鱼哥.mp4`, probed metadata, and initialized full-frame crop for a Chinese-path source video.
- Offscreen GUI queue render completed for `D:\GameJamTools\章鱼哥.mp4` with crop `120,180,360,360`, trim `0.0,1.0`, mode `fast`, pixel scale `12`, colors `12`.
- Latest offscreen GUI output probe reported `360x360 @ 30fps`, duration `1.0s`.
- `.\.venv\Scripts\python.exe -m pytest -q` passed with 46 tests after adding preview, crop, trim, queue worker, macro-block preservation, and linear-light downsampling.
- QtTest offscreen drag simulation changed preview crop to `x=357, y=268, width=643, height=232`.
- `.\.venv\Scripts\pixelator.exe $env:PIXELATOR_TEST_VIDEO --mode fast --pixel-scale 8 --colors 16 --crop 80,120,560,720 --trim 1.0,4.0 --out outputs\gui-pipeline-check.mp4 --overwrite` passed using `D:\GameJamTools\章鱼哥.mp4` as the source path.
- `outputs\gui-pipeline-check.mp4` probed as `560x720 @ 30fps`, duration `3.0s`.
- FFmpeg stream probe reported H.264 video and AAC stereo audio in `outputs\gui-pipeline-check.mp4`.
- `.venv\Scripts\pixelator-gui.exe` exists after editable install; launching it enters the Qt event loop as expected.

## Blockers

- None currently.

## Notes

- The first implementation should prioritize a closed end-to-end pipeline:
  `input.mp4 -> pixelated output.mp4`.
- `fast` mode is for parameter preview.
- `stable` mode is for final output with reduced temporal color flicker.
