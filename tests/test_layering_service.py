import io
import os
import subprocess
import sys
import tomllib
import types
from pathlib import Path

import pytest
from PIL import Image

from pixelator.layering.archive import validate_layer_zip
from pixelator.layering_service.backends import LayerRequest, SelfHostedQwenLayerBackend


def _test_client():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    return TestClient


def _png_bytes(size: tuple[int, int] = (4, 4)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", size, (255, 0, 0, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def _post_image(client, filename: str, content: bytes, request: str = "{}"):
    return client.post(
        "/v1/layer-splits",
        headers={"Authorization": "Bearer secret"},
        files={"image": (filename, content, "image/png")},
        data={"request": request},
    )


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


def test_dev_optional_dependencies_include_test_client_runtime():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    optional = pyproject["project"]["optional-dependencies"]

    assert "httpx2>=2.0" in optional["dev"]
    assert "httpx2>=2.0" not in pyproject["project"]["dependencies"]
    assert "httpx2>=2.0" not in optional["layer-cloud"]


def test_cloud_service_accepts_image_and_returns_layer_zip(tmp_path: Path):
    from pixelator.layering_service.app import create_app

    client = _test_client()(create_app(api_token="secret", work_dir=tmp_path))

    response = _post_image(
        client,
        "hero.png",
        _png_bytes(),
        request='{"target_layers": 4, "crop_alpha": true, "zip_result": true}',
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
    assert manifest.source.file_name.endswith(".png")
    assert "/" not in manifest.source.file_name
    assert "\\" not in manifest.source.file_name


def test_cloud_service_rejects_missing_auth(tmp_path: Path):
    from pixelator.layering_service.app import create_app

    client = _test_client()(create_app(api_token="secret", work_dir=tmp_path))

    response = client.get("/v1/layer-splits/missing")

    assert response.status_code == 401


def test_cloud_service_module_importable_without_fastapi_at_module_top():
    project_root = Path(__file__).resolve().parents[1]
    source_root = project_root / "src"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(source_root) + os.pathsep + env.get("PYTHONPATH", "")
    code = """
import importlib.abc
import sys

class Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "fastapi" or fullname.startswith("fastapi.") or fullname == "uvicorn":
            raise ImportError("blocked optional dependency")
        return None

sys.meta_path.insert(0, Blocker())
import pixelator.layering_service.app as app_module
print(callable(app_module.create_app), callable(app_module.main))
"""

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True True"


def test_layer_service_main_requires_explicit_token(monkeypatch):
    import pixelator.layering_service.app as app_module

    fake_uvicorn = types.SimpleNamespace(run=lambda *args, **kwargs: pytest.fail("uvicorn.run should not be called"))
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
    monkeypatch.delenv("PIXELATOR_LAYER_SERVICE_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="PIXELATOR_LAYER_SERVICE_TOKEN"):
        app_module.main()


def test_cloud_service_generates_safe_source_name_for_dangerous_filename(tmp_path: Path):
    from pixelator.layering_service.app import create_app

    client = _test_client()(create_app(api_token="secret", work_dir=tmp_path))

    response = _post_image(client, "../evil.png", _png_bytes())

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    artifact_response = client.get(f"/v1/layer-splits/{job_id}/artifact", headers={"Authorization": "Bearer secret"})
    artifact_path = tmp_path / "artifact.zip"
    artifact_path.write_bytes(artifact_response.content)
    manifest = validate_layer_zip(artifact_path)
    assert manifest.source.file_name != "evil.png"
    assert manifest.source.file_name.endswith(".png")
    assert "/" not in manifest.source.file_name
    assert "\\" not in manifest.source.file_name


def test_cloud_service_rejects_uploads_over_size_limit(monkeypatch, tmp_path: Path):
    from pixelator.layering_service.app import create_app

    monkeypatch.setenv("PIXELATOR_LAYER_SERVICE_MAX_UPLOAD_MB", "0")
    client = _test_client()(create_app(api_token="secret", work_dir=tmp_path))

    response = _post_image(client, "hero.png", _png_bytes())

    assert response.status_code == 413


def test_cloud_service_rejects_invalid_request_json(tmp_path: Path):
    from pixelator.layering_service.app import create_app

    client = _test_client()(create_app(api_token="secret", work_dir=tmp_path))

    response = _post_image(client, "hero.png", _png_bytes(), request="{")

    assert response.status_code == 400
