from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from pixelator.errors import OutputError
from pixelator.video import VideoMetadata, ensure_output_path, frame_window, mux_audio, sample_frames


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


def test_frame_window_uses_trim_bounds():
    metadata = VideoMetadata(width=320, height=180, fps=10.0, duration=5.0)

    start, end = frame_window(metadata, start_seconds=1.2, end_seconds=3.7, frame_count=50)

    assert start == 12
    assert end == 37


def test_frame_window_clamps_to_available_frames():
    metadata = VideoMetadata(width=320, height=180, fps=10.0, duration=5.0)

    start, end = frame_window(metadata, start_seconds=4.5, end_seconds=None, frame_count=50)

    assert start == 45
    assert end == 50


def test_mux_audio_decodes_ffmpeg_output_with_replacement(monkeypatch, tmp_path: Path):
    calls = {}

    def fake_run(command, **kwargs):
        calls["command"] = command
        calls["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("pixelator.video.imageio_ffmpeg.get_ffmpeg_exe", lambda: "ffmpeg")
    monkeypatch.setattr("pixelator.video.subprocess.run", fake_run)

    mux_audio(tmp_path / "源.mp4", tmp_path / "silent.mp4", tmp_path / "输出.mp4")

    assert calls["kwargs"]["encoding"] == "utf-8"
    assert calls["kwargs"]["errors"] == "replace"
