from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import imageio_ffmpeg
import numpy as np
from PIL import Image

from pixelator.errors import OutputError, VideoError


@dataclass(frozen=True)
class VideoMetadata:
    width: int
    height: int
    fps: float
    duration: float | None = None

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height


def ensure_output_path(path: str | Path, overwrite: bool) -> Path:
    output = Path(path)
    if output.exists() and not overwrite:
        raise OutputError(f"Output file already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    return output


def probe_video(path: str | Path) -> VideoMetadata:
    reader = imageio_ffmpeg.read_frames(str(path), pix_fmt="rgb24")
    try:
        metadata = next(reader)
    except Exception as exc:
        raise VideoError(f"Could not probe video: {path}") from exc
    finally:
        reader.close()
    size = metadata.get("size")
    fps = metadata.get("fps")
    duration = metadata.get("duration")
    if not size or not fps:
        raise VideoError(f"Video metadata is incomplete: {path}")
    return VideoMetadata(width=int(size[0]), height=int(size[1]), fps=float(fps), duration=duration)


def iter_frames(path: str | Path) -> Iterator[Image.Image]:
    reader = imageio_ffmpeg.read_frames(str(path), pix_fmt="rgb24")
    try:
        metadata = next(reader)
        width, height = metadata["size"]
        for frame_bytes in reader:
            yield Image.frombytes("RGB", (width, height), frame_bytes)
    except Exception as exc:
        raise VideoError(f"Could not decode frames: {path}") from exc
    finally:
        reader.close()


def write_video(frames: Iterable[Image.Image], output: str | Path, metadata: VideoMetadata, codec: str) -> None:
    writer = imageio_ffmpeg.write_frames(
        str(output),
        size=metadata.size,
        fps=metadata.fps,
        codec=codec,
        pix_fmt_in="rgb24",
        pix_fmt_out="yuv420p",
    )
    try:
        writer.send(None)
        for frame in frames:
            array = np.asarray(frame.convert("RGB"), dtype=np.uint8)
            writer.send(array.tobytes())
    except Exception as exc:
        raise VideoError(f"Could not encode video: {output}") from exc
    finally:
        writer.close()


def frame_window(
    metadata: VideoMetadata,
    start_seconds: float = 0.0,
    end_seconds: float | None = None,
    frame_count: int | None = None,
) -> tuple[int, int]:
    total = frame_count
    if total is None and metadata.duration is not None:
        total = max(0, round(metadata.duration * metadata.fps))
    start_index = max(0, int(start_seconds * metadata.fps))
    if end_seconds is None:
        end_index = total if total is not None else start_index
    else:
        end_index = max(start_index, int(end_seconds * metadata.fps))
    if total is not None:
        start_index = min(start_index, total)
        end_index = min(end_index, total)
    return start_index, end_index


def mux_audio(
    source_video: str | Path,
    silent_video: str | Path,
    output: str | Path,
    start_seconds: float = 0.0,
    duration_seconds: float | None = None,
) -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    source_input: list[str] = []
    if start_seconds > 0:
        source_input.extend(["-ss", str(start_seconds)])
    if duration_seconds is not None:
        source_input.extend(["-t", str(duration_seconds)])
    source_input.extend(["-i", str(source_video)])
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(silent_video),
        *source_input,
        "-map",
        "0:v:0",
        "-map",
        "1:a?",
        "-c:v",
        "copy",
        "-c:a",
        "copy",
        "-shortest",
        str(output),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise VideoError(f"Could not mux audio into output: {completed.stderr.strip()}")


def sample_frames(frames: list[Image.Image], sample_count: int) -> list[Image.Image]:
    if not frames:
        return []
    if sample_count >= len(frames):
        return list(frames)
    indices = np.linspace(0, len(frames) - 1, sample_count).round().astype(int)
    return [frames[index] for index in indices]
