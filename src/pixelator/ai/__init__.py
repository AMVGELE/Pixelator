"""AI asset generation support for Pixelator."""

from pixelator.ai.asset_store import AssetStore
from pixelator.ai.background_removal import BackgroundRemovalError
from pixelator.ai.dashscope_client import DashScopeClient, DashScopeError
from pixelator.ai.prompt_builder import build_prompt
from pixelator.ai.types import (
    AiAssetRecord,
    AiGenerationRequest,
    DashScopeConfig,
    DownloadedImage,
    PromptResult,
    StyleProfile,
)

__all__ = [
    "AiAssetRecord",
    "AiGenerationRequest",
    "AssetStore",
    "BackgroundRemovalError",
    "DashScopeClient",
    "DashScopeConfig",
    "DashScopeError",
    "DownloadedImage",
    "PromptResult",
    "StyleProfile",
    "build_prompt",
]
