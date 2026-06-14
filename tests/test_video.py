from pathlib import Path

import pytest
from PIL import Image

from pixelator.errors import OutputError
from pixelator.video import VideoMetadata, ensure_output_path, sample_frames


def test_ensure_output_path_rejects_existing_file_without_overwrite(tmp_path: Path):
    output = tmp_path / "out.mp4"
    output.write_bytes(b"existing")

    with pytest.raises(OutputError, match="already exists"):
        ensure_output_path(output, overwrite=False)


def test_ensure_output_path_allows_existing_file_with_overwrite(tmp_path: Path):
    output = tmp_path / "out.mp4"
    output.write_bytes(b"existing")

    assert ensure_output_path(output, overwrite=True) == output


def test_sample_frames_evenly_samples_sequence():
    frames = [Image.new("RGB", (2, 2), (index, index, index)) for index in range(10)]

    result = sample_frames(frames, sample_count=4)

    assert len(result) == 4
    assert result[0].getpixel((0, 0)) == (0, 0, 0)
    assert result[-1].getpixel((0, 0)) == (9, 9, 9)


def test_video_metadata_frame_size():
    metadata = VideoMetadata(width=320, height=180, fps=24.0, duration=None)

    assert metadata.size == (320, 180)
