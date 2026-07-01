from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from pixelator.ai.constants import (
    ASSET_SIZES,
    ASSET_TYPES,
    ASSET_VIEWS,
    ART_STYLES,
    BACKGROUND_MODES,
    DEFAULT_DASHSCOPE_IMAGE_ENDPOINT,
    DEFAULT_DASHSCOPE_TASK_ENDPOINT,
    DEFAULT_IMAGE_MODEL,
    DEFAULT_TASK_POLL_ATTEMPTS,
    DEFAULT_TASK_POLL_INTERVAL_SECONDS,
    GAME_GENRES,
)


@dataclass(frozen=True)
class StyleProfile:
    project_name: str = ""
    palette: str = ""
    line_style: str = ""
    lighting: str = ""
    view_rule: str = ""
    avoid_elements: str = ""

    def clean(self) -> StyleProfile:
        return StyleProfile(**{key: _clean_text(value) for key, value in asdict(self).items()})


@dataclass(frozen=True)
class AiGenerationRequest:
    description: str
    asset_type: str = "character"
    style: str = "pixel_art"
    game_genre: str = "rpg"
    view: str = "front"
    size: str = "128x128"
    background: str = "transparent"
    count: int = 1
    style_profile: StyleProfile = field(default_factory=StyleProfile)

    def validate(self) -> None:
        if len(_clean_text(self.description)) < 2:
            raise ValueError("Description must be at least 2 characters.")
        _validate_choice("asset_type", self.asset_type, ASSET_TYPES)
        _validate_choice("style", self.style, ART_STYLES)
        _validate_choice("game_genre", self.game_genre, GAME_GENRES)
        _validate_choice("view", self.view, ASSET_VIEWS)
        if self.size not in ASSET_SIZES:
            _validate_dynamic_size(self.size)
        _validate_choice("background", self.background, BACKGROUND_MODES)
        if self.count < 1 or self.count > 6:
            raise ValueError("Count must be between 1 and 6.")

    @property
    def target_dimensions(self) -> tuple[int, int]:
        return _parse_size(self.size)


@dataclass(frozen=True)
class PromptResult:
    positive_prompt: str
    negative_prompt: str
    applied_style_profile: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DashScopeConfig:
    api_key: str = ""
    model: str = DEFAULT_IMAGE_MODEL
    image_endpoint: str = DEFAULT_DASHSCOPE_IMAGE_ENDPOINT
    task_endpoint: str = DEFAULT_DASHSCOPE_TASK_ENDPOINT
    poll_attempts: int = DEFAULT_TASK_POLL_ATTEMPTS
    poll_interval_seconds: float = DEFAULT_TASK_POLL_INTERVAL_SECONDS
    timeout_seconds: float = 60.0


@dataclass(frozen=True)
class DownloadedImage:
    data: bytes
    source_url: str | None = None
    seed: str | None = None


@dataclass(frozen=True)
class AiAssetRecord:
    id: str
    batch_id: str
    name: str
    asset_type: str
    style: str
    game_genre: str
    view: str
    size: str
    background: str
    prompt: str
    negative_prompt: str
    image_path: Path
    created_at: str
    source_url: str | None = None
    seed: str | None = None


def _validate_choice(field_name: str, value: str, choices: tuple[str, ...]) -> None:
    if value not in choices:
        raise ValueError(f"{field_name} must be one of: {', '.join(choices)}.")


def _validate_dynamic_size(value: str) -> None:
    width, height = _parse_size(value)
    if width <= 0 or height <= 0:
        raise ValueError("size dimensions must be positive.")
    if width % 16 != 0 or height % 16 != 0:
        raise ValueError("size dimensions must use 16 pixel steps.")
    pixels = width * height
    if pixels < 512 * 512 or pixels > 2048 * 2048:
        raise ValueError("size total pixels must be between 512x512 and 2048x2048.")


def _parse_size(value: str) -> tuple[int, int]:
    try:
        width, height = [int(part) for part in value.lower().split("x", 1)]
    except (TypeError, ValueError):
        raise ValueError("size must use WIDTHxHEIGHT format.") from None
    return width, height


def _clean_text(value: str) -> str:
    return " ".join(value.strip().split())
