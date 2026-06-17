from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from pixelator.errors import OutputError, VideoError
from pixelator.video import (
    VideoMetadata,
    ensure_output_path,
    extract_frame,
    frame_window,
    mux_audio,
    sample_frames,
    write_gif,
    write_video,
)


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


def test_extract_frame_returns_frame_at_requested_time(monkeypatch, tmp_path: Path):
    frames = [
        Image.new("RGB", (2, 2), (index, 0, 0))
        for index in range(5)
    ]

    monkeypatch.setattr(
        "pixelator.video.probe_video",
        lambda path: VideoMetadata(width=2, height=2, fps=2.0, duration=2.5),
    )
    monkeypatch.setattr("pixelator.video.iter_frames", lambda path: iter(frames))

    result = extract_frame(tmp_path / "clip.mp4", seconds=1.1)

    assert result.getpixel((0, 0)) == (2, 0, 0)


def test_write_video_preserves_non_macroblock_dimensions(monkeypatch, tmp_path: Path):
    calls = {}

    class FakeWriter:
        def send(self, data):
            pass

        def close(self):
            pass

    def fake_write_frames(path, **kwargs):
        calls["kwargs"] = kwargs
        return FakeWriter()

    monkeypatch.setattr("pixelator.video.imageio_ffmpeg.write_frames", fake_write_frames)

    write_video([Image.new("RGB", (360, 360), (0, 0, 0))], tmp_path / "out.mp4", VideoMetadata(360, 360, 24.0), "libx264")

    assert calls["kwargs"]["macro_block_size"] == 1


def test_write_video_includes_encoder_error_details(monkeypatch, tmp_path: Path):
    class FakeWriter:
        def __init__(self):
            self.started = False

        def send(self, data):
            if self.started:
                raise OSError("width not divisible by 2")
            self.started = True

        def close(self):
            pass

    monkeypatch.setattr("pixelator.video.imageio_ffmpeg.write_frames", lambda path, **kwargs: FakeWriter())

    with pytest.raises(VideoError, match="width not divisible by 2"):
        write_video([Image.new("RGB", (3, 2), (0, 0, 0))], tmp_path / "out.mp4", VideoMetadata(3, 2, 24.0), "libx264")


def test_write_gif_creates_animated_gif_with_frame_duration(tmp_path: Path):
    output = tmp_path / "out.gif"
    frames = [
        Image.new("RGB", (3, 2), (255, 0, 0)),
        Image.new("RGB", (3, 2), (0, 0, 255)),
    ]

    write_gif(frames, output, VideoMetadata(width=3, height=2, fps=12.0, duration=2 / 12.0))

    with Image.open(output) as gif:
        assert gif.format == "GIF"
        assert gif.n_frames == 2
        assert gif.info["duration"] == pytest.approx(83, abs=10)
        assert gif.info["loop"] == 0


def test_write_gif_rejects_empty_frames(tmp_path: Path):
    with pytest.raises(VideoError, match="no frames"):
        write_gif([], tmp_path / "out.gif", VideoMetadata(width=3, height=2, fps=12.0))


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


def test_mux_audio_applies_trim_arguments(monkeypatch, tmp_path: Path):
    calls = {}

    def fake_run(command, **kwargs):
        calls["command"] = command
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("pixelator.video.imageio_ffmpeg.get_ffmpeg_exe", lambda: "ffmpeg")
    monkeypatch.setattr("pixelator.video.subprocess.run", fake_run)

    mux_audio(
        tmp_path / "source.mp4",
        tmp_path / "silent.mp4",
        tmp_path / "output.mp4",
        start_seconds=1.25,
        duration_seconds=3.5,
    )

    command = calls["command"]
    assert "-ss" in command
    assert "1.25" in command
    assert "-t" in command
    assert "3.5" in command
