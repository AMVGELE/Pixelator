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
