from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def config_value(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value is not None and value.strip():
        return value.strip()
    return local_env_values().get(name, default).strip()


def save_local_env_value(name: str, value: str) -> Path:
    clean_name = name.strip()
    clean_value = value.strip()
    if not clean_name or not clean_name.replace("_", "").isalnum() or clean_name[0].isdigit():
        raise ValueError("Environment variable names must use letters, numbers, and underscores.")
    if not clean_value:
        raise ValueError(f"{clean_name} cannot be empty.")
    if "\n" in clean_value or "\r" in clean_value:
        raise ValueError(f"{clean_name} cannot contain line breaks.")

    env_path = _env_write_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    updated_lines: list[str] = []
    replaced = False
    for line in lines:
        stripped = line.strip()
        key = stripped.split("=", 1)[0].strip() if "=" in stripped else ""
        if key == clean_name:
            if not replaced:
                updated_lines.append(f"{clean_name}={clean_value}")
                replaced = True
            continue
        updated_lines.append(line)
    if not replaced:
        updated_lines.append(f"{clean_name}={clean_value}")

    env_path.write_text("\n".join(updated_lines).rstrip() + "\n", encoding="utf-8")
    os.environ[clean_name] = clean_value
    local_env_values.cache_clear()
    return env_path


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


def _env_write_path() -> Path:
    explicit = os.environ.get("PIXELATOR_ENV_FILE", "").strip()
    return Path(explicit) if explicit else Path.cwd() / ".env.local"
