from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from pixelator.config import (
    CropConfig,
    EffectsConfig,
    ImageConfig,
    OutputConfig,
    PaletteConfig,
    PixelConfig,
    RenderConfig,
    TrimConfig,
)


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class VideoJob:
    source_path: Path
    id: str = ""
    output_path: Path | None = None
    status: JobStatus = JobStatus.QUEUED
    progress: int = 0
    error: str | None = None
    crop: CropConfig | None = None
    trim: TrimConfig | None = None
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None

    def __post_init__(self) -> None:
        if not self.id:
            object.__setattr__(self, "id", uuid4().hex)


@dataclass(frozen=True)
class RenderSettings:
    mode: str = "stable"
    pixel_scale: int = 4
    colors: int = 32
    brightness: float = 1.0
    sharpness: float = 1.2
    saturation: float = 1.1
    crt: str = "subtle"
    vhs: str = "light"
    keep_audio: bool = True
    overwrite: bool = False
    output_format: str = "mp4"
    crop: CropConfig | None = None
    trim: TrimConfig | None = None

    def to_config(self) -> RenderConfig:
        return RenderConfig(
            mode=self.mode,
            pixel=PixelConfig(scale=self.pixel_scale),
            palette=PaletteConfig(colors=self.colors),
            image=ImageConfig(
                brightness=self.brightness,
                sharpness=self.sharpness,
                saturation=self.saturation,
            ),
            effects=EffectsConfig(crt=self.crt, vhs=self.vhs),
            output=OutputConfig(keep_audio=self.keep_audio, overwrite=self.overwrite),
            crop=self.crop,
            trim=self.trim,
        )


class JobQueue:
    def __init__(self) -> None:
        self.jobs: list[VideoJob] = []

    def add(self, job: VideoJob) -> None:
        self.jobs.append(job)

    def update(self, job_id: str, **changes: object) -> VideoJob:
        for index, job in enumerate(self.jobs):
            if job.id == job_id:
                updated = replace(job, **changes)
                self.jobs[index] = updated
                return updated
        raise KeyError(job_id)

    def mark_running(self, job_id: str) -> VideoJob:
        return self.update(job_id, status=JobStatus.RUNNING, progress=0, error=None)

    def mark_completed(self, job_id: str, output_path: Path) -> VideoJob:
        return self.update(job_id, status=JobStatus.COMPLETED, progress=100, output_path=output_path, error=None)

    def mark_failed(self, job_id: str, error: str) -> VideoJob:
        return self.update(job_id, status=JobStatus.FAILED, error=error)

    def mark_progress(self, job_id: str, progress: int) -> VideoJob:
        clamped = max(0, min(100, progress))
        return self.update(job_id, progress=clamped)

    def mark_cancelled(self, job_id: str) -> VideoJob:
        return self.update(job_id, status=JobStatus.CANCELLED)

    def requeue_finished(self, job_id: str) -> VideoJob | None:
        job = next((candidate for candidate in self.jobs if candidate.id == job_id), None)
        if job is None or job.status not in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
            return None
        return self.update(job_id, status=JobStatus.QUEUED, progress=0, output_path=None, error=None)
