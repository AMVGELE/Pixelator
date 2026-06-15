import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from pixelator.config import CropConfig
from pixelator.gui.models import VideoJob
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


def test_numeric_crop_controls_snap_to_even_output_dimensions(monkeypatch, tmp_path: Path, qapp):
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
    window.crop_width_spin.setValue(25)
    window.crop_height_spin.setValue(19)

    assert window.queue.jobs[0].crop == CropConfig(x=0, y=0, width=24, height=18)
    assert window.crop_dimensions_label.text() == "Output: 24 x 18"
    window.close()


def test_crop_drag_update_does_not_reload_preview(monkeypatch, tmp_path: Path, qapp):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fake")
    requested_seconds = []

    monkeypatch.setattr(
        "pixelator.gui.main_window.probe_video",
        lambda path: VideoMetadata(width=64, height=48, fps=10.0, duration=10.0),
    )

    def fake_extract_frame(path, seconds=0.0):
        requested_seconds.append(seconds)
        return Image.new("RGB", (64, 48), (0, 0, 0))

    monkeypatch.setattr("pixelator.gui.main_window.extract_frame", fake_extract_frame)

    window = MainWindow()
    window.add_video_paths([source])
    assert requested_seconds == [0.0]

    window._on_crop_changed(CropConfig(x=4, y=6, width=24, height=18))

    assert requested_seconds == [0.0]
    assert window.queue.jobs[0].crop == CropConfig(x=4, y=6, width=24, height=18)
    assert window.crop_dimensions_label.text() == "Output: 24 x 18"
    window.close()


def test_start_requeues_selected_completed_job(monkeypatch, tmp_path: Path, qapp):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fake")
    window = MainWindow()
    job = VideoJob(source_path=source, duration=10.0, width=64, height=48, fps=10.0)
    window.queue.add(job)
    window._refresh_queue()
    window.queue_panel.list_widget.setCurrentRow(0)
    window.queue.mark_completed(job.id, tmp_path / "clip-pixelated.mp4")
    window._refresh_queue()
    calls = []

    monkeypatch.setattr(window, "_run_next_job", lambda: calls.append("run"))

    window._start_queue()

    assert calls == ["run"]
    assert window.queue.jobs[0].status.value == "queued"
    assert window.queue.jobs[0].progress == 0
    assert window.queue.jobs[0].output_path is None
    window.close()


def test_file_chooser_includes_gif_filter(monkeypatch, qapp):
    captured = {}
    window = MainWindow()

    def fake_get_open_file_names(parent, title, directory, file_filter):
        captured["filter"] = file_filter
        return [], ""

    monkeypatch.setattr("pixelator.gui.main_window.QFileDialog.getOpenFileNames", fake_get_open_file_names)

    window._choose_files()

    assert "*.gif" in captured["filter"]
    window.close()


def test_output_path_uses_selected_output_format(tmp_path: Path, qapp):
    source = tmp_path / "clip.mp4"
    job = VideoJob(source_path=source)
    window = MainWindow()
    window.settings_panel.output_folder_edit.setText(str(tmp_path))

    assert window._output_path_for_job(job) == tmp_path / "clip-pixelated.mp4"

    window.settings_panel.output_format_combo.setCurrentText("GIF")

    assert window._output_path_for_job(job) == tmp_path / "clip-pixelated.gif"
    window.close()


def test_right_side_splits_render_and_palette_tabs(qapp):
    window = MainWindow()

    assert window.right_tabs.count() == 2
    assert window.right_tabs.tabText(0) == "Render"
    assert window.right_tabs.tabText(1) == "Palette"
    window.close()


def test_main_window_carries_custom_palette_to_render_settings(tmp_path: Path, qapp):
    source = tmp_path / "clip.mp4"
    job = VideoJob(source_path=source)
    window = MainWindow()
    window.palette_panel.set_colors(["#000000", "#ffcc00"])

    settings = window._settings_for_job(job)

    assert settings.custom_palette == ["#000000", "#ffcc00"]
    assert settings.to_config().palette.strategy == "custom"
    window.close()


def test_main_window_extracts_palette_from_current_preview_frame(monkeypatch, tmp_path: Path, qapp):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fake")
    frame = Image.new("RGB", (6, 1))
    frame.putdata([(255, 0, 0)] * 4 + [(0, 255, 0)] * 2)

    monkeypatch.setattr(
        "pixelator.gui.main_window.probe_video",
        lambda path: VideoMetadata(width=6, height=1, fps=10.0, duration=1.0),
    )
    monkeypatch.setattr("pixelator.gui.main_window.extract_frame", lambda path, seconds=0.0: frame)

    window = MainWindow()
    window.add_video_paths([source])
    window._extract_palette_from_current_frame(2)

    assert window.palette_panel.colors() == ["#ff0000", "#00ff00"]
    settings = window._settings_for_job(window.queue.jobs[0])
    assert settings.custom_palette == ["#ff0000", "#00ff00"]
    assert settings.source_palette == ["#ff0000", "#00ff00"]
    assert settings.to_config().palette.strategy == "auto_match"
    window.close()


def test_main_window_current_frame_extract_without_preview_does_not_change_palette(qapp):
    window = MainWindow()

    window._extract_palette_from_current_frame(2)

    assert window.palette_panel.colors() == []
    assert window.palette_panel.status_label.text() == "No current frame to extract"
    window.close()
