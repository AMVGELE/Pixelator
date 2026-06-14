# Pixelator v0.1 Design

Date: 2026-06-14

## Summary

Pixelator converts stylized source videos into a light pixel-art video style. The first
version will be a reusable Python library plus a CLI. It will provide two processing
modes:

- `fast`: quick preview renders with controllable speed.
- `stable`: final renders that prioritize temporal color stability and reduced flicker.

The first release focuses on a reliable video pipeline rather than a GUI. GUI and
Aseprite round-tripping are planned for later versions.

## Goals

- Convert an input video into a lightly pixelated output video.
- Preserve the source audio when possible.
- Provide reproducible CLI commands and config files.
- Support both fast preview and stable final-output workflows.
- Keep image-processing stages modular so algorithms can be swapped later.
- Maintain `docs/PROGRESS.md` during development so project status is visible.

## Non-Goals

- No desktop GUI in v0.1.
- No Aseprite import/export round-trip in v0.1.
- No full manual frame editing workflow in v0.1.
- No machine-learning style transfer in v0.1.
- No attempt to clone PAC's GUI.

## Reference: PAC Pixel Art Converter

PAC is used as an algorithm reference, not as the architecture target. Relevant ideas:

- Downscale frames to a lower pixel resolution.
- Upscale with nearest-neighbor sampling.
- Quantize colors to a limited palette.
- Adjust brightness, sharpness, and color vibrance.

Pixelator extends this into a video-first workflow by adding:

- Audio preservation.
- CLI and config-driven repeatability.
- Shared pipeline stages with replaceable strategies.
- Stable palette selection to reduce frame-to-frame flicker.
- Optional CRT/VHS style post-processing.
- Batch-friendly output and progress logging.

## User Workflow

Basic commands:

```bash
pixelator input.mp4 --mode fast --out output-fast.mp4
pixelator input.mp4 --mode stable --out output-stable.mp4
pixelator input.mp4 --config pixelator.yaml
```

Expected v0.1 workflow:

1. Run `fast` mode for quick previews.
2. Tune pixel scale, palette size, sharpening, saturation, and effect strength.
3. Run `stable` mode for final output.
4. Compare preview and final output.
5. Record decisions and progress in `docs/PROGRESS.md`.

## Pipeline

```text
Probe input video
  -> Decode frames
  -> Sample frames for analysis
  -> Build processing plan
  -> Pixelate frames
  -> Apply palette mapping
  -> Upscale with nearest-neighbor sampling
  -> Apply optional CRT/VHS effects
  -> Encode output video
  -> Merge or copy source audio
```

## Architecture

### `pixelator.core`

Owns reusable pipeline primitives:

- Video metadata probing.
- Frame iteration.
- Frame writing.
- Audio extraction and muxing helpers.
- Config models.
- Pipeline orchestration.

The rest of the project should call into this layer instead of shelling out ad hoc.

### `pixelator.image`

Owns per-frame image operations:

- Downscale.
- Nearest-neighbor upscale.
- Palette quantization.
- Brightness adjustment.
- Sharpness adjustment.
- Saturation or vibrance adjustment.

These operations should be deterministic for a given input frame and config.

### `pixelator.strategies`

Owns the differences between render modes.

`fast` mode:

- Prioritizes short iteration time.
- Uses simple sampling or per-frame quantization.
- May skip expensive temporal analysis.
- Should expose worker count and preview duration controls.

`stable` mode:

- Prioritizes reduced flicker and repeatable color.
- Builds a global or sampled palette before full rendering.
- Reuses the selected palette across frames.
- May process fewer frames in parallel if ordering or cached analysis requires it.

Both modes must share the same high-level pipeline.

### `pixelator.effects`

Owns optional post-processing:

- Subtle CRT scanlines.
- VHS noise.
- Mild chroma offset.
- Color bleed.
- Output-safe effect presets.

Effects should be optional and parameterized. The default preset should be subtle.

### `pixelator.cli`

Owns user-facing commands:

- Argument parsing.
- Config loading.
- Preset selection.
- Logging.
- Exit codes.
- Friendly error messages.

The CLI should remain thin and delegate processing to library modules.

## Configuration

Example:

```yaml
mode: stable
pixel:
  scale: 4
  target_width: null
palette:
  strategy: global_sampled
  colors: 32
image:
  brightness: 1.0
  sharpness: 1.2
  saturation: 1.1
effects:
  crt: subtle
  vhs: light
performance:
  workers: auto
  preview_seconds: null
output:
  keep_audio: true
  codec: h264
```

CLI flags should override config values.

## Error Handling

Pixelator should fail with clear messages for:

- Missing input file.
- Unsupported video file.
- Missing FFmpeg or codec tools.
- Invalid config values.
- Output path conflicts when overwrite is not enabled.
- Audio muxing failure.

If audio preservation fails, the tool should report the failure and either stop or
continue without audio depending on a config option.

## Testing And Verification

v0.1 should include focused tests for:

- Config parsing and CLI override behavior.
- Frame downscale/upscale dimensions.
- Palette quantization result constraints.
- Strategy selection.
- Output-path handling.

Manual verification commands:

```bash
pixelator sample.mp4 --mode fast --out out-fast.mp4
pixelator sample.mp4 --mode stable --out out-stable.mp4
```

Manual acceptance checks:

- Output videos are playable.
- Output resolution matches expected settings.
- Source audio is preserved when `keep_audio` is true.
- `fast` mode completes quickly enough for parameter preview.
- `stable` mode has visibly less color flicker than naive per-frame quantization.
- CRT/VHS effects are subtle by default and can be disabled.

## Development Tracking

`docs/PROGRESS.md` is the living status document. It should be updated whenever:

- A milestone starts or finishes.
- A major design decision changes.
- A validation command passes or fails.
- A blocker appears.
- A release candidate is prepared.

## Milestones

### Milestone 0: Repository Setup

- Add project skeleton.
- Add dependency and environment documentation.
- Add progress tracking document.

### Milestone 1: Minimal Video Loop

- Probe video.
- Decode frames.
- Apply basic pixelation.
- Encode output video.
- Preserve or remux audio.

### Milestone 2: Fast And Stable Modes

- Implement `fast` mode.
- Implement `stable` global sampled palette mode.
- Add mode-specific presets.
- Add sample-based comparison workflow.

### Milestone 3: Effects And Presets

- Add subtle CRT effect.
- Add light VHS effect.
- Add preset config files.
- Keep effects optional.

### Milestone 4: Reliability Pass

- Add tests around core behavior.
- Improve errors and logs.
- Verify output on sample videos.
- Update progress and usage docs.

## Future Work

- Aseprite or sprite-sheet round-trip.
- Shot or scene segmentation for per-scene palettes.
- GUI or local web UI.
- Batch queue processing.
- Side-by-side preview generation.
- Palette import and export.
