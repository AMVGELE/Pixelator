import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from pixelator.layering.types import JobStatus
from pixelator.layering_service.backends import (
    LayerBackend,
    LayerRequest,
    MockLayerBackend,
    SelfHostedQwenLayerBackend,
)
from pixelator.layering_service.jobs import JobStore

_UPLOAD_CHUNK_SIZE = 1024 * 1024
_UPLOAD_SUFFIXES = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


def create_app(
    api_token: str | None = None,
    backend: LayerBackend | None = None,
    work_dir: str | Path | None = None,
) -> Any:
    try:
        from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
        from fastapi.responses import FileResponse
    except ImportError as exc:
        raise RuntimeError(
            "pixelator.layering_service requires the layer-cloud optional dependencies"
        ) from exc

    token = api_token or os.environ.get("PIXELATOR_LAYER_SERVICE_TOKEN") or "dev-token"
    max_upload_bytes = _max_upload_bytes()
    temporary_work_dir: tempfile.TemporaryDirectory[str] | None = None
    if work_dir is None:
        temporary_work_dir = tempfile.TemporaryDirectory(prefix="pixelator-layer-service-")
        service_work_dir = Path(temporary_work_dir.name)
    else:
        service_work_dir = Path(work_dir)
        service_work_dir.mkdir(parents=True, exist_ok=True)

    store = JobStore(service_work_dir, backend or select_layer_backend())
    app = FastAPI(title="Pixelator Layer Service", version="0.1.0")
    app.state.job_store = store
    if temporary_work_dir is not None:
        app.state.temporary_work_dir = temporary_work_dir

    def require_auth(authorization: str | None) -> None:
        if authorization != f"Bearer {token}":
            raise HTTPException(
                status_code=401,
                detail="missing or invalid bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    async def write_upload(upload: UploadFile, destination: Path) -> None:
        total_bytes = 0
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with destination.open("wb") as handle:
                while chunk := await upload.read(_UPLOAD_CHUNK_SIZE):
                    total_bytes += len(chunk)
                    if total_bytes > max_upload_bytes:
                        raise HTTPException(status_code=413, detail="uploaded image exceeds size limit")
                    handle.write(chunk)
        except HTTPException:
            _unlink_if_exists(destination)
            raise

    @app.post("/v1/layer-splits")
    async def submit_layer_split(
        image: UploadFile = File(...),
        request: str = Form("{}"),
        authorization: str | None = Header(default=None),
    ) -> dict[str, str]:
        require_auth(authorization)
        try:
            layer_request = _parse_layer_request(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        source_path = service_work_dir / "uploads" / f"{uuid.uuid4().hex}{_safe_upload_suffix(image.filename)}"
        await write_upload(image, source_path)

        job = store.create_and_run(source_path, layer_request)
        return {"job_id": job.id, "status": job.status.value}

    @app.get("/v1/layer-splits/{job_id}")
    def get_layer_split(
        job_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, str]:
        require_auth(authorization)
        job = store.get(job_id)
        if job is None:
            return {"job_id": job_id, "status": JobStatus.UNKNOWN.value}

        payload = {"job_id": job.id, "status": job.status.value}
        if job.status == JobStatus.SUCCEEDED:
            payload["artifact_url"] = f"/v1/layer-splits/{job.id}/artifact"
        if job.status == JobStatus.FAILED and job.error:
            payload["error"] = job.error
        return payload

    @app.get("/v1/layer-splits/{job_id}/artifact")
    def get_layer_split_artifact(
        job_id: str,
        authorization: str | None = Header(default=None),
    ) -> Any:
        require_auth(authorization)
        job = store.get(job_id)
        if job is None or job.status != JobStatus.SUCCEEDED or not job.artifact_path.exists():
            raise HTTPException(status_code=404, detail="layer split artifact not found")

        return FileResponse(
            job.artifact_path,
            media_type="application/zip",
            filename=f"{job.id}.zip",
        )

    return app


def main() -> int:
    token = os.environ.get("PIXELATOR_LAYER_SERVICE_TOKEN")
    if not token:
        raise RuntimeError("PIXELATOR_LAYER_SERVICE_TOKEN must be set to run pixelator-layer-service")

    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError(
            "pixelator-layer-service requires the layer-cloud optional dependencies"
        ) from exc

    port = int(os.environ.get("PIXELATOR_LAYER_SERVICE_PORT", "8000"))
    uvicorn.run(
        create_app(api_token=token, backend=select_layer_backend()),
        host="0.0.0.0",
        port=port,
    )
    return 0


def select_layer_backend() -> LayerBackend:
    backend_name = os.environ.get("PIXELATOR_LAYER_BACKEND", "mock").strip().lower()
    if backend_name in {"", "mock"}:
        return MockLayerBackend()
    if backend_name in {"qwen-self-hosted", "aliyun-self-hosted"}:
        return SelfHostedQwenLayerBackend()

    raise RuntimeError(
        "PIXELATOR_LAYER_BACKEND must be one of: mock, qwen-self-hosted, aliyun-self-hosted"
    )


def _parse_layer_request(request_json: str) -> LayerRequest:
    try:
        data = json.loads(request_json or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("request must be valid JSON") from exc

    if not isinstance(data, dict):
        raise ValueError("request must be a JSON object")

    target_layers = data.get("target_layers")
    if target_layers is not None and (isinstance(target_layers, bool) or not isinstance(target_layers, int)):
        raise ValueError("target_layers must be an integer or null")

    crop_alpha = data.get("crop_alpha", True)
    if not isinstance(crop_alpha, bool):
        raise ValueError("crop_alpha must be a boolean")

    zip_result = data.get("zip_result", True)
    if not isinstance(zip_result, bool):
        raise ValueError("zip_result must be a boolean")

    return LayerRequest(target_layers=target_layers, crop_alpha=crop_alpha, zip_result=zip_result)


def _max_upload_bytes() -> int:
    raw_value = os.environ.get("PIXELATOR_LAYER_SERVICE_MAX_UPLOAD_MB", "64")
    try:
        megabytes = int(raw_value)
    except ValueError as exc:
        raise RuntimeError("PIXELATOR_LAYER_SERVICE_MAX_UPLOAD_MB must be an integer") from exc

    if megabytes < 0:
        raise RuntimeError("PIXELATOR_LAYER_SERVICE_MAX_UPLOAD_MB must be non-negative")
    return megabytes * 1024 * 1024


def _safe_upload_suffix(file_name: str | None) -> str:
    name = (file_name or "").replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    suffix = Path(name).suffix.lower()
    if suffix in _UPLOAD_SUFFIXES:
        return suffix
    return ".bin"


def _unlink_if_exists(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
