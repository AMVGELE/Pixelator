from __future__ import annotations

import hashlib
import json
import zipfile
from io import BytesIO
from pathlib import Path

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


def compose_preview(
    canvas_size: tuple[int, int],
    layers: list[Image.Image],
    bboxes: list[tuple[int, int, int, int]],
) -> Image.Image:
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
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    source_rgba = source_image.convert("RGBA")
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
        prepared_layers.append(prepared)
        bboxes.append(bbox)
        layer_infos.append(
            LayerInfo(
                id=layer_id,
                name=layer_id,
                file=f"layers/{layer_id}.png",
                order=index - 1,
                bbox=bbox,
                width=prepared.width,
                height=prepared.height,
            )
        )

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

    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for prepared, info in zip(prepared_layers, layer_infos, strict=True):
            archive.writestr(info.file, _png_bytes(prepared))

        preview = compose_preview(source_rgba.size, prepared_layers, bboxes)
        archive.writestr(manifest.preview.file, _png_bytes(preview))
        archive.writestr(
            "manifest.json",
            json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False).encode("utf-8"),
        )

    return manifest


def validate_layer_zip(path: str | Path) -> LayerManifest:
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if "manifest.json" not in names:
                raise LayeringError(ErrorCode.ARTIFACT_INVALID, "layer ZIP is missing manifest.json")

            try:
                manifest_data = json.loads(archive.read("manifest.json").decode("utf-8"))
            except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise LayeringError(ErrorCode.ARTIFACT_INVALID, "layer ZIP manifest is invalid JSON") from exc

            manifest = LayerManifest.from_dict(manifest_data)
            _require_safe_artifact_path(manifest.preview.file, "preview/")
            _require_zip_member(names, manifest.preview.file)
            for layer in manifest.layers:
                _require_safe_artifact_path(layer.file, "layers/")
                _require_zip_member(names, layer.file)

            return manifest
    except zipfile.BadZipFile as exc:
        raise LayeringError(ErrorCode.ARTIFACT_INVALID, "layer ZIP is not a valid ZIP archive") from exc
    except OSError as exc:
        raise LayeringError(ErrorCode.ARTIFACT_INVALID, f"cannot read layer ZIP: {path}") from exc


def _png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _require_zip_member(names: set[str], member: str) -> None:
    if member not in names:
        raise LayeringError(ErrorCode.ARTIFACT_INVALID, f"layer ZIP is missing required file: {member}")


def _require_safe_artifact_path(member: str, required_prefix: str) -> None:
    parts = member.split("/")
    if (
        not member.startswith(required_prefix)
        or member.startswith("/")
        or any(_has_windows_drive(part) for part in parts)
        or "\\" in member
        or ".." in parts
        or "" in parts
    ):
        raise LayeringError(ErrorCode.ARTIFACT_INVALID, f"unsafe artifact path in layer ZIP: {member}")


def _has_windows_drive(member: str) -> bool:
    return len(member) >= 2 and member[0].isalpha() and member[1] == ":"
