from __future__ import annotations

from dataclasses import asdict

from pixelator.ai.constants import (
    ART_STYLE_PROMPT_PARTS,
    ASSET_TYPE_PROMPT_PARTS,
    BACKGROUND_PROMPT_PARTS,
    BASE_NEGATIVE_PROMPT_PARTS,
    GAME_GENRE_PROMPT_PARTS,
    VIEW_PROMPT_PARTS,
)
from pixelator.ai.types import AiGenerationRequest, PromptResult, StyleProfile


def build_prompt(request: AiGenerationRequest) -> PromptResult:
    request.validate()
    profile_parts = _build_style_profile_parts(request.style_profile.clean())
    positive_parts = _compact_parts(
        [
            ART_STYLE_PROMPT_PARTS[request.style],
            ASSET_TYPE_PROMPT_PARTS[request.asset_type],
            _normalize_description(request.description),
            GAME_GENRE_PROMPT_PARTS[request.game_genre],
            VIEW_PROMPT_PARTS[request.view],
            BACKGROUND_PROMPT_PARTS[request.background],
            f"目标尺寸 {request.size}",
            "清晰轮廓，clean outline",
            "游戏可用素材，game-ready asset",
            "统一视觉语言，consistent visual language",
            *profile_parts["positive"],
        ]
    )
    negative_parts = _compact_parts(
        [
            *BASE_NEGATIVE_PROMPT_PARTS,
            request.background != "scene" and "杂乱场景背景",
            request.background == "transparent" and "白色背景",
            request.background == "transparent" and "假透明背景",
            request.background == "transparent" and "棋盘格背景",
            *profile_parts["negative"],
        ]
    )
    return PromptResult(
        positive_prompt=_join_unique(positive_parts),
        negative_prompt=_join_unique(negative_parts),
        applied_style_profile=profile_parts["applied"],
    )


def _build_style_profile_parts(profile: StyleProfile) -> dict[str, list[str]]:
    fields = asdict(profile)
    positive = _compact_parts(
        [
            fields["project_name"] and f"项目风格参考：{fields['project_name']}",
            fields["palette"] and f"配色方案：{fields['palette']}",
            fields["line_style"] and f"线条风格：{fields['line_style']}",
            fields["lighting"] and f"光照规则：{fields['lighting']}",
            fields["view_rule"] and f"项目视角规则：{fields['view_rule']}",
        ]
    )
    negative = _compact_parts([fields["avoid_elements"]])
    return {
        "positive": positive,
        "negative": negative,
        "applied": [*positive, *[f"避免元素：{part}" for part in negative]],
    }


def _normalize_description(description: str) -> str:
    return " ".join(description.strip().split())


def _compact_parts(parts: list[str | bool | None]) -> list[str]:
    compacted: list[str] = []
    for part in parts:
        if isinstance(part, str) and part.strip():
            compacted.append(part.strip())
    return compacted


def _join_unique(parts: list[str]) -> str:
    seen: set[str] = set()
    unique_parts: list[str] = []
    for part in parts:
        if part not in seen:
            unique_parts.append(part)
            seen.add(part)
    return ", ".join(unique_parts)
