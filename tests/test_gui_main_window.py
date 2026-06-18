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
    assert "*.png" in captured["filter"]
    window.close()


def test_add_image_path_loads_preview_and_disables_timeline(tmp_path: Path, qapp):
    source = tmp_path / "texture.png"
    Image.new("RGB", (7, 5), (255, 0, 0)).save(source)

    window = MainWindow()
    window.add_media_paths([source])

    job = window.queue.jobs[0]
    assert job.is_image
    assert job.width == 7
    assert job.height == 5
    assert job.trim is None
    assert window.preview_widget.source_size() == (7, 5)
    assert not window.trim_start_spin.isEnabled()
    assert not window.trim_end_spin.isEnabled()
    assert not window.scrubber_slider.isEnabled()
    window.close()


def test_add_image_folder_batches_supported_images(tmp_path: Path, qapp):
    first = tmp_path / "b.png"
    second = tmp_path / "a.jpg"
    Image.new("RGB", (2, 2), (255, 0, 0)).save(first)
    Image.new("RGB", (3, 3), (0, 255, 0)).save(second)
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")

    window = MainWindow()
    window.add_media_paths([tmp_path])

    assert [job.source_path.name for job in window.queue.jobs] == ["a.jpg", "b.png"]
    assert all(job.is_image for job in window.queue.jobs)
    window.close()


def test_choose_folder_adds_image_directory(monkeypatch, tmp_path: Path, qapp):
    source = tmp_path / "texture.png"
    Image.new("RGB", (2, 2), (255, 0, 0)).save(source)
    window = MainWindow()

    monkeypatch.setattr("pixelator.gui.main_window.QFileDialog.getExistingDirectory", lambda *args: str(tmp_path))

    window._choose_folder()

    assert len(window.queue.jobs) == 1
    assert window.queue.jobs[0].is_image
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


def test_output_path_for_image_job_uses_png(tmp_path: Path, qapp):
    source = tmp_path / "texture.png"
    job = VideoJob(source_path=source, media_type="image")
    window = MainWindow()
    window.settings_panel.output_folder_edit.setText(str(tmp_path))
    window.settings_panel.output_format_combo.setCurrentText("GIF")

    assert window._output_path_for_job(job) == tmp_path / "texture-pixelated.png"
    assert window._settings_for_job(job).trim is None
    assert window._settings_for_job(job).keep_audio is False
    window.close()


def test_uncustomized_jobs_share_global_render_settings(tmp_path: Path, qapp):
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    Image.new("RGB", (4, 4), (255, 0, 0)).save(first)
    Image.new("RGB", (4, 4), (0, 0, 255)).save(second)
    window = MainWindow()
    window.add_media_paths([first, second])

    window.settings_panel.pixel_scale_spin.setValue(8)

    assert window.queue.jobs[0].settings_override is None
    assert window.queue.jobs[1].settings_override is None
    assert window._settings_for_job(window.queue.jobs[0]).pixel_scale == 8
    assert window._settings_for_job(window.queue.jobs[1]).pixel_scale == 8
    window.close()


def test_customize_this_item_isolates_render_settings(tmp_path: Path, qapp):
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    Image.new("RGB", (4, 4), (255, 0, 0)).save(first)
    Image.new("RGB", (4, 4), (0, 0, 255)).save(second)
    window = MainWindow()
    window.add_media_paths([first, second])

    window._customize_selected_job_settings()
    window.settings_panel.pixel_scale_spin.setValue(9)

    assert window.queue.jobs[0].settings_override is not None
    assert window.queue.jobs[0].settings_override.pixel_scale == 9
    assert window._settings_for_job(window.queue.jobs[1]).pixel_scale == 4

    window._use_global_settings_for_selected_job()

    assert window.queue.jobs[0].settings_override is None
    assert window.settings_panel.settings().pixel_scale == 4
    window.close()


def test_shared_palette_applies_to_all_jobs_by_default(tmp_path: Path, qapp):
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    Image.new("RGB", (4, 4), (255, 0, 0)).save(first)
    Image.new("RGB", (4, 4), (0, 0, 255)).save(second)
    window = MainWindow()
    window.add_media_paths([first, second])

    window.palette_panel.set_source_and_render_colors(["#000000", "#ffffff"])

    assert window._settings_for_job(window.queue.jobs[0]).custom_palette == ["#000000", "#ffffff"]
    assert window._settings_for_job(window.queue.jobs[1]).custom_palette == ["#000000", "#ffffff"]
    window.close()


def test_per_item_palette_snapshot_does_not_pollute_shared_palette(tmp_path: Path, qapp):
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    Image.new("RGB", (4, 4), (255, 0, 0)).save(first)
    Image.new("RGB", (4, 4), (0, 0, 255)).save(second)
    window = MainWindow()
    window.add_media_paths([first, second])
    window.palette_panel.set_source_and_render_colors(["#000000", "#ffffff"])

    window.palette_panel.palette_mode_combo.setCurrentText("Per Item Palette")
    window.palette_panel.set_colors(["#ff0000", "#00ff00"])
    window.queue_panel.list_widget.setCurrentRow(1)

    assert window.palette_panel.palette_mode() == "shared"
    assert window.palette_panel.colors() == ["#000000", "#ffffff"]

    window.queue_panel.list_widget.setCurrentRow(0)

    assert window.palette_panel.palette_mode() == "item"
    assert window.palette_panel.colors() == ["#ff0000", "#00ff00"]
    window.close()


def test_current_crop_palette_extract_uses_cropped_preview_region(tmp_path: Path, qapp):
    source = tmp_path / "texture.png"
    image = Image.new("RGB", (4, 2))
    image.putdata([(255, 0, 0)] * 4 + [(0, 0, 255)] * 4)
    image.save(source)
    window = MainWindow()
    window.add_media_paths([source])
    window.preview_widget.set_crop(CropConfig(x=0, y=1, width=4, height=1))

    window._extract_palette_from_current_frame(2, "dominant", "crop")

    assert window.palette_panel.source_colors() == ["#0000ff"]
    assert window.palette_panel.colors() == ["#0000ff"]
    window.close()


def test_image_crop_controls_preserve_odd_dimensions(tmp_path: Path, qapp):
    source = tmp_path / "texture.png"
    Image.new("RGB", (7, 5), (255, 0, 0)).save(source)

    window = MainWindow()
    window.add_media_paths([source])
    window.crop_width_spin.setValue(3)
    window.crop_height_spin.setValue(3)

    assert window.queue.jobs[0].crop == CropConfig(x=0, y=0, width=3, height=3)
    assert window.crop_dimensions_label.text() == "Output: 3 x 3"
    window.close()


def test_right_side_splits_render_and_palette_tabs(qapp):
    window = MainWindow()

    assert window.right_tabs.count() == 4
    assert window.right_tabs.tabText(0) == "Render"
    assert window.right_tabs.tabText(1) == "Palette"
    assert window.right_tabs.tabText(2) == "AI Assets"
    assert window.right_tabs.tabText(3) == "Qwen Lab"
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
    window._extract_palette_from_current_frame(2, "dominant", "full")

    assert window.palette_panel.colors() == ["#ff0000", "#00ff00"]
    settings = window._settings_for_job(window.queue.jobs[0])
    assert settings.custom_palette == ["#ff0000", "#00ff00"]
    assert settings.source_palette == ["#ff0000", "#00ff00"]
    assert settings.to_config().palette.strategy == "auto_match"
    window.close()


def test_main_window_current_frame_extract_without_preview_does_not_change_palette(qapp):
    window = MainWindow()

    window._extract_palette_from_current_frame(2, "dominant", "full")

    assert window.palette_panel.colors() == []
    assert window.palette_panel.status_label.text() == "No current frame to extract"
    window.close()
