import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from pixelator.config import CropConfig
from pixelator.gui.main_window import MainWindow
from pixelator.video import VideoMetadata


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_scrubber_refreshes_preview_frame(monkeypatch, tmp_path: Path, qapp):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fake")
    requested_seconds = []

    monkeypatch.setattr(
        "pixelator.gui.main_window.probe_video",
        lambda path: VideoMetadata(width=64, height=48, fps=10.0, duration=10.0),
    )

    def fake_extract_frame(path, seconds=0.0):
        requested_seconds.append(seconds)
        return Image.new("RGB", (64, 48), (int(seconds) % 255, 0, 0))

    monkeypatch.setattr("pixelator.gui.main_window.extract_frame", fake_extract_frame)

    window = MainWindow()
    window.add_video_paths([source])
    window.scrubber_slider.setValue(500)

    assert requested_seconds[-1] == pytest.approx(5.0)
    window.close()


def test_default_gui_settings_export_full_duration(monkeypatch, tmp_path: Path, qapp):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fake")

    monkeypatch.setattr(
        "pixelator.gui.main_window.probe_video",
        lambda path: VideoMetadata(width=64, height=48, fps=10.0, duration=10.0),
    )
    monkeypatch.setattr(
        "pixelator.gui.main_window.extract_frame",
        lambda path, seconds=0.0: Image.new("RGB", (64, 48), (0, 0, 0)),
    )

    window = MainWindow()
    window.add_video_paths([source])
    job = window.queue.jobs[0]

    assert job.trim is None
    assert window._settings_for_job(job).trim is None
    assert window.trim_end_spin.value() == pytest.approx(10.0)
    window.close()


def test_crop_is_not_carried_to_uncropped_job(monkeypatch, tmp_path: Path, qapp):
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    first.write_bytes(b"fake")
    second.write_bytes(b"fake")

    monkeypatch.setattr(
        "pixelator.gui.main_window.probe_video",
        lambda path: VideoMetadata(width=64, height=48, fps=10.0, duration=10.0),
    )
    monkeypatch.setattr(
        "pixelator.gui.main_window.extract_frame",
        lambda path, seconds=0.0: Image.new("RGB", (64, 48), (0, 0, 0)),
    )

    window = MainWindow()
    window.add_video_paths([first, second])
    window.preview_widget.set_crop(CropConfig(x=8, y=6, width=20, height=16))
    window.queue_panel.list_widget.setCurrentRow(1)

    assert window.preview_widget.crop() == CropConfig(x=0, y=0, width=64, height=48)
    assert window.queue.jobs[1].crop is None
    window.close()


def test_numeric_crop_controls_update_job_crop(monkeypatch, tmp_path: Path, qapp):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fake")

    monkeypatch.setattr(
        "pixelator.gui.main_window.probe_video",
        lambda path: VideoMetadata(width=64, height=48, fps=10.0, duration=10.0),
    )
    monkeypatch.setattr(
        "pixelator.gui.main_window.extract_frame",
        lambda path, seconds=0.0: Image.new("RGB", (64, 48), (0, 0, 0)),
    )

    window = MainWindow()
    window.add_video_paths([source])
    window.crop_x_spin.setValue(10)
    window.crop_y_spin.setValue(4)
    window.crop_width_spin.setValue(24)
    window.crop_height_spin.setValue(18)

    assert window.queue.jobs[0].crop == CropConfig(x=10, y=4, width=24, height=18)
    assert window.crop_dimensions_label.text() == "Output: 24 x 18"
    window.close()
