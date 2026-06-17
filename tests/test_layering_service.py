import io
from pathlib import Path

import pytest
from PIL import Image

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from pixelator.layering.archive import validate_layer_zip
from pixelator.layering_service.app import create_app


def test_cloud_service_accepts_image_and_returns_layer_zip(tmp_path: Path):
    app = create_app(api_token="secret", work_dir=tmp_path)
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


def test_cloud_service_rejects_missing_auth(tmp_path: Path):
    app = create_app(api_token="secret", work_dir=tmp_path)
    client = TestClient(app)

    response = client.get("/v1/layer-splits/missing")

    assert response.status_code == 401


def test_cloud_service_module_importable_without_fastapi_at_module_top():
    # This documents the packaging contract: console script modules must import even
    # when layer-cloud extras are not installed. The actual app creation may require FastAPI.
    import pixelator.layering_service.app as app_module

    assert callable(app_module.create_app)
    assert callable(app_module.main)
