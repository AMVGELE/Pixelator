from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable, Iterator

from PIL import Image

from pixelator.config import RenderConfig
from pixelator.effects import apply_effects
from pixelator.errors import VideoError
from pixelator.image_ops import adjust_frame, pixelate_frame
from pixelator.palette import (
    apply_auto_match_palette,
    apply_palette,
    auto_match_palette,
    build_global_palette,
    custom_palette,
    quantize_per_frame,
)
from pixelator.video import (
    VideoMetadata,
    ensure_output_path,
    frame_window,
    iter_frames,
    is_gif_path,
    mux_audio,
    probe_video,
    sample_frames,
    write_gif,
    write_video,
)


def prepare_source_frames(
    frames: Iterable[Image.Image],
    config: RenderConfig,
    metadata: VideoMetadata,
    encoder_safe: bool = True,
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
    if encoder_safe:
        frame_list, metadata = _make_frames_encoder_safe(frame_list, metadata)
    return frame_list, metadata


def _make_frames_encoder_safe(
    frames: list[Image.Image],
    metadata: VideoMetadata,
) -> tuple[list[Image.Image], VideoMetadata]:
    width = _even_encoder_dimension(metadata.width)
    height = _even_encoder_dimension(metadata.height)
    if width < 2 or height < 2:
        raise VideoError("Output dimensions must be at least 2x2 for H.264 yuv420p encoding")
    if (width, height) == metadata.size:
        return frames, metadata
    resized = [frame.crop((0, 0, width, height)) for frame in frames]
    return resized, VideoMetadata(width=width, height=height, fps=metadata.fps, duration=metadata.duration)


def _even_encoder_dimension(value: int) -> int:
    if value <= 2:
        return value
    return value if value % 2 == 0 else value - 1


def process_frames(
    frames: Iterable[Image.Image],
    config: RenderConfig,
    metadata: VideoMetadata,
) -> Iterator[Image.Image]:
    frame_list = list(frames)
    explicit_palette = custom_palette(config.palette)
    auto_match = auto_match_palette(config.palette)
    palette = None
    if explicit_palette is None and auto_match is None and config.mode == "stable":
        samples = sample_frames(frame_list, config.palette.sample_frames)
        adjusted_samples = [adjust_frame(pixelate_frame(frame, config.pixel), config.image) for frame in samples]
        palette = build_global_palette(adjusted_samples, config.palette)

    for index, frame in enumerate(frame_list):
        result = pixelate_frame(frame, config.pixel)
        result = adjust_frame(result, config.image)
        if explicit_palette is None and auto_match is None and config.mode == "stable" and palette is not None:
            result = apply_palette(result, palette)
        elif explicit_palette is None and auto_match is None:
            result = quantize_per_frame(result, config.palette)
        result = apply_effects(result, config.effects, frame_index=index)
        if explicit_palette is not None:
            result = apply_palette(result, explicit_palette)
        elif auto_match is not None:
            source_colors, target_colors, sort_mode = auto_match
            result = apply_auto_match_palette(result, source_colors, target_colors, sort_mode)
        if result.size != metadata.size:
            result = result.resize(metadata.size, Image.Resampling.NEAREST)
        yield result


def render_video(input_path: str | Path, output_path: str | Path, config: RenderConfig) -> Path:
    input_file = Path(input_path)
    if not input_file.exists():
        raise VideoError(f"Input video does not exist: {input_file}")

    final_output = ensure_output_path(output_path, overwrite=config.output.overwrite)
    output_is_gif = is_gif_path(final_output)
    input_is_gif = is_gif_path(input_file)
    metadata = probe_video(input_file)
    frames = list(iter_frames(input_file))
    frames, metadata = prepare_source_frames(frames, config, metadata, encoder_safe=not output_is_gif)

    if output_is_gif:
        processed = process_frames(frames, config, metadata)
        write_gif(processed, final_output, metadata)
        return final_output

    with TemporaryDirectory(prefix="pixelator-") as temp_dir:
        silent_output = Path(temp_dir) / f"{final_output.stem}.silent.mp4"
        processed = process_frames(frames, config, metadata)
        write_video(processed, silent_output, metadata, codec=config.output.codec)
        if config.output.keep_audio and not input_is_gif:
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
