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
        _validate_choice("size", self.size, ASSET_SIZES)
        _validate_choice("background", self.background, BACKGROUND_MODES)
        if self.count < 1 or self.count > 6:
            raise ValueError("Count must be between 1 and 6.")

    @property
    def target_dimensions(self) -> tuple[int, int]:
        width, height = self.size.split("x", 1)
        return int(width), int(height)


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


def _clean_text(value: str) -> str:
    return " ".join(value.strip().split())
