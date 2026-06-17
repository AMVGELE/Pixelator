from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PIL import Image

from pixelator.layering.archive import write_layer_zip


@dataclass(frozen=True)
class LayerRequest:
    target_layers: int | None = None
    crop_alpha: bool = True
    zip_result: bool = True


class LayerBackend(Protocol):
    backend_name: str
    model_id: str

    def split(self, source_path: str | Path, output_path: str | Path, request: LayerRequest) -> None:
        ...


class MockLayerBackend:
    backend_name = "mock"
    model_id = "mock-rgba-single-layer"

    def split(self, source_path: str | Path, output_path: str | Path, request: LayerRequest) -> None:
        with Image.open(source_path) as image:
            rgba = image.convert("RGBA")

        write_layer_zip(
            source_path=source_path,
            source_image=rgba,
            layers=[rgba],
            output_path=output_path,
            backend=self.backend_name,
            model_id=self.model_id,
            crop_alpha=request.crop_alpha,
        )
