from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from pixelator.ai.asset_store import AssetStore
from pixelator.ai.dashscope_client import DashScopeClient
from pixelator.ai.prompt_builder import build_prompt
from pixelator.ai.types import AiGenerationRequest, DashScopeConfig, PromptResult


class AiGenerationWorker(QObject):
    logMessage = Signal(str)
    generationCompleted = Signal(object)
    generationFailed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        request: AiGenerationRequest,
        config: DashScopeConfig,
        output_dir: Path,
        prompt: PromptResult | None = None,
    ) -> None:
        super().__init__()
        self.request = request
        self.config = config
        self.output_dir = output_dir
        self.prompt = prompt

    @Slot()
    def run(self) -> None:
        try:
            prompt = self.prompt or build_prompt(self.request)
            self.logMessage.emit(f"Generating {self.request.count} AI asset(s) with {self.config.model}")
            if self.request.background == "transparent":
                self.logMessage.emit("Transparent output will use Aliyun VIAPI background removal.")
            images = DashScopeClient(self.config).generate(self.request, prompt)
            records = AssetStore(self.output_dir).save_assets(self.request, prompt, images)
            self.generationCompleted.emit(records)
        except Exception as exc:  # noqa: BLE001 - worker errors must be surfaced in the GUI.
            self.generationFailed.emit(str(exc))
        finally:
            self.finished.emit()
