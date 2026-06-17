from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from pixelator.layering.types import JobStatus
from pixelator.layering_service.backends import LayerBackend, LayerRequest


@dataclass
class LayerJob:
    id: str
    source_path: Path
    artifact_path: Path
    status: JobStatus = JobStatus.QUEUED
    error: str | None = None


class JobStore:
    def __init__(self, work_dir: str | Path, backend: LayerBackend) -> None:
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.backend = backend
        self._jobs: dict[str, LayerJob] = {}

    def create_and_run(self, source_path: str | Path, request: LayerRequest) -> LayerJob:
        job_id = uuid.uuid4().hex
        job = LayerJob(
            id=job_id,
            source_path=Path(source_path),
            artifact_path=self.work_dir / f"{job_id}.zip",
        )
        self._jobs[job.id] = job
        job.status = JobStatus.RUNNING

        try:
            self.backend.split(job.source_path, job.artifact_path, request)
        except Exception as exc:  # noqa: BLE001 - job state should retain backend failure text.
            job.status = JobStatus.FAILED
            job.error = str(exc)
        else:
            job.status = JobStatus.SUCCEEDED

        return job

    def get(self, job_id: str) -> LayerJob | None:
        return self._jobs.get(job_id)
