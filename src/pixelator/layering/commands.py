from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


def discover_images(input_path: str | Path) -> list[Path]:
    path = Path(input_path)
    if path.is_dir():
        return iter_image_files(path)
    if path.is_file() and is_image_path(path):
        return [path]
    return []


def output_zip_path(source_path: str | Path, output_dir: str | Path) -> Path:
    source = Path(source_path)
    return Path(output_dir) / f"{source.stem}-layers.zip"


def split_path(options: SplitOptions) -> int:
    output_dir = Path(options.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    images = discover_images(options.input_path)
    items: list[dict[str, Any]] = []
    succeeded = 0
    failed = 0

    client = None
    if images:
        client = LayerSplitClient(
            endpoint=options.endpoint,
            api_key=options.api_key,
            poll_interval=options.poll_interval,
            timeout=options.timeout,
        )

    for image_path in images:
        destination = output_zip_path(image_path, output_dir)
        item: dict[str, Any] = {
            "source": str(image_path),
            "output": str(destination),
        }

        if destination.exists() and not options.overwrite:
            item.update(
                {
                    "status": "failed",
                    "error_code": "OUTPUT_EXISTS",
                    "error": f"output already exists: {destination}",
                }
            )
            failed += 1
            items.append(item)
            if options.fail_fast:
                break
            continue

        try:
            if client is None:
                raise RuntimeError("layer split client was not initialized")
            client.split_image(image_path, destination, target_layers=options.target_layers)
        except LayeringError as exc:
            item.update(
                {
                    "status": "failed",
                    "error_code": exc.code.value,
                    "error": str(exc),
                }
            )
            if exc.request_id:
                item["request_id"] = exc.request_id
            failed += 1
        except Exception as exc:
            item.update(
                {
                    "status": "failed",
                    "error_code": "UNEXPECTED_ERROR",
                    "error": str(exc),
                }
            )
            failed += 1
        else:
            item["status"] = "succeeded"
            succeeded += 1

        items.append(item)
        if item["status"] == "failed" and options.fail_fast:
            break

    summary = {
        "input": str(options.input_path),
        "output_dir": str(output_dir),
        "total": len(images),
        "succeeded": succeeded,
        "failed": failed,
        "items": items,
    }
    (output_dir / "batch-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return 0 if images and failed == 0 else 1
