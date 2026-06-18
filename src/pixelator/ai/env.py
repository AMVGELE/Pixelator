from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def config_value(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value is not None and value.strip():
        return value.strip()
    return local_env_values().get(name, default).strip()


@lru_cache(maxsize=1)
def local_env_values() -> dict[str, str]:
    env_path = _env_path()
    if env_path is None:
        return {}
    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        value = raw_value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _env_path() -> Path | None:
    explicit = os.environ.get("PIXELATOR_ENV_FILE", "").strip()
    candidates = [Path(explicit)] if explicit else []
    candidates.append(Path.cwd() / ".env.local")
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None
