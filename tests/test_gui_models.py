from pathlib import Path

from pixelator.config import CropConfig, TrimConfig
from pixelator.gui.models import JobQueue, JobStatus, RenderSettings, VideoJob


def test_video_job_defaults_to_full_frame_and_full_trim(tmp_path: Path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fake")

    job = VideoJob(source_path=source)

    assert job.status == JobStatus.QUEUED
    assert job.crop is None
    assert job.trim is None
    assert job.progress == 0


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
        colors=16,
        keep_audio=False,
        overwrite=True,
        crop=CropConfig(x=1, y=2, width=30, height=40),
        trim=TrimConfig(start=0.5, end=2.0),
    )

    config = settings.to_config()

    assert config.mode == "fast"
    assert config.pixel.scale == 8
    assert config.palette.colors == 16
    assert config.output.keep_audio is False
    assert config.output.overwrite is True
    assert config.crop == settings.crop
    assert config.trim == settings.trim


def test_render_settings_default_output_format_is_mp4():
    settings = RenderSettings()

    assert settings.output_format == "mp4"
    assert settings.crt == "off"
    assert settings.vhs == "off"


def test_render_settings_create_config_with_custom_palette():
    settings = RenderSettings(custom_palette=["#000000", "#ffcc00"])

    config = settings.to_config()

    assert config.palette.strategy == "custom"
    assert config.palette.custom_colors == ["#000000", "#ffcc00"]


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
