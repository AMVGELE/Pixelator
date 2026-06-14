# Pixelator Progress

This document tracks development status, decisions, validation commands, and blockers.
It should be updated throughout development.

## Current Status

- Phase: Implementation
- Active milestone: Milestone 0 - Repository Setup
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
- [ ] Add CLI entry point.
- [ ] Probe input video metadata.
- [ ] Decode frames.
- [ ] Apply basic pixelation.
- [ ] Encode output video.
- [ ] Preserve source audio.

### Milestone 2 - Fast And Stable Modes

- [ ] Add `fast` strategy.
- [ ] Add `stable` strategy.
- [ ] Add global sampled palette support.
- [ ] Add preset configs.
- [ ] Add comparison workflow.

### Milestone 3 - Effects And Presets

- [ ] Add CRT scanline effect.
- [ ] Add light VHS noise effect.
- [ ] Add chroma offset or color bleed effect.
- [ ] Make effects optional and subtle by default.

### Milestone 4 - Reliability Pass

- [ ] Add unit tests.
- [ ] Add sample verification commands.
- [ ] Improve user-facing errors.
- [ ] Update usage docs.

## Validation Log

- Implementation plan self-review completed on 2026-06-14.
- Implementation plan approved by user on 2026-06-14.
- `py -3.11 -m pytest tests/test_package.py -v` passed.

## Blockers

- None currently.

## Notes

- The first implementation should prioritize a closed end-to-end pipeline:
  `input.mp4 -> pixelated output.mp4`.
- `fast` mode is for parameter preview.
- `stable` mode is for final output with reduced temporal color flicker.
