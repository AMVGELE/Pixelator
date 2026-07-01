from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable, Iterator

from PIL import Image

from pixelator.config import EffectsConfig, RenderConfig
from pixelator.effects import apply_effects, apply_palette_dither, dither_enabled
from pixelator.errors import ImageError, MediaError, VideoError
from pixelator.image_io import load_static_image, save_static_image
from pixelator.image_ops import adjust_frame, pixelate_frame, pixelate_frame_low
from pixelator.media import is_image_path, is_video_path
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

_FPS_MISMATCH_TOLERANCE = 0.05


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


def _metadata_with_decoded_timing(metadata: VideoMetadata, frame_count: int) -> VideoMetadata:
    if frame_count < 1 or metadata.duration is None or metadata.duration <= 0 or metadata.fps <= 0:
        return metadata
    decoded_fps = frame_count / metadata.duration
    relative_delta = abs(decoded_fps - metadata.fps) / metadata.fps
    if relative_delta <= _FPS_MISMATCH_TOLERANCE:
        return metadata
    return replace(metadata, fps=decoded_fps)


def process_frames(
    frames: Iterable[Image.Image],
    config: RenderConfig,
    metadata: VideoMetadata,
) -> Iterator[Image.Image]:
    frame_list = list(frames)
    use_palette = config.palette.strategy != "original"
    explicit_palette = custom_palette(config.palette) if use_palette else None
    auto_match = auto_match_palette(config.palette) if use_palette else None
    palette = None
    use_pixel_space_dither = use_palette and _use_pixel_space_dither(config, auto_match)
    if use_palette and explicit_palette is None and auto_match is None and config.mode == "stable":
        samples = sample_frames(frame_list, config.palette.sample_frames)
        if use_pixel_space_dither:
            adjusted_samples = [
                adjust_frame(pixelate_frame_low(frame, config.pixel), config.image) for frame in samples
            ]
        else:
            adjusted_samples = [adjust_frame(pixelate_frame(frame, config.pixel), config.image) for frame in samples]
        palette = build_global_palette(adjusted_samples, config.palette)

    for index, frame in enumerate(frame_list):
        result = (
            pixelate_frame_low(frame, config.pixel)
            if use_pixel_space_dither
            else pixelate_frame(frame, config.pixel)
        )
        result = adjust_frame(result, config.image)
        result = _apply_palette_and_effects(result, config, palette, explicit_palette, auto_match, index, use_palette)
        if use_pixel_space_dither:
            result = result.resize(metadata.size, Image.Resampling.NEAREST)
        elif result.size != metadata.size:
            result = result.resize(metadata.size, Image.Resampling.NEAREST)
        yield result


def _apply_palette_and_effects(
    result: Image.Image,
    config: RenderConfig,
    palette: list[tuple[int, int, int]] | None,
    explicit_palette: list[tuple[int, int, int]] | None,
    auto_match: tuple[list[tuple[int, int, int]], list[tuple[int, int, int]], str] | None,
    index: int,
    use_palette: bool = True,
) -> Image.Image:
    if not use_palette:
        return apply_effects(result, config.effects, frame_index=index)
    if explicit_palette is None and auto_match is None and config.mode == "stable" and palette is not None:
        result = _apply_palette_with_optional_dither(result, palette, config.effects)
    elif explicit_palette is None and auto_match is None:
        if dither_enabled(config.effects):
            frame_palette = build_global_palette([result], config.palette)
            result = apply_palette_dither(result, frame_palette, config.effects)
        else:
            result = quantize_per_frame(result, config.palette)
    result = apply_effects(result, config.effects, frame_index=index)
    if explicit_palette is not None:
        result = _apply_palette_with_optional_dither(result, explicit_palette, config.effects)
    elif auto_match is not None:
        source_colors, target_colors, sort_mode = auto_match
        result = apply_auto_match_palette(result, source_colors, target_colors, sort_mode)
    return result


def _use_pixel_space_dither(
    config: RenderConfig,
    auto_match: tuple[list[tuple[int, int, int]], list[tuple[int, int, int]], str] | None,
) -> bool:
    return auto_match is None and dither_enabled(config.effects) and config.effects.dither_space == "pixel"


def _apply_palette_with_optional_dither(
    image: Image.Image,
    palette: list[tuple[int, int, int]],
    effects: EffectsConfig,
) -> Image.Image:
    if dither_enabled(effects):
        return apply_palette_dither(image, palette, effects)
    return apply_palette(image, palette)


def render_video(input_path: str | Path, output_path: str | Path, config: RenderConfig) -> Path:
    input_file = Path(input_path)
    if not input_file.exists():
        raise VideoError(f"Input video does not exist: {input_file}")

    final_output = ensure_output_path(output_path, overwrite=config.output.overwrite)
    output_is_gif = is_gif_path(final_output)
    input_is_gif = is_gif_path(input_file)
    metadata = probe_video(input_file)
    frames = list(iter_frames(input_file))
    metadata = _metadata_with_decoded_timing(metadata, len(frames))
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
                mux_audio(input_file, silent_output, final_output, trim_start, metadata.duration)
            except VideoError:
                if config.output.audio_failure == "stop":
                    raise
                final_output.write_bytes(silent_output.read_bytes())
        else:
            final_output.write_bytes(silent_output.read_bytes())

    return final_output


def render_image(input_path: str | Path, output_path: str | Path, config: RenderConfig) -> Path:
    input_file = Path(input_path)
    if not input_file.exists():
        raise ImageError(f"Input image does not exist: {input_file}")
    if not is_image_path(input_file):
        raise ImageError(f"Unsupported image input format: {input_file.suffix}")

    final_output = ensure_output_path(output_path, overwrite=config.output.overwrite)
    image = load_static_image(input_file)
    alpha = image.getchannel("A").copy() if "A" in image.getbands() else None
    rgb_image = image.convert("RGB")
    image_config = replace(config, trim=None)
    source_metadata = VideoMetadata(width=image.width, height=image.height, fps=1.0, duration=None)
    frames, metadata = prepare_source_frames([rgb_image], image_config, source_metadata, encoder_safe=False)
    alpha = _prepare_image_alpha(alpha, image_config, source_metadata)
    processed = list(process_frames(frames, image_config, metadata))
    if not processed:
        raise ImageError(f"Could not render image: {input_file}")
    result = _apply_image_alpha(processed[0], alpha)
    save_static_image(result, final_output)
    return final_output


def _prepare_image_alpha(
    alpha: Image.Image | None,
    config: RenderConfig,
    metadata: VideoMetadata,
) -> Image.Image | None:
    if alpha is None:
        return None
    if config.crop is None:
        return alpha
    left = config.crop.x
    upper = config.crop.y
    right = min(metadata.width, left + config.crop.width)
    lower = min(metadata.height, upper + config.crop.height)
    if right <= left or lower <= upper:
        raise VideoError("Crop rectangle is outside the source frame")
    return alpha.crop((left, upper, right, lower))


def _apply_image_alpha(image: Image.Image, alpha: Image.Image | None) -> Image.Image:
    if alpha is None:
        return image
    result = image.convert("RGBA")
    if alpha.size != result.size:
        alpha = alpha.resize(result.size, Image.Resampling.NEAREST)
    result.putalpha(alpha)
    return result


def render_media(input_path: str | Path, output_path: str | Path, config: RenderConfig) -> Path:
    input_file = Path(input_path)
    if is_image_path(input_file):
        return render_image(input_file, output_path, config)
    if is_video_path(input_file):
        return render_video(input_file, output_path, config)
    raise MediaError(f"Unsupported input media type: {input_file.suffix or input_file}")
