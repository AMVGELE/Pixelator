# Pixelator Progress

This document tracks development status, decisions, validation commands, and blockers.
It should be updated throughout development.

## Current Status

- Phase: v0.1 implemented
- Active milestone: Milestone 4 - Reliability Pass
- Repository: https://github.com/AMVGELE/Pixelator.git
- Design spec: `docs/superpowers/specs/2026-06-14-pixelator-v0.1-design.md`
- Implementation plan: `docs/superpowers/plans/2026-06-14-pixelator-v0.1-implementation.md`

## Decisions

- Build Pixelator as a Python library plus CLI first.
- Keep GUI work out of v0.1.
- Support both `fast` and `stable` modes from the beginning.
- Treat PAC Pixel Art Converter as an algorithm reference, not as source architecture.
- Use `docs/PROGRESS.md` as the live development tracker.
- Defer Aseprite or sprite-sheet round-tripping to v0.2.

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

## Blockers

- None currently.

## Notes

- The first implementation should prioritize a closed end-to-end pipeline:
  `input.mp4 -> pixelated output.mp4`.
- `fast` mode is for parameter preview.
- `stable` mode is for final output with reduced temporal color flicker.
