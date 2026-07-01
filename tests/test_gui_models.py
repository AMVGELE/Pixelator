from pathlib import Path

from pixelator.config import CropConfig, TrimConfig
from pixelator.gui.models import JobQueue, JobStatus, PaletteSnapshot, RenderSettings, VideoJob


def test_video_job_defaults_to_full_frame_and_full_trim(tmp_path: Path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fake")

    job = VideoJob(source_path=source)

    assert job.status == JobStatus.QUEUED
    assert job.crop is None
    assert job.trim is None
    assert job.progress == 0
    assert job.media_type == "video"
    assert not job.is_image
    assert job.settings_override is None
    assert job.palette_mode == "shared"
    assert job.palette_snapshot is None


def test_image_job_marks_media_type(tmp_path: Path):
    job = VideoJob(source_path=tmp_path / "texture.png", media_type="image")

    assert job.is_image


def test_palette_snapshot_carries_source_render_and_automatch_state():
    snapshot = PaletteSnapshot(
        source_colors=["#ff0000", "#0000ff"],
        render_colors=["#1a1c2c", "#f4f4f4"],
        auto_match=False,
        match_sort="brightness",
    )

    assert snapshot.source_colors == ["#ff0000", "#0000ff"]
    assert snapshot.render_colors == ["#1a1c2c", "#f4f4f4"]
    assert snapshot.auto_match is False
    assert snapshot.match_sort == "brightness"
    assert snapshot.has_render_palette()


def test_job_queue_tracks_status_transitions(tmp_path: Path):
    queue = JobQueue()
    job = VideoJob(source_path=tmp_path / "clip.mp4")

    queue.add(job)
    queue.mark_running(job.id)
    queue.mark_completed(job.id, tmp_path / "out.mp4")

    assert queue.jobs[0].status == JobStatus.COMPLETED
    assert queue.jobs[0].progress == 100
    assert queue.jobs[0].output_path == tmp_path / "out.mp4"


def test_job_queue_tracks_progress_and_cancellation(tmp_path: Path):
    queue = JobQueue()
    job = VideoJob(source_path=tmp_path / "clip.mp4")

    queue.add(job)
    queue.mark_running(job.id)
    queue.mark_progress(job.id, 47)
    queue.mark_cancelled(job.id)

    assert queue.jobs[0].status == JobStatus.CANCELLED
    assert queue.jobs[0].progress == 47


def test_job_queue_requeues_selected_finished_job(tmp_path: Path):
    queue = JobQueue()
    job = VideoJob(source_path=tmp_path / "clip.mp4")
    queue.add(job)
    queue.mark_running(job.id)
    queue.mark_completed(job.id, tmp_path / "out.mp4")

    requeued = queue.requeue_finished(job.id)

    assert requeued is not None
    assert queue.jobs[0].status == JobStatus.QUEUED
    assert queue.jobs[0].progress == 0
    assert queue.jobs[0].output_path is None
    assert queue.jobs[0].error is None


def test_job_queue_does_not_requeue_running_job(tmp_path: Path):
    queue = JobQueue()
    job = VideoJob(source_path=tmp_path / "clip.mp4")
    queue.add(job)
    queue.mark_running(job.id)

    assert queue.requeue_finished(job.id) is None
    assert queue.jobs[0].status == JobStatus.RUNNING


def test_render_settings_create_config_with_crop_and_trim():
    settings = RenderSettings(
        mode="fast",
        pixel_scale=8,
        target_width=1280,
        colors=16,
        keep_audio=False,
        overwrite=True,
        crop=CropConfig(x=1, y=2, width=30, height=40),
        trim=TrimConfig(start=0.5, end=2.0),
    )

    config = settings.to_config()

    assert config.mode == "fast"
    assert config.pixel.scale == 8
    assert config.pixel.target_width == 1280
    assert config.palette.colors == 16
    assert config.output.keep_audio is False
    assert config.output.overwrite is True
    assert config.crop == settings.crop
    assert config.trim == settings.trim


def test_render_settings_default_output_format_is_mp4():
    settings = RenderSettings()

    assert settings.style_filter == "clean_pixel"
    assert settings.palette_mode == "fixed"
    assert settings.output_format == "mp4"
    assert settings.target_width is None
    assert settings.crt == "off"
    assert settings.vhs == "off"
    assert settings.dither == "off"
    assert settings.dither_ramp == "nearest"
    assert settings.dither_space == "output"


def test_render_settings_create_config_with_dither_effect():
    settings = RenderSettings(
        dither="diamond",
        dither_ramp="tone",
        dither_space="pixel",
        dither_strength=0.65,
        dither_scale=5,
        dither_angle=45.0,
    )

    config = settings.to_config()

    assert config.effects.dither == "diamond"
    assert config.effects.dither_ramp == "tone"
    assert config.effects.dither_space == "pixel"
    assert config.effects.dither_strength == 0.65
    assert config.effects.dither_scale == 5
    assert config.effects.dither_angle == 45.0


def test_render_settings_create_config_with_custom_palette():
    settings = RenderSettings(custom_palette=["#000000", "#ffcc00"])

    config = settings.to_config()

    assert config.palette.strategy == "custom"
    assert config.palette.custom_colors == ["#000000", "#ffcc00"]


def test_render_settings_original_colors_skip_custom_palette():
    settings = RenderSettings(
        palette_strategy="original",
        custom_palette=["#000000", "#ffcc00"],
        source_palette=["#ff0000", "#0000ff"],
    )

    config = settings.to_config()

    assert config.palette.strategy == "original"
    assert config.palette.custom_colors is None
    assert config.palette.source_colors is None


def test_render_settings_create_config_with_auto_match_palette():
    settings = RenderSettings(
        custom_palette=["#00ff00", "#ffff00"],
        source_palette=["#ff0000", "#0000ff"],
        palette_strategy="auto_match",
        palette_match_sort="original",
    )

    config = settings.to_config()

    assert config.palette.strategy == "auto_match"
    assert config.palette.custom_colors == ["#00ff00", "#ffff00"]
    assert config.palette.source_colors == ["#ff0000", "#0000ff"]
    assert config.palette.match_sort == "original"
