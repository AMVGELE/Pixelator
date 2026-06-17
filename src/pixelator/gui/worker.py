from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from pixelator.gui.models import RenderSettings, VideoJob
from pixelator.pipeline import render_media


class RenderWorker(QObject):
    progressChanged = Signal(str, int)
    logMessage = Signal(str)
    jobCompleted = Signal(str, Path)
    jobFailed = Signal(str, str)
    finished = Signal()

    def __init__(self, job: VideoJob, output_path: Path, settings: RenderSettings) -> None:
        super().__init__()
        self.job = job
        self.output_path = output_path
        self.settings = settings

    @Slot()
    def run(self) -> None:
        try:
            self.progressChanged.emit(self.job.id, 0)
            self.logMessage.emit(f"Rendering {self.job.source_path.name}")
            output = render_media(self.job.source_path, self.output_path, self.settings.to_config())
            self.progressChanged.emit(self.job.id, 100)
            self.jobCompleted.emit(self.job.id, output)
        except Exception as exc:  # noqa: BLE001 - GUI must surface worker failures instead of crashing.
            self.jobFailed.emit(self.job.id, str(exc))
        finally:
            self.finished.emit()
