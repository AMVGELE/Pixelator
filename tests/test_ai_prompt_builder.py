import pytest

from pixelator.ai.prompt_builder import build_prompt
from pixelator.ai.types import AiGenerationRequest, StyleProfile


def test_prompt_builder_includes_asset_style_background_and_profile():
    prompt = build_prompt(
        AiGenerationRequest(
            description="Fire slime monster",
            asset_type="character",
            style="pixel_art",
            game_genre="rpg",
            view="front",
            size="128x128",
            background="transparent",
            style_profile=StyleProfile(
                project_name="Lava Caves",
                palette="red, black, amber",
                avoid_elements="photorealistic texture",
            ),
        )
    )

    assert "Fire slime monster" in prompt.positive_prompt
    assert "pixel art" in prompt.positive_prompt
    assert "transparent PNG" in prompt.positive_prompt
    assert "项目风格参考：Lava Caves" in prompt.positive_prompt
    assert "photorealistic texture" in prompt.negative_prompt
    assert "白色背景" in prompt.negative_prompt


def test_prompt_builder_rejects_unknown_choice():
    with pytest.raises(ValueError, match="asset_type"):
        build_prompt(AiGenerationRequest(description="Fire slime", asset_type="bad"))


def test_prompt_builder_supports_last_protocol_realism_style():
    prompt = build_prompt(
        AiGenerationRequest(
            description="Loop 1 spaceship bridge with damaged cable and protocol button",
            asset_type="background",
            style="last_protocol_realism",
            game_genre="puzzle",
            view="front",
            size="2048x1152",
            background="scene",
        )
    )

    assert "Loop 1 spaceship bridge" in prompt.positive_prompt
    assert "hard sci-fi realism" in prompt.positive_prompt
    assert "cinematic hard sci-fi concept art" in prompt.positive_prompt
    assert "realistic materials" in prompt.positive_prompt
    assert "anime" in prompt.negative_prompt
    assert "cartoon" in prompt.negative_prompt
    assert "chibi" in prompt.negative_prompt
    assert "鐪熷疄鐓х墖璐ㄦ劅" not in prompt.negative_prompt
