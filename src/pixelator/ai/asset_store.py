from __future__ import annotations

import json
import re
import time
from dataclasses import asdict
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

from pixelator.ai.types import AiAssetRecord, AiGenerationRequest, DownloadedImage, PromptResult


class AssetStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.index_path = self.directory / "assets.json"

    def save_assets(
        self,
        request: AiGenerationRequest,
        prompt: PromptResult,
        images: list[DownloadedImage],
    ) -> list[AiAssetRecord]:
        self.directory.mkdir(parents=True, exist_ok=True)
        batch_id = f"batch_{time.time_ns():x}"
        batch_code = batch_id[-6:]
        created_at = datetime.now(UTC).isoformat()
        records: list[AiAssetRecord] = []
        for index, image in enumerate(images, start=1):
            name = _build_asset_name(request.description, index, batch_code)
            image_path = self.directory / f"{name}.png"
            self._write_png(image.data, image_path, request.target_dimensions)
            records.append(
                AiAssetRecord(
                    id=f"asset_{uuid4().hex}",
                    batch_id=batch_id,
                    name=name,
                    asset_type=request.asset_type,
                    style=request.style,
                    game_genre=request.game_genre,
                    view=request.view,
                    size=request.size,
                    background=request.background,
                    prompt=prompt.positive_prompt,
                    negative_prompt=prompt.negative_prompt,
                    image_path=image_path,
                    created_at=created_at,
                    source_url=image.source_url,
                    seed=image.seed,
                )
            )
        self._write_records([*self.load_records(), *records])
        return records

    def load_records(self) -> list[AiAssetRecord]:
        if not self.index_path.exists():
            return []
        try:
            raw_records = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        records: list[AiAssetRecord] = []
        if not isinstance(raw_records, list):
            return records
        for raw in raw_records:
            if not isinstance(raw, dict):
                continue
            try:
                image_path = Path(str(raw["image_path"]))
                if not image_path.is_absolute():
                    image_path = self.directory / image_path
                if not image_path.exists():
                    continue
                records.append(
                    AiAssetRecord(
                        id=str(raw["id"]),
                        batch_id=str(raw["batch_id"]),
                        name=str(raw["name"]),
                        asset_type=str(raw["asset_type"]),
                        style=str(raw["style"]),
                        game_genre=str(raw["game_genre"]),
                        view=str(raw["view"]),
                        size=str(raw["size"]),
                        background=str(raw["background"]),
                        prompt=str(raw["prompt"]),
                        negative_prompt=str(raw["negative_prompt"]),
                        image_path=image_path,
                        created_at=str(raw["created_at"]),
                        source_url=_optional_string(raw.get("source_url")),
                        seed=_optional_string(raw.get("seed")),
                    )
                )
            except KeyError:
                continue
        return records

    def _write_records(self, records: list[AiAssetRecord]) -> None:
        payload = [_record_to_json(record, self.directory) for record in records]
        self.index_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _write_png(self, data: bytes, path: Path, target_dimensions: tuple[int, int]) -> None:
        try:
            image = Image.open(BytesIO(data))
        except UnidentifiedImageError as exc:
            raise ValueError("Generated image could not be decoded.") from exc
        image = image.convert("RGBA")
        if image.size != target_dimensions:
            image = image.resize(target_dimensions, Image.Resampling.LANCZOS)
        image.save(path, format="PNG")


def _record_to_json(record: AiAssetRecord, directory: Path) -> dict[str, object]:
    payload = asdict(record)
    try:
        payload["image_path"] = record.image_path.relative_to(directory).as_posix()
    except ValueError:
        payload["image_path"] = str(record.image_path)
    return payload


def _build_asset_name(description: str, index: int, batch_code: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", description.strip().lower())
    slug = slug.strip("_")[:40] or "asset"
    return f"{slug}_{index}_{batch_code}"


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
