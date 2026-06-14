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
    frame_window,
    iter_frames,
    mux_audio,
    probe_video,
    sample_frames,
    write_video,
)


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
    frames, metadata = prepare_source_frames(frames, config, metadata)

    with TemporaryDirectory(prefix="pixelator-") as temp_dir:
        silent_output = Path(temp_dir) / f"{final_output.stem}.silent.mp4"
        processed = process_frames(frames, config, metadata)
        write_video(processed, silent_output, metadata, codec=config.output.codec)
        if config.output.keep_audio:
            try:
                trim_start = config.trim.start if config.trim is not None else 0.0
                trim_duration = metadata.duration if config.trim is not None else None
                mux_audio(input_file, silent_output, final_output, trim_start, trim_duration)
            except VideoError:
                if config.output.audio_failure == "stop":
                    raise
                final_output.write_bytes(silent_output.read_bytes())
        else:
            final_output.write_bytes(silent_output.read_bytes())

    return final_output
