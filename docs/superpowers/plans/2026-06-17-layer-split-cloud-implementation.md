# 云端 AI 拆图层 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个本地 `pixelator-layer` 批处理命令，通过稳定 HTTP 合约调用云端拆图层服务，并为每张源图输出 `PNG 图层 + manifest.json + preview/composite.png` 的 ZIP 包。

**Architecture:** 本地侧新增 `pixelator.layering` 包，负责 manifest 类型、ZIP 校验、HTTP 客户端、批处理编排和 CLI。云端侧新增 `pixelator.layering_service` 可选服务包，默认用轻量 Mock 后端验证 HTTP 合约，生产部署时切到阿里云 GPU 上的 Qwen-Image-Layered 后端。Pixelator 现有 `pixelator` 和 `pixelator-gui` 渲染流程不变。

**Tech Stack:** Python 3.11、Pillow、标准库 `urllib`/`zipfile`/`json`、可选 FastAPI/Uvicorn、可选 Qwen-Image-Layered Diffusers 后端、pytest。

---

## 范围检查

规格中包含本地 CLI 和云端服务两个部署单元，但第一版需要端到端验证稳定合约，因此放在同一份计划里完成一个可运行的最小闭环：本地 CLI 可以调用云端 Mock 服务拿到标准 ZIP；Qwen 真模型作为同一服务内的可替换后端接入，并通过注入 fake pipeline 做单元测试。PSD、GUI、递归拆分、OSS 直连批处理不进入本计划。

## 文件结构

- Create: `src/pixelator/layering/__init__.py`
  - 导出本地拆图层包的公共类型。
- Create: `src/pixelator/layering/types.py`
  - 定义 manifest dataclass、错误码、状态枚举、JSON 序列化和校验。
- Create: `src/pixelator/layering/archive.py`
  - 负责 alpha 裁切、预览合成、ZIP 写入、ZIP 校验、源图 hash。
- Create: `src/pixelator/layering/client.py`
  - 用标准库实现 multipart 上传、任务轮询、artifact 下载和远端错误映射。
- Create: `src/pixelator/layering/commands.py`
  - 实现 `split_path` 批处理编排、图片发现、输出命名、`batch-summary.json`。
- Create: `src/pixelator/layering/cli.py`
  - `argparse` 入口，提供 `pixelator-layer split`。
- Modify: `pyproject.toml`
  - 增加 `pixelator-layer` 和 `pixelator-layer-service` console scripts；新增 `layer-cloud` 可选依赖。
- Create: `src/pixelator/layering_service/__init__.py`
  - 云端服务包标识。
- Create: `src/pixelator/layering_service/backends.py`
  - 定义 `LayerBackend` 协议、`MockLayerBackend`、`SelfHostedQwenLayerBackend`。
- Create: `src/pixelator/layering_service/jobs.py`
  - 内存 job store、后台 worker、状态转换。
- Create: `src/pixelator/layering_service/app.py`
  - FastAPI 应用工厂、HTTP 路由、服务启动入口。
- Create: `docs/layer-split-aliyun.md`
  - 中文部署和使用文档，覆盖百炼原生接口缺口、自托管 GPU 服务、环境变量、验证命令。
- Create: `tests/test_layering_types.py`
- Create: `tests/test_layering_archive.py`
- Create: `tests/test_layering_client.py`
- Create: `tests/test_layering_cli.py`
- Create: `tests/test_layering_service.py`

---

### Task 1: Manifest 类型与错误模型

**Files:**
- Create: `src/pixelator/layering/__init__.py`
- Create: `src/pixelator/layering/types.py`
- Test: `tests/test_layering_types.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_layering_types.py` 写入：

```python
import pytest

from pixelator.layering.types import (
    ErrorCode,
    LayerInfo,
    LayerManifest,
    LayeringError,
    ModelInfo,
    PreviewInfo,
    SourceInfo,
)


def test_manifest_round_trips_to_stable_json_dict():
    manifest = LayerManifest(
        source=SourceInfo(file_name="hero.png", width=128, height=64, sha256="abc123"),
        model=ModelInfo(provider="qwen-image-layered", backend="aliyun-self-hosted", model_id="Qwen/Qwen-Image-Layered"),
        layers=[
            LayerInfo(
                id="layer_001",
                name="layer_001",
                file="layers/layer_001.png",
                order=0,
                bbox=(4, 6, 32, 40),
                width=32,
                height=40,
            )
        ],
        preview=PreviewInfo(file="preview/composite.png"),
    )

    data = manifest.to_dict()
    restored = LayerManifest.from_dict(data)

    assert data["schema_version"] == 1
    assert data["layers"][0]["bbox"] == [4, 6, 32, 40]
    assert restored == manifest


def test_manifest_rejects_empty_layers():
    data = {
        "schema_version": 1,
        "source": {"file_name": "hero.png", "width": 128, "height": 64, "sha256": "abc123"},
        "model": {"provider": "qwen-image-layered", "backend": "mock", "model_id": "mock"},
        "layers": [],
        "preview": {"file": "preview/composite.png"},
    }

    with pytest.raises(LayeringError) as exc_info:
        LayerManifest.from_dict(data)

    assert exc_info.value.code == ErrorCode.ARTIFACT_INVALID
    assert "at least one layer" in str(exc_info.value)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_layering_types.py -v`

Expected: FAIL，报错包含 `ModuleNotFoundError: No module named 'pixelator.layering'`。

- [ ] **Step 3: 实现最小类型层**

在 `src/pixelator/layering/__init__.py` 写入：

```python
from pixelator.layering.types import (
    ErrorCode,
    JobStatus,
    LayerInfo,
    LayerManifest,
    LayeringError,
    ModelInfo,
    PreviewInfo,
    SourceInfo,
)

__all__ = [
    "ErrorCode",
    "JobStatus",
    "LayerInfo",
    "LayerManifest",
    "LayeringError",
    "ModelInfo",
    "PreviewInfo",
    "SourceInfo",
]
```

在 `src/pixelator/layering/types.py` 写入：

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_layering_types.py -v`

Expected: PASS，2 tests passed。

- [ ] **Step 5: 提交**

```bash
git add src/pixelator/layering/__init__.py src/pixelator/layering/types.py tests/test_layering_types.py
git commit -m "Add layer manifest types"
```

---

### Task 2: ZIP 写入、manifest 校验与 alpha 裁切

**Files:**
- Create: `src/pixelator/layering/archive.py`
- Test: `tests/test_layering_archive.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_layering_archive.py` 写入：

```python
import json
import zipfile
from pathlib import Path

from PIL import Image

from pixelator.layering.archive import alpha_bbox, validate_layer_zip, write_layer_zip


def test_alpha_bbox_returns_visible_bounds():
    image = Image.new("RGBA", (8, 6), (0, 0, 0, 0))
    for x in range(2, 5):
        for y in range(1, 4):
            image.putpixel((x, y), (255, 0, 0, 255))

    assert alpha_bbox(image) == (2, 1, 3, 3)


def test_write_layer_zip_crops_layers_and_writes_manifest(tmp_path: Path):
    source = tmp_path / "hero.png"
    Image.new("RGBA", (8, 6), (10, 20, 30, 255)).save(source)
    layer = Image.new("RGBA", (8, 6), (0, 0, 0, 0))
    for x in range(2, 5):
        for y in range(1, 4):
            layer.putpixel((x, y), (255, 0, 0, 255))
    zip_path = tmp_path / "hero-layers.zip"

    manifest = write_layer_zip(
        source_path=source,
        source_image=Image.open(source).convert("RGBA"),
        layers=[layer],
        output_path=zip_path,
        backend="mock",
        model_id="mock",
    )

    assert manifest.layers[0].bbox == (2, 1, 3, 3)
    assert manifest.layers[0].width == 3
    assert manifest.layers[0].height == 3

    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "layers/layer_001.png" in names
        assert "preview/composite.png" in names
        data = json.loads(archive.read("manifest.json").decode("utf-8"))

    assert data["source"]["file_name"] == "hero.png"
    assert data["layers"][0]["file"] == "layers/layer_001.png"
    assert validate_layer_zip(zip_path).source.file_name == "hero.png"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_layering_archive.py -v`

Expected: FAIL，报错包含 `ModuleNotFoundError: No module named 'pixelator.layering.archive'`。

- [ ] **Step 3: 实现 archive 模块**

在 `src/pixelator/layering/archive.py` 写入：

```python
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from pixelator.layering.types import (
    ErrorCode,
    LayerInfo,
    LayerManifest,
    LayeringError,
    ModelInfo,
    PreviewInfo,
    SourceInfo,
)


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    rgba = image.convert("RGBA")
    bbox = rgba.getchannel("A").getbbox()
    if bbox is None:
        return (0, 0, rgba.width, rgba.height)
    left, top, right, bottom = bbox
    return (left, top, right - left, bottom - top)


def crop_to_alpha(image: Image.Image) -> tuple[Image.Image, tuple[int, int, int, int]]:
    rgba = image.convert("RGBA")
    left, top, width, height = alpha_bbox(rgba)
    return rgba.crop((left, top, left + width, top + height)), (left, top, width, height)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compose_preview(canvas_size: tuple[int, int], layers: list[Image.Image], bboxes: list[tuple[int, int, int, int]]) -> Image.Image:
    preview = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    for layer, bbox in zip(layers, bboxes, strict=True):
        preview.alpha_composite(layer.convert("RGBA"), dest=(bbox[0], bbox[1]))
    return preview


def write_layer_zip(
    source_path: str | Path,
    source_image: Image.Image,
    layers: list[Image.Image],
    output_path: str | Path,
    backend: str,
    model_id: str,
    crop_alpha: bool = True,
) -> LayerManifest:
    if not layers:
        raise LayeringError(ErrorCode.ARTIFACT_INVALID, "cannot write layer ZIP without layers")

    source_file = Path(source_path)
    final_output = Path(output_path)
    final_output.parent.mkdir(parents=True, exist_ok=True)
    prepared_layers: list[Image.Image] = []
    bboxes: list[tuple[int, int, int, int]] = []
    layer_infos: list[LayerInfo] = []

    for index, layer in enumerate(layers, start=1):
        rgba = layer.convert("RGBA")
        if crop_alpha:
            prepared, bbox = crop_to_alpha(rgba)
        else:
            prepared = rgba
            bbox = (0, 0, rgba.width, rgba.height)
        layer_id = f"layer_{index:03d}"
        layer_file = f"layers/{layer_id}.png"
        prepared_layers.append(prepared)
        bboxes.append(bbox)
        layer_infos.append(
            LayerInfo(
                id=layer_id,
                name=layer_id,
                file=layer_file,
                order=index - 1,
                bbox=bbox,
                width=prepared.width,
                height=prepared.height,
            )
        )

    source_rgba = source_image.convert("RGBA")
    manifest = LayerManifest(
        source=SourceInfo(
            file_name=source_file.name,
            width=source_rgba.width,
            height=source_rgba.height,
            sha256=sha256_file(source_file),
        ),
        model=ModelInfo(provider="qwen-image-layered", backend=backend, model_id=model_id),
        layers=layer_infos,
        preview=PreviewInfo(file="preview/composite.png"),
    )

    with TemporaryDirectory(prefix="pixelator-layer-") as temp_dir:
        temp_path = Path(temp_dir)
        layer_dir = temp_path / "layers"
        preview_dir = temp_path / "preview"
        layer_dir.mkdir()
        preview_dir.mkdir()
        for prepared, info in zip(prepared_layers, layer_infos, strict=True):
            prepared.save(temp_path / info.file)
        preview = compose_preview(source_rgba.size, prepared_layers, bboxes)
        preview.save(temp_path / manifest.preview.file)
        (temp_path / "manifest.json").write_text(json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        with zipfile.ZipFile(final_output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in sorted(temp_path.rglob("*")):
                if file_path.is_file():
                    archive.write(file_path, file_path.relative_to(temp_path).as_posix())

    return manifest


def validate_layer_zip(path: str | Path) -> LayerManifest:
    zip_path = Path(path)
    try:
        with zipfile.ZipFile(zip_path) as archive:
            names = set(archive.namelist())
            if "manifest.json" not in names:
                raise LayeringError(ErrorCode.ARTIFACT_INVALID, "artifact is missing manifest.json")
            data = json.loads(archive.read("manifest.json").decode("utf-8"))
            manifest = LayerManifest.from_dict(data)
            required = {manifest.preview.file, *(layer.file for layer in manifest.layers)}
            missing = sorted(required - names)
            if missing:
                raise LayeringError(ErrorCode.ARTIFACT_INVALID, f"artifact is missing files: {', '.join(missing)}")
            return manifest
    except zipfile.BadZipFile as exc:
        raise LayeringError(ErrorCode.ARTIFACT_INVALID, f"artifact is not a valid ZIP: {zip_path}") from exc
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_layering_types.py tests/test_layering_archive.py -v`

Expected: PASS，全部测试通过。

- [ ] **Step 5: 提交**

```bash
git add src/pixelator/layering/archive.py tests/test_layering_archive.py
git commit -m "Add layer ZIP archive helpers"
```

---

### Task 3: 云端 HTTP 客户端与 artifact 下载

**Files:**
- Create: `src/pixelator/layering/client.py`
- Test: `tests/test_layering_client.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_layering_client.py` 写入：

```python
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image

from pixelator.layering.archive import write_layer_zip
from pixelator.layering.client import LayerSplitClient


class FakeLayerHandler(BaseHTTPRequestHandler):
    artifact_path: Path

    def do_POST(self):
        if self.path != "/v1/layer-splits":
            self.send_error(404)
            return
        body = json.dumps({"job_id": "job_123", "status": "queued"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/v1/layer-splits/job_123":
            body = json.dumps({"job_id": "job_123", "status": "succeeded", "artifact_url": "/v1/layer-splits/job_123/artifact", "error": None}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/v1/layer-splits/job_123/artifact":
            data = self.artifact_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_error(404)

    def log_message(self, format, *args):
        return


def test_client_submits_polls_and_downloads_artifact(tmp_path: Path):
    source = tmp_path / "hero.png"
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(source)
    artifact = tmp_path / "artifact.zip"
    write_layer_zip(source, Image.open(source), [Image.open(source)], artifact, backend="mock", model_id="mock")
    FakeLayerHandler.artifact_path = artifact
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeLayerHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}"

    try:
        client = LayerSplitClient(endpoint=endpoint, api_key="secret", poll_interval=0.01, timeout=2.0)
        downloaded = client.split_image(source, tmp_path / "downloaded.zip", target_layers=4)
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert downloaded.source.file_name == "hero.png"
    assert (tmp_path / "downloaded.zip").exists()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_layering_client.py -v`

Expected: FAIL，报错包含 `ModuleNotFoundError: No module named 'pixelator.layering.client'`。

- [ ] **Step 3: 实现标准库 HTTP 客户端**

在 `src/pixelator/layering/client.py` 写入：

```python
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from pixelator.layering.archive import validate_layer_zip
from pixelator.layering.types import ErrorCode, JobStatus, LayerManifest, LayeringError


class LayerSplitClient:
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        poll_interval: float = 2.0,
        timeout: float = 600.0,
    ) -> None:
        self.endpoint = endpoint.rstrip("/") + "/"
        self.api_key = api_key
        self.poll_interval = poll_interval
        self.timeout = timeout

    def split_image(self, image_path: str | Path, output_path: str | Path, target_layers: int | None = None) -> LayerManifest:
        job_id = self.submit_split(image_path, target_layers=target_layers)
        artifact_url = self.wait_for_artifact(job_id)
        self.download_artifact(artifact_url, output_path)
        return validate_layer_zip(output_path)

    def submit_split(self, image_path: str | Path, target_layers: int | None = None) -> str:
        image_file = Path(image_path)
        request_payload = {"target_layers": target_layers, "crop_alpha": True, "zip_result": True}
        body, content_type = _multipart_body(image_file, request_payload)
        response = self._request_json(
            "POST",
            "v1/layer-splits",
            body=body,
            headers={"Content-Type": content_type},
        )
        job_id = response.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            raise LayeringError(ErrorCode.JOB_FAILED, "layer service did not return a job_id")
        return job_id

    def wait_for_artifact(self, job_id: str) -> str:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            response = self._request_json("GET", f"v1/layer-splits/{job_id}")
            status = JobStatus(str(response.get("status", "unknown")))
            if status == JobStatus.SUCCEEDED:
                artifact_url = response.get("artifact_url") or f"v1/layer-splits/{job_id}/artifact"
                if not isinstance(artifact_url, str):
                    raise LayeringError(ErrorCode.JOB_FAILED, "layer service returned an invalid artifact URL")
                return artifact_url
            if status in {JobStatus.FAILED, JobStatus.CANCELED, JobStatus.UNKNOWN}:
                error = response.get("error")
                message = str(error.get("message")) if isinstance(error, dict) and error.get("message") else f"layer job {job_id} failed"
                raise LayeringError(ErrorCode.JOB_FAILED, message, request_id=job_id)
            time.sleep(self.poll_interval)
        raise LayeringError(ErrorCode.JOB_TIMEOUT, f"layer job {job_id} did not finish within {self.timeout:g} seconds", request_id=job_id)

    def download_artifact(self, artifact_url: str, output_path: str | Path) -> Path:
        url = artifact_url if artifact_url.startswith(("http://", "https://")) else urljoin(self.endpoint, artifact_url.lstrip("/"))
        request = Request(url, headers=self._auth_headers(), method="GET")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                data = response.read()
        except HTTPError as exc:
            raise _http_error(exc) from exc
        except URLError as exc:
            raise LayeringError(ErrorCode.JOB_FAILED, f"could not download layer artifact: {exc.reason}") from exc
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        validate_layer_zip(target)
        return target

    def _request_json(self, method: str, path: str, body: bytes | None = None, headers: dict[str, str] | None = None) -> dict[str, object]:
        request_headers = self._auth_headers()
        if headers:
            request_headers.update(headers)
        url = urljoin(self.endpoint, path)
        request = Request(url, data=body, headers=request_headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            raise _http_error(exc) from exc
        except URLError as exc:
            raise LayeringError(ErrorCode.JOB_FAILED, f"could not reach layer service: {exc.reason}") from exc
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise LayeringError(ErrorCode.JOB_FAILED, "layer service returned a non-object JSON response")
        return data

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}


def _multipart_body(image_path: Path, request_payload: dict[str, object]) -> tuple[bytes, str]:
    boundary = f"----pixelator-{uuid.uuid4().hex}"
    parts: list[bytes] = []
    image_bytes = image_path.read_bytes()
    request_json = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")
    parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="image"; filename="{image_path.name}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8")
        + image_bytes
        + b"\r\n"
    )
    parts.append(
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="request"\r\n'
            "Content-Type: application/json\r\n\r\n"
        ).encode("utf-8")
        + request_json
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _http_error(exc: HTTPError) -> LayeringError:
    if exc.code in {401, 403}:
        return LayeringError(ErrorCode.AUTH_FAILED, "layer service rejected the API key")
    if exc.code == 413:
        return LayeringError(ErrorCode.INPUT_TOO_LARGE, "layer service rejected the image because it is too large")
    try:
        payload = json.loads(exc.read().decode("utf-8"))
    except Exception:
        payload = {}
    message = str(payload.get("message") or payload.get("detail") or f"layer service returned HTTP {exc.code}")
    return LayeringError(ErrorCode.JOB_FAILED, message)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_layering_types.py tests/test_layering_archive.py tests/test_layering_client.py -v`

Expected: PASS，全部测试通过。

- [ ] **Step 5: 提交**

```bash
git add src/pixelator/layering/client.py tests/test_layering_client.py
git commit -m "Add layer split HTTP client"
```

---

### Task 4: 本地批处理命令与 `pixelator-layer` CLI

**Files:**
- Create: `src/pixelator/layering/commands.py`
- Create: `src/pixelator/layering/cli.py`
- Modify: `pyproject.toml`
- Test: `tests/test_layering_cli.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_layering_cli.py` 写入：

```python
import json
from pathlib import Path

from PIL import Image

from pixelator.layering import cli
from pixelator.layering.archive import write_layer_zip


class FakeClient:
    def __init__(self, endpoint, api_key, poll_interval=2.0, timeout=600.0):
        self.endpoint = endpoint
        self.api_key = api_key

    def split_image(self, image_path, output_path, target_layers=None):
        image = Image.open(image_path).convert("RGBA")
        return write_layer_zip(image_path, image, [image], output_path, backend="fake", model_id="fake")


def test_cli_splits_image_folder_and_writes_summary(monkeypatch, tmp_path: Path):
    first = tmp_path / "b.png"
    second = tmp_path / "a.jpg"
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(first)
    Image.new("RGB", (3, 3), (0, 255, 0)).save(second)
    output_dir = tmp_path / "out"
    monkeypatch.setenv("PIXELATOR_LAYER_API_KEY", "secret")
    monkeypatch.setattr("pixelator.layering.commands.LayerSplitClient", FakeClient)

    exit_code = cli.main(["split", str(tmp_path), "--out", str(output_dir), "--endpoint", "http://service", "--overwrite"])

    assert exit_code == 0
    assert (output_dir / "a-layers.zip").exists()
    assert (output_dir / "b-layers.zip").exists()
    summary = json.loads((output_dir / "batch-summary.json").read_text(encoding="utf-8"))
    assert [item["source"] for item in summary["items"]] == [str(second), str(first)]
    assert all(item["status"] == "succeeded" for item in summary["items"])


def test_cli_requires_api_key(monkeypatch, tmp_path: Path, capsys):
    source = tmp_path / "hero.png"
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(source)
    monkeypatch.delenv("PIXELATOR_LAYER_API_KEY", raising=False)

    exit_code = cli.main(["split", str(source), "--out", str(tmp_path / "out"), "--endpoint", "http://service"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "PIXELATOR_LAYER_API_KEY" in captured.err
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_layering_cli.py -v`

Expected: FAIL，报错包含 `ImportError` 或 `ModuleNotFoundError`，因为 `pixelator.layering.cli` 还不存在。

- [ ] **Step 3: 实现 commands 与 CLI**

在 `src/pixelator/layering/commands.py` 写入：

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pixelator.layering.client import LayerSplitClient
from pixelator.layering.types import LayeringError
from pixelator.media import is_image_path, iter_image_files


@dataclass(frozen=True)
class SplitOptions:
    input_path: Path
    output_dir: Path
    endpoint: str
    api_key: str
    target_layers: int | None = None
    timeout: float = 600.0
    poll_interval: float = 2.0
    overwrite: bool = False
    fail_fast: bool = False


def discover_images(input_path: Path) -> list[Path]:
    if input_path.is_dir():
        return iter_image_files(input_path)
    if input_path.is_file() and is_image_path(input_path):
        return [input_path]
    return []


def output_zip_path(source_path: Path, output_dir: Path) -> Path:
    return output_dir / f"{source_path.stem}-layers.zip"


def split_path(options: SplitOptions) -> int:
    images = discover_images(options.input_path)
    options.output_dir.mkdir(parents=True, exist_ok=True)
    client = LayerSplitClient(
        endpoint=options.endpoint,
        api_key=options.api_key,
        poll_interval=options.poll_interval,
        timeout=options.timeout,
    )
    summary: dict[str, object] = {"items": []}
    failures = 0
    for image_path in images:
        zip_path = output_zip_path(image_path, options.output_dir)
        item: dict[str, object] = {"source": str(image_path), "output": str(zip_path)}
        if zip_path.exists() and not options.overwrite:
            item["status"] = "failed"
            item["error"] = "output exists; pass --overwrite to replace it"
            failures += 1
        else:
            try:
                manifest = client.split_image(image_path, zip_path, target_layers=options.target_layers)
                item["status"] = "succeeded"
                item["layers"] = len(manifest.layers)
            except LayeringError as exc:
                item["status"] = "failed"
                item["error_code"] = exc.code.value
                item["error"] = str(exc)
                failures += 1
        cast_items = summary["items"]
        assert isinstance(cast_items, list)
        cast_items.append(item)
        if failures and options.fail_fast:
            break
    summary["succeeded"] = len([item for item in summary["items"] if item["status"] == "succeeded"])
    summary["failed"] = failures
    (options.output_dir / "batch-summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0 if failures == 0 and images else 1
```

在 `src/pixelator/layering/cli.py` 写入：

```python
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from pixelator.layering.commands import SplitOptions, split_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pixelator-layer", description="Split AI art images into transparent PNG layers.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    split = subparsers.add_parser("split", help="Split one image or a folder of images into layer ZIP files.")
    split.add_argument("input", type=Path, help="Input image path or folder.")
    split.add_argument("--out", type=Path, required=True, help="Output folder for layer ZIP files.")
    split.add_argument("--endpoint", required=True, help="Layer split service endpoint.")
    split.add_argument("--api-key-env", default="PIXELATOR_LAYER_API_KEY", help="Environment variable that stores the service API key.")
    split.add_argument("--layers", type=int, help="Requested layer count when supported by the backend.")
    split.add_argument("--timeout", type=float, default=600.0, help="Maximum seconds to wait for each image.")
    split.add_argument("--poll-interval", type=float, default=2.0, help="Seconds between job status polls.")
    split.add_argument("--overwrite", action="store_true", help="Replace existing ZIP outputs.")
    split.add_argument("--fail-fast", action="store_true", help="Stop after the first failed image.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        print(f"pixelator-layer: error: missing API key environment variable {args.api_key_env}", file=sys.stderr)
        return 1
    if args.command == "split":
        return split_path(
            SplitOptions(
                input_path=args.input,
                output_dir=args.out,
                endpoint=args.endpoint,
                api_key=api_key,
                target_layers=args.layers,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
                overwrite=args.overwrite,
                fail_fast=args.fail_fast,
            )
        )
    parser.print_help(sys.stderr)
    return 2
```

修改 `pyproject.toml` 的 `[project.scripts]`：

```toml
[project.scripts]
pixelator = "pixelator.cli:main"
pixelator-gui = "pixelator.gui.app:main"
pixelator-layer = "pixelator.layering.cli:main"
pixelator-layer-service = "pixelator.layering_service.app:main"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_layering_types.py tests/test_layering_archive.py tests/test_layering_client.py tests/test_layering_cli.py -v`

Expected: PASS，全部测试通过。

- [ ] **Step 5: 提交**

```bash
git add pyproject.toml src/pixelator/layering/commands.py src/pixelator/layering/cli.py tests/test_layering_cli.py
git commit -m "Add layer split batch CLI"
```

---

### Task 5: 云端服务骨架与 Mock 后端

**Files:**
- Modify: `pyproject.toml`
- Create: `src/pixelator/layering_service/__init__.py`
- Create: `src/pixelator/layering_service/backends.py`
- Create: `src/pixelator/layering_service/jobs.py`
- Create: `src/pixelator/layering_service/app.py`
- Test: `tests/test_layering_service.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_layering_service.py` 写入：

```python
import io
from pathlib import Path

import pytest
from PIL import Image

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from pixelator.layering.archive import validate_layer_zip
from pixelator.layering_service.app import create_app


def test_cloud_service_accepts_image_and_returns_layer_zip(tmp_path: Path):
    app = create_app(api_token="secret")
    client = TestClient(app)
    buffer = io.BytesIO()
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(buffer, format="PNG")

    response = client.post(
        "/v1/layer-splits",
        headers={"Authorization": "Bearer secret"},
        files={"image": ("hero.png", buffer.getvalue(), "image/png")},
        data={"request": '{"target_layers": 4, "crop_alpha": true, "zip_result": true}'},
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    status_response = client.get(f"/v1/layer-splits/{job_id}", headers={"Authorization": "Bearer secret"})
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "succeeded"

    artifact_response = client.get(f"/v1/layer-splits/{job_id}/artifact", headers={"Authorization": "Bearer secret"})
    assert artifact_response.status_code == 200
    artifact_path = tmp_path / "artifact.zip"
    artifact_path.write_bytes(artifact_response.content)
    manifest = validate_layer_zip(artifact_path)
    assert manifest.source.file_name == "hero.png"
```

- [ ] **Step 2: 安装可选云端依赖并运行测试确认失败**

Run: `python -m pip install -e ".[dev,layer-cloud]"`

Expected: 安装成功，包含 `fastapi`、`uvicorn`、`python-multipart`。

Run: `python -m pytest tests/test_layering_service.py -v`

Expected: FAIL，报错包含 `ModuleNotFoundError: No module named 'pixelator.layering_service'`。

- [ ] **Step 3: 实现云端服务骨架**

在 `pyproject.toml` 的 `[project.optional-dependencies]` 中加入：

```toml
layer-cloud = [
  "fastapi>=0.115",
  "python-multipart>=0.0.9",
  "uvicorn>=0.30",
]
```

在 `src/pixelator/layering_service/__init__.py` 写入：

```python
"""Cloud service for Pixelator layer splitting."""
```

在 `src/pixelator/layering_service/backends.py` 写入：

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

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

    def split(self, source_path: Path, output_path: Path, request: LayerRequest) -> LayerManifest:
        raise NotImplementedError


class MockLayerBackend:
    backend_name = "mock"
    model_id = "mock"

    def split(self, source_path: Path, output_path: Path, request: LayerRequest) -> LayerManifest:
        image = Image.open(source_path).convert("RGBA")
        return write_layer_zip(
            source_path=source_path,
            source_image=image,
            layers=[image],
            output_path=output_path,
            backend=self.backend_name,
            model_id=self.model_id,
            crop_alpha=request.crop_alpha,
        )
```

在 `src/pixelator/layering_service/jobs.py` 写入：

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from pixelator.layering.types import JobStatus
from pixelator.layering_service.backends import LayerBackend, LayerRequest


@dataclass
class LayerJob:
    id: str
    source_path: Path
    artifact_path: Path
    status: JobStatus
    error: str | None = None


class JobStore:
    def __init__(self, work_dir: Path, backend: LayerBackend) -> None:
        self.work_dir = work_dir
        self.backend = backend
        self.jobs: dict[str, LayerJob] = {}
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def create_and_run(self, source_path: Path, request: LayerRequest) -> LayerJob:
        job_id = f"job_{uuid4().hex}"
        artifact_path = self.work_dir / f"{job_id}.zip"
        job = LayerJob(id=job_id, source_path=source_path, artifact_path=artifact_path, status=JobStatus.QUEUED)
        self.jobs[job_id] = job
        job.status = JobStatus.RUNNING
        try:
            self.backend.split(source_path, artifact_path, request)
            job.status = JobStatus.SUCCEEDED
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
        return job

    def get(self, job_id: str) -> LayerJob | None:
        return self.jobs.get(job_id)
```

在 `src/pixelator/layering_service/app.py` 写入：

```python
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from pixelator.layering.types import JobStatus
from pixelator.layering_service.backends import LayerBackend, LayerRequest, MockLayerBackend
from pixelator.layering_service.jobs import JobStore


def create_app(api_token: str | None = None, backend: LayerBackend | None = None, work_dir: Path | None = None):
    try:
        from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
        from fastapi.responses import FileResponse
    except ImportError as exc:
        raise RuntimeError("Install cloud service dependencies with: python -m pip install -e .[layer-cloud]") from exc

    token = api_token or os.environ.get("PIXELATOR_LAYER_SERVICE_TOKEN", "dev-token")
    temp_dir = TemporaryDirectory(prefix="pixelator-layer-service-") if work_dir is None else None
    store_dir = work_dir or Path(temp_dir.name)
    store = JobStore(store_dir, backend or MockLayerBackend())
    app = FastAPI(title="Pixelator Layer Split Service")

    def require_auth(authorization: str | None) -> None:
        if authorization != f"Bearer {token}":
            raise HTTPException(status_code=401, detail="invalid API token")

    @app.post("/v1/layer-splits")
    async def create_layer_split(
        image: UploadFile = File(...),
        request: str = Form("{}"),
        authorization: str | None = Header(default=None),
    ):
        require_auth(authorization)
        payload = json.loads(request)
        layer_request = LayerRequest(
            target_layers=payload.get("target_layers"),
            crop_alpha=bool(payload.get("crop_alpha", True)),
            zip_result=bool(payload.get("zip_result", True)),
        )
        suffix = Path(image.filename or "image.png").suffix or ".png"
        source_path = store_dir / f"input_{len(store.jobs) + 1}{suffix}"
        source_path.write_bytes(await image.read())
        job = store.create_and_run(source_path, layer_request)
        return {"job_id": job.id, "status": job.status.value}

    @app.get("/v1/layer-splits/{job_id}")
    def get_layer_split(job_id: str, authorization: str | None = Header(default=None)):
        require_auth(authorization)
        job = store.get(job_id)
        if job is None:
            return {"job_id": job_id, "status": JobStatus.UNKNOWN.value, "error": {"message": "job not found"}}
        return {
            "job_id": job.id,
            "status": job.status.value,
            "artifact_url": f"/v1/layer-splits/{job.id}/artifact" if job.status == JobStatus.SUCCEEDED else None,
            "error": {"message": job.error} if job.error else None,
        }

    @app.get("/v1/layer-splits/{job_id}/artifact")
    def get_artifact(job_id: str, authorization: str | None = Header(default=None)):
        require_auth(authorization)
        job = store.get(job_id)
        if job is None or job.status != JobStatus.SUCCEEDED:
            raise HTTPException(status_code=404, detail="artifact not found")
        return FileResponse(job.artifact_path, media_type="application/zip", filename=f"{job_id}.zip")

    return app


def main() -> int:
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("Install cloud service dependencies with: python -m pip install -e .[layer-cloud]") from exc
    uvicorn.run(create_app(), host="0.0.0.0", port=int(os.environ.get("PIXELATOR_LAYER_SERVICE_PORT", "8000")))
    return 0
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_layering_service.py tests/test_layering_cli.py -v`

Expected: PASS，云端服务测试和 CLI 测试通过。

- [ ] **Step 5: 提交**

```bash
git add pyproject.toml src/pixelator/layering_service tests/test_layering_service.py
git commit -m "Add cloud layer split service skeleton"
```

---

### Task 6: Qwen 自托管后端与阿里云部署文档

**Files:**
- Modify: `src/pixelator/layering_service/backends.py`
- Create: `docs/layer-split-aliyun.md`
- Test: `tests/test_layering_service.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_layering_service.py` 追加：

```python
from pixelator.layering_service.backends import LayerRequest, SelfHostedQwenLayerBackend


class FakeQwenOutput:
    def __init__(self, layers):
        self.images = [layers]


class FakeQwenPipeline:
    def __call__(self, **kwargs):
        image = kwargs["image"].convert("RGBA")
        transparent = Image.new("RGBA", image.size, (0, 0, 0, 0))
        return FakeQwenOutput([image, transparent])


def test_self_hosted_qwen_backend_uses_injected_pipeline(tmp_path: Path):
    source = tmp_path / "hero.png"
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(source)
    backend = SelfHostedQwenLayerBackend(pipeline_factory=lambda: FakeQwenPipeline())

    manifest = backend.split(source, tmp_path / "artifact.zip", LayerRequest(target_layers=2))

    assert backend.backend_name == "aliyun-self-hosted"
    assert manifest.model.model_id == "Qwen/Qwen-Image-Layered"
    assert len(manifest.layers) == 2
    assert (tmp_path / "artifact.zip").exists()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_layering_service.py::test_self_hosted_qwen_backend_uses_injected_pipeline -v`

Expected: FAIL，报错包含 `ImportError: cannot import name 'SelfHostedQwenLayerBackend'`。

- [ ] **Step 3: 实现懒加载 Qwen 后端并写中文部署文档**

在 `src/pixelator/layering_service/backends.py` 追加：

```python
class SelfHostedQwenLayerBackend:
    backend_name = "aliyun-self-hosted"
    model_id = "Qwen/Qwen-Image-Layered"

    def __init__(
        self,
        pipeline_factory=None,
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
        self._pipeline = None

    def split(self, source_path: Path, output_path: Path, request: LayerRequest) -> LayerManifest:
        image = Image.open(source_path).convert("RGBA")
        pipeline = self._pipeline_instance()
        output = pipeline(
            image=image,
            true_cfg_scale=self.true_cfg_scale,
            negative_prompt=" ",
            num_inference_steps=self.steps,
            num_images_per_prompt=1,
            layers=request.target_layers or self.default_layers,
            resolution=self.resolution,
            cfg_normalize=True,
            use_en_prompt=True,
        )
        output_layers = [layer.convert("RGBA") for layer in output.images[0]]
        return write_layer_zip(
            source_path=source_path,
            source_image=image,
            layers=output_layers,
            output_path=output_path,
            backend=self.backend_name,
            model_id=self.model_id,
            crop_alpha=request.crop_alpha,
        )

    def _pipeline_instance(self):
        if self._pipeline is None:
            self._pipeline = self.pipeline_factory()
        return self._pipeline

    def _default_pipeline_factory(self):
        try:
            import torch
            from diffusers import QwenImageLayeredPipeline
        except ImportError as exc:
            raise RuntimeError(
                "Qwen backend requires torch and the latest diffusers on the cloud GPU image. "
                "Install them in the cloud runtime, not in the default Pixelator desktop package."
            ) from exc
        pipeline = QwenImageLayeredPipeline.from_pretrained(self.model_id)
        pipeline = pipeline.to("cuda", torch.bfloat16)
        pipeline.set_progress_bar_config(disable=None)
        return pipeline
```

创建 `docs/layer-split-aliyun.md`，正文使用中文：

```markdown
# 阿里云 AI 拆图层部署说明

## 目标

本服务用于接收本地 `pixelator-layer` 上传的 AI 美术图片，在云端调用 Qwen-Image-Layered 拆分 RGBA 图层，并返回包含 `manifest.json`、`layers/*.png`、`preview/composite.png` 的 ZIP。

## 推荐路径

优先检查阿里百炼是否已经开放 Qwen-Image-Layered 原生 API。如果已开放，可以在云端服务中实现 `NativeBailianLayerBackend`，但本地 CLI 不需要改变。

如果百炼没有原生 Layered API，使用阿里云 GPU 实例或容器服务自托管 `Qwen/Qwen-Image-Layered`。模型权重和 Hugging Face cache 放在持久化数据盘，容器镜像只放服务代码和 Python 依赖。

## 本地验证命令

```powershell
python -m pip install -e ".[dev,layer-cloud]"
$env:PIXELATOR_LAYER_SERVICE_TOKEN="change-me"
pixelator-layer-service
```

另开终端：

```powershell
$env:PIXELATOR_LAYER_API_KEY="change-me"
pixelator-layer split .\inputs --out .\outputs\layers --endpoint http://127.0.0.1:8000 --overwrite
```

## 云端 Qwen 运行时

云端镜像需要安装 CUDA 版 PyTorch、最新版 Diffusers、Transformers、Accelerate、Pillow，并能访问或预缓存 `Qwen/Qwen-Image-Layered`。

Qwen 官方示例使用：

```python
from diffusers import QwenImageLayeredPipeline
import torch

pipeline = QwenImageLayeredPipeline.from_pretrained("Qwen/Qwen-Image-Layered")
pipeline = pipeline.to("cuda", torch.bfloat16)
```

## 运维要求

- 使用 HTTPS 暴露服务。
- `PIXELATOR_LAYER_SERVICE_TOKEN` 使用强随机值。
- 不在日志中记录图片 base64、原始图片内容或签名下载地址。
- 模型 cache 使用持久化磁盘，避免每次部署重新下载。
- 输出 ZIP 设置过期清理策略。
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_layering_service.py -v`

Expected: PASS，包含 Qwen fake pipeline 测试通过。

- [ ] **Step 5: 提交**

```bash
git add src/pixelator/layering_service/backends.py docs/layer-split-aliyun.md tests/test_layering_service.py
git commit -m "Add self hosted Qwen layer backend"
```

---

### Task 7: 端到端验证、文档收口与回归测试

**Files:**
- Modify: `README.md`
- Test: full test suite

- [ ] **Step 1: 写 README 更新片段**

在 `README.md` 的 Desktop GUI 之前加入：

```markdown
## AI Layer Split CLI

`pixelator-layer` splits AI art images through a cloud layer service and writes one ZIP per source image. The ZIP contains transparent PNG layers, `manifest.json`, and `preview/composite.png`.

```powershell
$env:PIXELATOR_LAYER_API_KEY="your-service-token"
pixelator-layer split .\inputs --out .\outputs\layers --endpoint https://your-layer-service --overwrite
```

The default Pixelator install does not bundle Qwen model weights or GPU dependencies. See `docs/layer-split-aliyun.md` for the Alibaba Cloud deployment path.
```

- [ ] **Step 2: 运行局部测试**

Run: `python -m pytest tests/test_layering_types.py tests/test_layering_archive.py tests/test_layering_client.py tests/test_layering_cli.py tests/test_layering_service.py -v`

Expected: PASS，所有拆图层相关测试通过。

- [ ] **Step 3: 运行全量测试**

Run: `python -m pytest -v`

Expected: PASS，现有 Pixelator 渲染、GUI、调色板、视频和新增拆图层测试都通过。

- [ ] **Step 4: 检查包入口**

Run: `python -m pixelator.layering.cli --help`

Expected: 输出 `pixelator-layer` 帮助文本，包含 `split` 子命令。

Run: `python -m pixelator.layering.cli split --help`

Expected: 输出 `split` 参数，包含 `--endpoint`、`--api-key-env`、`--layers`、`--overwrite`。

- [ ] **Step 5: 提交**

```bash
git add README.md
git commit -m "Document layer split CLI usage"
```

---

## 自查结果

**规格覆盖：**
- 本地 CLI、文件夹批处理、API key env、超时、轮询、失败汇总：Task 3、Task 4。
- ZIP、PNG layers、manifest、preview、bbox、alpha 裁切：Task 1、Task 2。
- 云端稳定 HTTP 合约：Task 3、Task 5。
- 阿里云/百炼双路径与 Qwen 自托管：Task 5、Task 6。
- 默认 Pixelator 不携带 GPU 依赖：Task 5 使用 `layer-cloud` 可选依赖，Task 6 懒加载 Qwen 依赖。
- 测试与端到端验证：Task 1 至 Task 7。

**占位符扫描：**
- 本计划不包含待补内容标记。
- 每个任务都有明确文件、测试、实现、验证命令和提交点。

**类型一致性：**
- `LayerManifest`、`LayerInfo`、`SourceInfo` 在 Task 1 定义，后续 archive/client/service 均复用。
- `LayerRequest` 在 Task 5 定义，Task 6 的 Qwen 后端复用同一参数对象。
- `ErrorCode` 和 `JobStatus` 在 Task 1 定义，client 和 service 均复用。
