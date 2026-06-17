import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from pixelator.layering.archive import alpha_bbox, validate_layer_zip, write_layer_zip
from pixelator.layering.types import ErrorCode, LayeringError


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


def test_validate_layer_zip_rejects_bad_zip(tmp_path: Path):
    bad_zip = tmp_path / "bad.zip"
    bad_zip.write_bytes(b"not a zip")

    with pytest.raises(LayeringError) as exc_info:
        validate_layer_zip(bad_zip)

    assert exc_info.value.code == ErrorCode.ARTIFACT_INVALID


def test_validate_layer_zip_rejects_manifest_that_is_not_object(tmp_path: Path):
    zip_path = tmp_path / "bad-manifest.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("manifest.json", "null")

    with pytest.raises(LayeringError) as exc_info:
        validate_layer_zip(zip_path)

    assert exc_info.value.code == ErrorCode.ARTIFACT_INVALID


def test_validate_layer_zip_rejects_missing_layer_file(tmp_path: Path):
    zip_path = tmp_path / "missing-layer.zip"
    manifest = {
        "schema_version": 1,
        "source": {"file_name": "hero.png", "width": 8, "height": 6, "sha256": "abc"},
        "model": {"provider": "qwen-image-layered", "backend": "mock", "model_id": "mock"},
        "layers": [
            {
                "id": "layer_001",
                "name": "layer_001",
                "file": "layers/layer_001.png",
                "order": 0,
                "bbox": [0, 0, 8, 6],
                "width": 8,
                "height": 6,
                "opacity": 1.0,
                "blend_mode": "normal",
            }
        ],
        "preview": {"file": "preview/composite.png"},
    }
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("preview/composite.png", b"fake")

    with pytest.raises(LayeringError) as exc_info:
        validate_layer_zip(zip_path)

    assert exc_info.value.code == ErrorCode.ARTIFACT_INVALID
    assert "layers/layer_001.png" in str(exc_info.value)


@pytest.mark.parametrize(
    "layer_file",
    [
        "../escape.png",
        "/absolute/path.png",
        "C:/temp/layer.png",
        "layers\\layer_001.png",
    ],
)
def test_validate_layer_zip_rejects_unsafe_layer_file_path(tmp_path: Path, layer_file: str):
    zip_path = tmp_path / "unsafe-layer-path.zip"
    manifest = _manifest_data(layer_file=layer_file)

    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr(layer_file, b"fake")
        archive.writestr("preview/composite.png", b"fake")

    with pytest.raises(LayeringError) as exc_info:
        validate_layer_zip(zip_path)

    assert exc_info.value.code == ErrorCode.ARTIFACT_INVALID
    assert "unsafe artifact path" in str(exc_info.value)
    assert layer_file in str(exc_info.value)


def test_validate_layer_zip_rejects_preview_file_without_required_prefix(tmp_path: Path):
    zip_path = tmp_path / "unsafe-preview-path.zip"
    preview_file = "composite.png"
    manifest = _manifest_data(preview_file=preview_file)

    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("layers/layer_001.png", b"fake")
        archive.writestr(preview_file, b"fake")

    with pytest.raises(LayeringError) as exc_info:
        validate_layer_zip(zip_path)

    assert exc_info.value.code == ErrorCode.ARTIFACT_INVALID
    assert "unsafe artifact path" in str(exc_info.value)
    assert preview_file in str(exc_info.value)


def _manifest_data(
    layer_file: str = "layers/layer_001.png",
    preview_file: str = "preview/composite.png",
) -> dict:
    return {
        "schema_version": 1,
        "source": {"file_name": "hero.png", "width": 8, "height": 6, "sha256": "abc"},
        "model": {"provider": "qwen-image-layered", "backend": "mock", "model_id": "mock"},
        "layers": [
            {
                "id": "layer_001",
                "name": "layer_001",
                "file": layer_file,
                "order": 0,
                "bbox": [0, 0, 8, 6],
                "width": 8,
                "height": 6,
                "opacity": 1.0,
                "blend_mode": "normal",
            }
        ],
        "preview": {"file": preview_file},
    }
