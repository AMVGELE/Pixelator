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
from pixelator.layering_service.backends import LayerRequest, MockLayerBackend, SelfHostedQwenLayerBackend


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
    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        image = kwargs["image"].convert("RGBA")
        transparent = Image.new("RGBA", image.size, (0, 0, 0, 0))
        return FakeQwenOutput([image, transparent])


def test_self_hosted_qwen_backend_uses_injected_pipeline(tmp_path: Path):
    source = tmp_path / "hero.png"
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(source)
    factory_calls = 0
    pipeline = FakeQwenPipeline()

    def pipeline_factory():
        nonlocal factory_calls
        factory_calls += 1
        return pipeline

    backend = SelfHostedQwenLayerBackend(pipeline_factory=pipeline_factory)

    manifest = backend.split(source, tmp_path / "artifact.zip", LayerRequest(target_layers=2))
    second_manifest = backend.split(source, tmp_path / "artifact-2.zip", LayerRequest(target_layers=2))

    assert backend.backend_name == "aliyun-self-hosted"
    assert manifest.model.model_id == "Qwen/Qwen-Image-Layered"
    assert second_manifest.model.model_id == "Qwen/Qwen-Image-Layered"
    assert len(manifest.layers) == 2
    assert (tmp_path / "artifact.zip").exists()
    assert factory_calls == 1
    assert len(pipeline.calls) == 2
    assert pipeline.calls[0]["layers"] == 2
    assert pipeline.calls[0]["resolution"] == 640
    assert pipeline.calls[0]["num_inference_steps"] == 50
    assert pipeline.calls[0]["true_cfg_scale"] == 4.0
    assert pipeline.calls[0]["cfg_normalize"] is True
    assert pipeline.calls[0]["use_en_prompt"] is True


def test_self_hosted_qwen_backend_rejects_empty_pipeline_output():
    output = types.SimpleNamespace(images=[])

    with pytest.raises(RuntimeError, match="Qwen pipeline output"):
        SelfHostedQwenLayerBackend._extract_layers(output)


def test_self_hosted_qwen_default_factory_uses_layered_pipeline(monkeypatch):
    calls = {}

    class FakeCuda:
        @staticmethod
        def is_available():
            return True

    fake_torch = types.SimpleNamespace(bfloat16="bfloat16", cuda=FakeCuda())

    class FakeQwenImageLayeredPipeline:
        @classmethod
        def from_pretrained(cls, model_id, torch_dtype=None):
            calls["model_id"] = model_id
            calls["torch_dtype"] = torch_dtype
            return cls()

        def to(self, device):
            calls["device"] = device
            return self

    fake_diffusers = types.SimpleNamespace(QwenImageLayeredPipeline=FakeQwenImageLayeredPipeline)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "diffusers", fake_diffusers)

    backend = SelfHostedQwenLayerBackend()

    assert backend.pipeline is backend.pipeline
    assert calls == {
        "model_id": "Qwen/Qwen-Image-Layered",
        "torch_dtype": "bfloat16",
        "device": "cuda",
    }


def test_layer_service_selects_backend_from_environment(monkeypatch):
    import pixelator.layering_service.app as app_module

    monkeypatch.delenv("PIXELATOR_LAYER_BACKEND", raising=False)
    assert isinstance(app_module.select_layer_backend(), MockLayerBackend)

    monkeypatch.setenv("PIXELATOR_LAYER_BACKEND", "mock")
    assert isinstance(app_module.select_layer_backend(), MockLayerBackend)

    monkeypatch.setenv("PIXELATOR_LAYER_BACKEND", "qwen-self-hosted")
    assert isinstance(app_module.select_layer_backend(), SelfHostedQwenLayerBackend)

    monkeypatch.setenv("PIXELATOR_LAYER_BACKEND", "aliyun-self-hosted")
    assert isinstance(app_module.select_layer_backend(), SelfHostedQwenLayerBackend)


def test_layer_service_rejects_unknown_backend(monkeypatch):
    import pixelator.layering_service.app as app_module

    monkeypatch.setenv("PIXELATOR_LAYER_BACKEND", "surprise")

    with pytest.raises(RuntimeError, match="PIXELATOR_LAYER_BACKEND"):
        app_module.select_layer_backend()


def test_create_app_uses_environment_backend_when_not_injected(monkeypatch, tmp_path: Path):
    from pixelator.layering_service.app import create_app

    monkeypatch.setenv("PIXELATOR_LAYER_BACKEND", "qwen-self-hosted")

    app = create_app(api_token="secret", work_dir=tmp_path)

    assert isinstance(app.state.job_store.backend, SelfHostedQwenLayerBackend)


def test_create_app_prefers_injected_backend_over_environment(monkeypatch, tmp_path: Path):
    from pixelator.layering_service.app import create_app

    injected_backend = MockLayerBackend()
    monkeypatch.setenv("PIXELATOR_LAYER_BACKEND", "qwen-self-hosted")

    app = create_app(api_token="secret", backend=injected_backend, work_dir=tmp_path)

    assert app.state.job_store.backend is injected_backend


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


def test_layer_service_main_uses_selected_backend(monkeypatch):
    import pixelator.layering_service.app as app_module

    selected_backend = MockLayerBackend()
    calls = {}

    def fake_select_layer_backend():
        calls["selected"] = True
        return selected_backend

    def fake_run(app, **kwargs):
        calls["backend"] = app.state.job_store.backend
        calls["port"] = kwargs["port"]

    monkeypatch.setenv("PIXELATOR_LAYER_SERVICE_TOKEN", "secret")
    monkeypatch.setenv("PIXELATOR_LAYER_SERVICE_PORT", "8123")
    monkeypatch.setattr(app_module, "select_layer_backend", fake_select_layer_backend)
    monkeypatch.setitem(sys.modules, "uvicorn", types.SimpleNamespace(run=fake_run))

    assert app_module.main() == 0
    assert calls == {"selected": True, "backend": selected_backend, "port": 8123}


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
