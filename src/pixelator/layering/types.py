from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    AUTH_FAILED = "AUTH_FAILED"
    INPUT_TOO_LARGE = "INPUT_TOO_LARGE"
    UNSUPPORTED_IMAGE = "UNSUPPORTED_IMAGE"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    JOB_TIMEOUT = "JOB_TIMEOUT"
    JOB_FAILED = "JOB_FAILED"
    ARTIFACT_INVALID = "ARTIFACT_INVALID"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    UNKNOWN = "unknown"


class LayeringError(Exception):
    def __init__(self, code: ErrorCode, message: str, request_id: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.request_id = request_id


@dataclass(frozen=True)
class SourceInfo:
    file_name: str
    width: int
    height: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {"file_name": self.file_name, "width": self.width, "height": self.height, "sha256": self.sha256}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceInfo":
        return cls(
            file_name=_require_str(data, "file_name"),
            width=_require_positive_int(data, "width"),
            height=_require_positive_int(data, "height"),
            sha256=_require_str(data, "sha256"),
        )


@dataclass(frozen=True)
class ModelInfo:
    provider: str
    backend: str
    model_id: str

    def to_dict(self) -> dict[str, Any]:
        return {"provider": self.provider, "backend": self.backend, "model_id": self.model_id}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelInfo":
        return cls(
            provider=_require_str(data, "provider"),
            backend=_require_str(data, "backend"),
            model_id=_require_str(data, "model_id"),
        )


@dataclass(frozen=True)
class LayerInfo:
    id: str
    name: str
    file: str
    order: int
    bbox: tuple[int, int, int, int]
    width: int
    height: int
    opacity: float = 1.0
    blend_mode: str = "normal"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "file": self.file,
            "order": self.order,
            "bbox": list(self.bbox),
            "width": self.width,
            "height": self.height,
            "opacity": self.opacity,
            "blend_mode": self.blend_mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LayerInfo":
        bbox_value = data.get("bbox")
        if not isinstance(bbox_value, list) or len(bbox_value) != 4 or not all(isinstance(value, int) for value in bbox_value):
            raise LayeringError(ErrorCode.ARTIFACT_INVALID, "layer bbox must contain four integers")
        return cls(
            id=_require_str(data, "id"),
            name=_require_str(data, "name"),
            file=_require_str(data, "file"),
            order=_require_non_negative_int(data, "order"),
            bbox=(bbox_value[0], bbox_value[1], bbox_value[2], bbox_value[3]),
            width=_require_positive_int(data, "width"),
            height=_require_positive_int(data, "height"),
            opacity=float(data.get("opacity", 1.0)),
            blend_mode=str(data.get("blend_mode", "normal")),
        )


@dataclass(frozen=True)
class PreviewInfo:
    file: str

    def to_dict(self) -> dict[str, Any]:
        return {"file": self.file}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PreviewInfo":
        return cls(file=_require_str(data, "file"))


@dataclass(frozen=True)
class LayerManifest:
    source: SourceInfo
    model: ModelInfo
    layers: list[LayerInfo]
    preview: PreviewInfo
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "source": self.source.to_dict(),
            "model": self.model.to_dict(),
            "layers": [layer.to_dict() for layer in sorted(self.layers, key=lambda item: item.order)],
            "preview": self.preview.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LayerManifest":
        version = data.get("schema_version")
        if version != 1:
            raise LayeringError(ErrorCode.ARTIFACT_INVALID, "manifest schema_version must be 1")
        manifest = cls(
            schema_version=version,
            source=SourceInfo.from_dict(_require_dict(data, "source")),
            model=ModelInfo.from_dict(_require_dict(data, "model")),
            layers=[LayerInfo.from_dict(item) for item in _require_list(data, "layers")],
            preview=PreviewInfo.from_dict(_require_dict(data, "preview")),
        )
        manifest.validate()
        return manifest

    def validate(self) -> None:
        if self.schema_version != 1:
            raise LayeringError(ErrorCode.ARTIFACT_INVALID, "manifest schema_version must be 1")
        if not self.layers:
            raise LayeringError(ErrorCode.ARTIFACT_INVALID, "manifest must contain at least one layer")
        seen_files: set[str] = set()
        for layer in self.layers:
            if layer.file in seen_files:
                raise LayeringError(ErrorCode.ARTIFACT_INVALID, f"duplicate layer file: {layer.file}")
            seen_files.add(layer.file)


def _require_dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise LayeringError(ErrorCode.ARTIFACT_INVALID, f"manifest field {key} must be an object")
    return value


def _require_list(data: dict[str, Any], key: str) -> list[Any]:
    value = data.get(key)
    if not isinstance(value, list):
        raise LayeringError(ErrorCode.ARTIFACT_INVALID, f"manifest field {key} must be a list")
    return value


def _require_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise LayeringError(ErrorCode.ARTIFACT_INVALID, f"manifest field {key} must be a non-empty string")
    return value


def _require_positive_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or value <= 0:
        raise LayeringError(ErrorCode.ARTIFACT_INVALID, f"manifest field {key} must be a positive integer")
    return value


def _require_non_negative_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or value < 0:
        raise LayeringError(ErrorCode.ARTIFACT_INVALID, f"manifest field {key} must be a non-negative integer")
    return value
