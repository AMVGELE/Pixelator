from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from pixelator.ai.super_resolution import SuperResolutionClient, SuperResolutionOptions


class SuperResolutionWorker(QObject):
    logMessage = Signal(str)
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, options: SuperResolutionOptions, output_dir: Path) -> None:
        super().__init__()
        self.options = options
        self.output_dir = output_dir

    @Slot()
    def run(self) -> None:
        try:
            self.logMessage.emit(
                f"Running super resolution x{self.options.upscale_factor} for {self.options.source_path.name}"
            )
            result = SuperResolutionClient().upscale(self.options, self.output_dir)
            self.completed.emit(result)
        except Exception as exc:  # noqa: BLE001 - worker errors must be surfaced in the GUI.
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()
