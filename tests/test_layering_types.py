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


def _layer(**overrides):
    data = {
        "id": "layer_001",
        "name": "layer_001",
        "file": "layers/layer_001.png",
        "order": 0,
        "bbox": (4, 6, 32, 40),
        "width": 32,
        "height": 40,
    }
    data.update(overrides)
    return LayerInfo(**data)


def _manifest(**overrides):
    data = {
        "source": SourceInfo(file_name="hero.png", width=128, height=64, sha256="abc123"),
        "model": ModelInfo(provider="qwen-image-layered", backend="mock", model_id="mock"),
        "layers": [_layer()],
        "preview": PreviewInfo(file="preview/composite.png"),
    }
    data.update(overrides)
    return LayerManifest(**data)


def _layer_data(**overrides):
    data = {
        "id": "layer_001",
        "name": "layer_001",
        "file": "layers/layer_001.png",
        "order": 0,
        "bbox": [4, 6, 32, 40],
        "width": 32,
        "height": 40,
    }
    data.update(overrides)
    return data


def _manifest_data(**overrides):
    data = {
        "schema_version": 1,
        "source": {"file_name": "hero.png", "width": 128, "height": 64, "sha256": "abc123"},
        "model": {"provider": "qwen-image-layered", "backend": "mock", "model_id": "mock"},
        "layers": [_layer_data()],
        "preview": {"file": "preview/composite.png"},
    }
    data.update(overrides)
    return data


def _assert_artifact_invalid(exc_info):
    assert exc_info.value.code == ErrorCode.ARTIFACT_INVALID


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


def test_manifest_rejects_invalid_schema_version():
    data = _manifest_data(schema_version=2)

    with pytest.raises(LayeringError) as exc_info:
        LayerManifest.from_dict(data)

    _assert_artifact_invalid(exc_info)


@pytest.mark.parametrize("data", [None, [], "bad"])
def test_manifest_from_dict_rejects_malformed_top_level_manifest(data):
    with pytest.raises(LayeringError) as exc_info:
        LayerManifest.from_dict(data)

    _assert_artifact_invalid(exc_info)


@pytest.mark.parametrize("schema_version", [True, 1.0])
def test_manifest_from_dict_rejects_non_integer_schema_version(schema_version):
    data = _manifest_data(schema_version=schema_version)

    with pytest.raises(LayeringError) as exc_info:
        LayerManifest.from_dict(data)

    _assert_artifact_invalid(exc_info)


@pytest.mark.parametrize("schema_version", [True, 1.0])
def test_manifest_to_dict_rejects_non_integer_schema_version(schema_version):
    manifest = _manifest(schema_version=schema_version)

    with pytest.raises(LayeringError) as exc_info:
        manifest.to_dict()

    _assert_artifact_invalid(exc_info)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("bbox", (4, 6, 32)),
        ("bbox", (-1, 6, 32, 40)),
        ("bbox", (4, 6, 0, 40)),
        ("width", 0),
        ("height", 0),
        ("order", -1),
        ("opacity", "opaque"),
        ("opacity", 1.5),
        ("blend_mode", ""),
    ],
)
def test_manifest_to_dict_rejects_invalid_layer_fields(field, value):
    manifest = _manifest(layers=[_layer(**{field: value})])

    with pytest.raises(LayeringError) as exc_info:
        manifest.to_dict()

    _assert_artifact_invalid(exc_info)


@pytest.mark.parametrize(
    "override",
    [
        {"source": SourceInfo(file_name="hero.png", width=0, height=64, sha256="abc")},
        {"model": ModelInfo(provider="", backend="mock", model_id="mock")},
        {"preview": PreviewInfo(file="")},
    ],
)
def test_manifest_to_dict_rejects_invalid_metadata_fields(override):
    manifest = _manifest(**override)

    with pytest.raises(LayeringError) as exc_info:
        manifest.to_dict()

    _assert_artifact_invalid(exc_info)


@pytest.mark.parametrize(
    "override",
    [
        {"source": {}},
        {"model": {}},
        {"preview": {}},
    ],
)
def test_manifest_to_dict_rejects_wrong_metadata_object_types(override):
    manifest = _manifest(**override)

    with pytest.raises(LayeringError) as exc_info:
        manifest.to_dict()

    _assert_artifact_invalid(exc_info)


@pytest.mark.parametrize("bbox", [[-1, 6, 32, 40], [4, 6, 0, 40]])
def test_manifest_from_dict_rejects_invalid_bbox_geometry(bbox):
    data = _manifest_data(layers=[_layer_data(bbox=bbox)])

    with pytest.raises(LayeringError) as exc_info:
        LayerManifest.from_dict(data)

    _assert_artifact_invalid(exc_info)


def test_manifest_rejects_duplicate_layer_file():
    data = _manifest_data(
        layers=[
            _layer_data(id="layer_001", file="layers/shared.png", order=0),
            _layer_data(id="layer_002", file="layers/shared.png", order=1),
        ]
    )

    with pytest.raises(LayeringError) as exc_info:
        LayerManifest.from_dict(data)

    _assert_artifact_invalid(exc_info)


def test_manifest_rejects_malformed_layer_entry():
    data = _manifest_data(layers=["bad"])

    with pytest.raises(LayeringError) as exc_info:
        LayerManifest.from_dict(data)

    _assert_artifact_invalid(exc_info)


def test_layering_error_stores_request_id():
    error = LayeringError(ErrorCode.JOB_FAILED, "job failed", request_id="req_123")

    assert error.code == ErrorCode.JOB_FAILED
    assert error.request_id == "req_123"
    assert str(error) == "job failed"
