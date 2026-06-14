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
    iter_frames,
    mux_audio,
    probe_video,
    sample_frames,
    write_video,
)


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

    with TemporaryDirectory(prefix="pixelator-") as temp_dir:
        silent_output = Path(temp_dir) / f"{final_output.stem}.silent.mp4"
        processed = process_frames(frames, config, metadata)
        write_video(processed, silent_output, metadata, codec=config.output.codec)
        if config.output.keep_audio:
            try:
                mux_audio(input_file, silent_output, final_output)
            except VideoError:
                if config.output.audio_failure == "stop":
                    raise
                final_output.write_bytes(silent_output.read_bytes())
        else:
            final_output.write_bytes(silent_output.read_bytes())

    return final_output
