from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from PIL import Image

from pixelator.layering.archive import write_layer_zip
from pixelator.layering.types import LayerManifest


@dataclass(frozen=True)
class LayerRequest:
    target_layers: int | None = None
    crop_alpha: bool = True
    zip_result: bool = True


class LayerBackend(Protocol):
    backend_name: str
    model_id: str

    def split(self, source_path: str | Path, output_path: str | Path, request: LayerRequest) -> LayerManifest:
        ...


class MockLayerBackend:
    backend_name = "mock"
    model_id = "mock-rgba-single-layer"

    def split(self, source_path: str | Path, output_path: str | Path, request: LayerRequest) -> LayerManifest:
        with Image.open(source_path) as image:
            rgba = image.convert("RGBA")

        return write_layer_zip(
            source_path=source_path,
            source_image=rgba,
            layers=[rgba],
            output_path=output_path,
            backend=self.backend_name,
            model_id=self.model_id,
            crop_alpha=request.crop_alpha,
        )


class SelfHostedQwenLayerBackend:
    backend_name = "aliyun-self-hosted"
    model_id = "Qwen/Qwen-Image-Layered"

    def __init__(
        self,
        pipeline_factory: Callable[[], Any] | None = None,
        layers: int = 4,
        resolution: int = 640,
        steps: int = 50,
        true_cfg_scale: float = 4.0,
    ) -> None:
        self.pipeline_factory = pipeline_factory or self._default_pipeline_factory
        self.default_layers = layers
        self.resolution = resolution
        self.steps = steps
        self.true_cfg_scale = true_cfg_scale
        self._pipeline: Any | None = None

    @property
    def pipeline(self) -> Any:
        if self._pipeline is None:
            self._pipeline = self.pipeline_factory()
        return self._pipeline

    def split(self, source_path: str | Path, output_path: str | Path, request: LayerRequest) -> LayerManifest:
        with Image.open(source_path) as image:
            rgba = image.convert("RGBA")

        output = self.pipeline(
            image=rgba,
            true_cfg_scale=self.true_cfg_scale,
            negative_prompt=" ",
            num_inference_steps=self.steps,
            num_images_per_prompt=1,
            layers=request.target_layers or self.default_layers,
            resolution=self.resolution,
            cfg_normalize=True,
            use_en_prompt=True,
        )
        layers = self._extract_layers(output)

        return write_layer_zip(
            source_path=source_path,
            source_image=rgba,
            layers=layers,
            output_path=output_path,
            backend=self.backend_name,
            model_id=self.model_id,
            crop_alpha=request.crop_alpha,
        )

    @staticmethod
    def _extract_layers(output: Any) -> list[Image.Image]:
        images = output.images
        first = images[0]
        if isinstance(first, (list, tuple)):
            return [layer.convert("RGBA") for layer in first]

        return [layer.convert("RGBA") for layer in images]

    @classmethod
    def _default_pipeline_factory(cls) -> Any:
        try:
            import torch
            from diffusers import DiffusionPipeline
        except ImportError as exc:
            raise RuntimeError(
                "SelfHostedQwenLayerBackend requires torch and diffusers in the cloud GPU image. "
                "Install CUDA PyTorch, Diffusers, Transformers, Accelerate, and Pillow there; "
                "the default Pixelator desktop package does not include these heavyweight dependencies."
            ) from exc

        pipeline = DiffusionPipeline.from_pretrained(cls.model_id, torch_dtype=torch.bfloat16)
        if torch.cuda.is_available():
            pipeline = pipeline.to("cuda")
        return pipeline
