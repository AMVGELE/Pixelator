# Pixelator Desktop GUI Design

Date: 2026-06-14

## Summary

Pixelator's next milestone is a restrained desktop video-processing workstation. The
GUI will wrap the existing Python library and CLI pipeline with a first-class visual
workflow for batch rendering, parameter tuning, crop selection, and time trimming.

The recommended implementation is a PySide6 desktop application. This keeps the GUI
close to the current Python codebase, avoids a separate frontend/runtime stack, and
gives enough control for video preview widgets, draggable crop handles, queues, logs,
and future Windows packaging.

## Goals

- Provide a desktop window for converting videos into the existing light pixel-art
  style.
- Support a visible job queue with queued, running, completed, failed, and cancelled
  states.
- Let users tune the current Pixelator parameters without writing CLI commands.
- Let users define a draggable crop rectangle from a video preview.
- Let users set start and end trim times before rendering.
- Preserve the current `fast` and `stable` render modes.
- Reuse the existing pipeline instead of duplicating processing logic in the GUI.
- Keep the visual style restrained, dense, and tool-focused.
- Maintain `docs/PROGRESS.md` as milestones move forward.

## Non-Goals

- No web UI in this milestone.
- No Tauri or Electron runtime in this milestone.
- No frame-by-frame manual pixel editing.
- No Aseprite round-trip editing.
- No multi-track video editing timeline.
- No advanced color grading UI beyond the existing Pixelator controls.
- No visual ideation pass unless the user asks for it later.

## Visual Direction

The GUI should feel like a practical desktop video tool, closer to HandBrake or a
compact DaVinci Resolve utility panel than a landing page or showcase app.

Design principles:

- Dense but readable controls.
- Neutral dark or muted system-style palette.
- Clear grouping for input, preview, render settings, queue, and output.
- Small icon buttons where appropriate, with tooltips.
- Minimal ornamentation.
- Stable dimensions for preview, controls, queue rows, and progress areas.
- No decorative hero sections, gradients, bokeh, or large marketing-style cards.

## Primary User Workflow

1. Open Pixelator Desktop.
2. Add one or more videos by file picker or drag-and-drop.
3. Select a video in the queue.
4. Inspect source metadata such as resolution, duration, frame rate, and audio state.
5. Preview a representative frame or scrub to a timestamp.
6. Adjust crop by dragging a rectangle on the preview.
7. Set trim start and end times on the timeline controls.
8. Choose a preset or tune parameters such as mode, pixel scale, palette size,
   saturation, sharpness, CRT strength, and VHS strength.
9. Start rendering.
10. Watch progress, logs, and job state.
11. Open the output file or containing folder.

## Layout

The first version should use one main window with four regions:

- Left queue panel: input list, job status, progress, and basic actions.
- Center preview panel: video preview, crop overlay, scrubber, and trim controls.
- Right settings panel: render mode, presets, pixel settings, palette settings,
  image adjustments, effects, audio/output options.
- Bottom console/status panel: current task message, expandable logs, and errors.

The layout should be usable at common desktop sizes such as 1280x720 and 1440x900.
Panels may be resizable, but their minimum sizes should prevent controls from
overlapping or truncating important labels.

## Controls

### Queue

Each queue item should show:

- Source filename.
- Source duration and resolution after probing succeeds.
- Render mode or preset.
- Status: `queued`, `running`, `completed`, `failed`, or `cancelled`.
- Progress percentage when available.
- Output path when completed.

Queue actions:

- Add files.
- Remove selected job.
- Clear completed jobs.
- Move selected job up or down.
- Start queue.
- Pause after current job.
- Cancel selected running job when supported by the worker process.

### Preview And Crop

The preview panel should display a frame from the selected source video. The crop
overlay should be draggable and resizable from handles.

Crop behavior:

- Store crop in source-video pixel coordinates, not preview-widget coordinates.
- Clamp crop to the video bounds.
- Support reset-to-full-frame.
- Support common aspect locks later, but default v1 behavior is freeform crop.
- Show numeric crop values for `x`, `y`, `width`, and `height`.
- Show the output `width` and `height` clearly near the crop controls.
- Let users adjust crop `x`, `y`, `width`, and `height` with numeric inputs.
- Keep numeric crop inputs and the draggable preview rectangle synchronized.

The first implementation may preview source frames rather than fully processed pixel
frames. Processed preview can be added later as a separate feature.

### Trim

Trim controls should define a source time range:

- Start time.
- End time.
- Duration preview.
- Scrubber position for frame preview.
- The timeline and trim controls should sit above the preview so the current
  frame can be checked directly under the active time controls.

Trim behavior:

- Default range is the full video.
- Clamp start and end inside the source duration.
- Prevent start from being equal to or greater than end.
- Store values in seconds as floats internally.
- Format values as timecode in the UI.
- Moving the scrubber should refresh the preview frame without changing the
  selected trim range.

### Render Settings

The GUI should expose the important v0.1 settings without overwhelming the first
screen:

- Mode: `fast` or `stable`.
- Preset: built-in preset selector.
- Pixel scale.
- Palette color count.
- Brightness.
- Sharpness.
- Saturation.
- CRT effect strength or preset.
- VHS effect strength or preset.
- Keep audio toggle.
- Output folder.
- Overwrite behavior.

Advanced settings can live in a collapsible section once the core workflow works.

## Architecture

### `pixelator.gui.app`

Owns application startup, command-line launch behavior for the GUI, Qt application
lifetime, and top-level window creation.

### `pixelator.gui.main_window`

Owns the main window layout, menus, panels, and high-level signal wiring. It should
not run video processing directly.

### `pixelator.gui.models`

Owns GUI-side data models:

- `VideoJob`
- `JobQueue`
- `CropSelection`
- `TrimRange`
- `RenderSettings`
- `JobStatus`

These models should be small and testable without creating Qt widgets.

### `pixelator.gui.preview`

Owns source-frame preview, crop overlay drawing, mouse interaction, coordinate
conversion, and scrubber frame requests.

### `pixelator.gui.worker`

Owns background rendering workers and progress events. It should call the existing
Pixelator library API rather than shelling out to the CLI when possible.

### `pixelator.gui.settings_panel`

Owns settings controls and conversion between widget values and `RenderSettings`.

### `pixelator.gui.queue_panel`

Owns queue display, selection, job actions, and progress updates.

## Data Flow

```text
User adds video
  -> GUI probes metadata through existing video helpers
  -> VideoJob is added to JobQueue
  -> User selects job
  -> Preview panel loads source frame
  -> User edits crop, trim, and render settings
  -> Start queue creates a render request
  -> Worker calls Pixelator pipeline with crop and trim options
  -> Worker emits progress, logs, completion, or error
  -> Queue and status panels update
```

The GUI should treat the existing pipeline as the source of truth for output
generation. If the pipeline lacks crop or trim options, those should be added to the
shared library layer before the GUI worker depends on them.

## Pipeline Changes Required

The current CLI pipeline already supports core rendering. The GUI milestone requires
two library-level additions:

- Crop support: accept an optional crop rectangle in source coordinates and apply it
  before pixelation.
- Trim support: accept optional start and end seconds and process only that source
  range while preserving audio for the same range when possible.

These changes should also be exposed through CLI flags so GUI behavior remains
testable without opening a window.

Suggested CLI additions:

```bash
pixelator input.mp4 --crop 80,40,480,360 --trim 1.5,8.0 --out output.mp4
```

## Error Handling

The GUI should report failures without losing the queue state.

Expected errors:

- Missing FFmpeg or unsupported codec.
- Failed metadata probe.
- Failed preview-frame extraction.
- Invalid crop or trim state.
- Output path conflict.
- Render worker crash or cancellation.
- Audio trim or mux failure.

For failed jobs, show a concise error in the queue row and keep the detailed message
in the bottom log panel.

## Persistence

The first version should persist lightweight local preferences:

- Last input folder.
- Last output folder.
- Last selected preset.
- Last window size.
- Last keep-audio and overwrite choices.

It should not persist private source file histories unless explicitly added later.

## Testing And Verification

Automated tests should cover:

- Crop coordinate conversion between preview widget and source pixels.
- Crop clamping.
- Trim validation.
- Render settings conversion.
- Job queue status transitions.
- CLI crop and trim argument parsing if added.
- Pipeline crop and trim behavior on synthetic video.

Manual checks should cover:

- Launching the GUI.
- Adding a video with a non-ASCII filename.
- Dragging and resizing the crop rectangle.
- Setting a trim range.
- Rendering one job.
- Rendering multiple queued jobs.
- Cancelling or failing a job without freezing the window.
- Opening the generated output.

## Milestones

### Milestone GUI-0: Design And Plan

- Write this design document.
- Review the design with the user.
- Write an implementation plan after approval.

### Milestone GUI-1: Pipeline Crop And Trim

- Add library config fields for crop and trim.
- Add CLI flags for crop and trim.
- Add tests for validation and output behavior.

### Milestone GUI-2: Desktop Skeleton

- Add PySide6 dependency.
- Add GUI entry point.
- Build main window layout.
- Add queue, settings, preview, and log panels with static wiring.

### Milestone GUI-3: Preview, Crop, And Trim Interaction

- Load source metadata and preview frames.
- Implement draggable crop rectangle.
- Implement trim controls and scrubber state.
- Bind UI state to job settings.

### Milestone GUI-4: Queue Rendering

- Add background worker.
- Render selected jobs.
- Update progress and logs.
- Handle completion, failure, and cancellation states.

### Milestone GUI-5: Packaging And Polish

- Add launch docs.
- Verify Windows local environment.
- Add packaging notes or initial PyInstaller config.
- Run manual video tests.

### Milestone GUI-6: Timeline, Numeric Crop, And Portable Package

- Move timeline and trim controls above the preview.
- Refresh the preview frame when the scrubber changes.
- Preserve full-source export duration when no trim range is explicitly edited.
- Add synchronized numeric crop `x`, `y`, `width`, and `height` controls.
- Show crop output dimensions in the GUI.
- Add a reproducible Windows portable packaging script.
- Build and smoke-check the local portable package.

## Future Work

- Processed preview for selected frames.
- Side-by-side source versus pixelated preview.
- Aspect-ratio locks for crop selection.
- Batch applying one crop and trim preset to many jobs.
- Per-job config import/export.
- Aseprite or sprite-sheet round-trip.
- Scene-aware palettes and per-scene settings.
