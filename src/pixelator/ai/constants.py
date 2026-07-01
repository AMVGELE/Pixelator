from __future__ import annotations

ASSET_TYPES = ("character", "item", "icon", "tile", "ui", "background")
ART_STYLES = ("pixel_art", "cartoon", "hand_drawn", "dark_fantasy", "chibi")
GAME_GENRES = ("rpg", "platformer", "tower_defense", "roguelike", "puzzle")
ASSET_VIEWS = ("front", "side", "top_down", "isometric")
ASSET_SIZES = ("64x64", "128x128", "256x256", "512x512")
BACKGROUND_MODES = ("transparent", "solid", "scene")

ASSET_TYPE_LABELS = {
    "character": "Character",
    "item": "Item",
    "icon": "Icon",
    "tile": "Tile",
    "ui": "UI Element",
    "background": "Background",
}

ART_STYLE_LABELS = {
    "pixel_art": "Pixel Art",
    "cartoon": "Cartoon",
    "hand_drawn": "Hand Drawn",
    "dark_fantasy": "Dark Fantasy",
    "chibi": "Chibi",
}

GAME_GENRE_LABELS = {
    "rpg": "RPG",
    "platformer": "Platformer",
    "tower_defense": "Tower Defense",
    "roguelike": "Roguelike",
    "puzzle": "Puzzle",
}

VIEW_LABELS = {
    "front": "Front",
    "side": "Side",
    "top_down": "Top Down",
    "isometric": "Isometric",
}

BACKGROUND_LABELS = {
    "transparent": "Transparent",
    "solid": "Solid",
    "scene": "Scene",
}

ASSET_TYPE_PROMPT_PARTS = {
    "character": "2D 游戏角色素材，完整身体，居中构图，清晰剪影，小尺寸可读，game character sprite",
    "item": "2D 游戏道具素材，独立物体，居中构图，轮廓明确，适合背包或掉落物，inventory item",
    "icon": "2D 游戏图标，符号清晰，居中构图，边缘干净，适合 UI 或背包栏，game icon",
    "tile": "2D 地形地块素材，可平铺纹理，顶部表面清晰，适合 tilemap 工作流，seamless tile",
    "ui": "2D 游戏界面元素，形状清晰，适合 HUD 或菜单，game UI asset",
    "background": "2D 游戏背景素材，场景层次清楚，空间深度明确，适合游戏环境，game background",
}

ART_STYLE_PROMPT_PARTS = {
    "pixel_art": "像素风，pixel art，清晰像素，有限色板，无抗锯齿，game sprite aesthetic",
    "cartoon": "卡通风格，cartoon style，粗轮廓，明亮配色，简洁明暗，playful game-ready look",
    "hand_drawn": "手绘风格，hand drawn style，自然线条，柔和质感，illustrated game asset look",
    "dark_fantasy": "暗黑幻想风格，dark fantasy，强烈明暗对比，低饱和配色，精致细节，moody game asset",
    "chibi": "Q 版风格，chibi style，可爱比例，圆润形体，表情明确，compact game asset",
}

GAME_GENRE_PROMPT_PARTS = {
    "rpg": "适合 2D RPG 游戏，作为 RPG 素材易识别",
    "platformer": "适合 2D 平台跳跃游戏，侧向移动场景中易读",
    "tower_defense": "适合塔防游戏，从策略视角观察时轮廓清楚",
    "roguelike": "适合 Roguelike 游戏，紧凑且可重复使用的素材设计",
    "puzzle": "适合解谜游戏，视觉语言简洁易读",
}

VIEW_PROMPT_PARTS = {
    "front": "正面视角，front view，对称展示",
    "side": "侧面视角，side view，适合横版玩法",
    "top_down": "俯视视角，top-down view，从上方观察仍清晰",
    "isometric": "等距视角，isometric view，保持统一 2D 游戏透视",
}

BACKGROUND_PROMPT_PARTS = {
    "transparent": "透明背景，transparent PNG，alpha channel，独立素材，背景必须完全透明，不要白底，不要棋盘格",
    "solid": "纯色背景，plain solid color background，便于抠图",
    "scene": "简洁游戏场景背景，simple game scene background，构图不拥挤",
}

BASE_NEGATIVE_PROMPT_PARTS = (
    "文字",
    "水印",
    "logo",
    "签名",
    "模糊",
    "低分辨率",
    "真实照片质感",
    "复杂背景",
    "主体被裁切",
    "风格不一致",
    "多余肢体",
    "重复物体",
)

DEFAULT_IMAGE_MODEL = "qwen-image-2.0"
DEFAULT_DASHSCOPE_IMAGE_ENDPOINT = (
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
)
DEFAULT_DASHSCOPE_TASK_ENDPOINT = "https://dashscope.aliyuncs.com/api/v1/tasks"
DEFAULT_TASK_POLL_ATTEMPTS = 20
DEFAULT_TASK_POLL_INTERVAL_SECONDS = 3.0

# Project-specific preset for Last Protocol L3 placeholder art. The generic
# Pixelator presets intentionally bias toward sprite/cartoon assets; this one
# keeps Qwen Lab and AI Assets aimed at grounded sci-fi concept art.
ART_STYLES = (*ART_STYLES, "last_protocol_realism")
ART_STYLE_LABELS["last_protocol_realism"] = "Last Protocol Realism"
ART_STYLE_PROMPT_PARTS[
    "last_protocol_realism"
] = (
    "Last Protocol hard sci-fi realism, cinematic hard sci-fi concept art, "
    "realistic industrial spaceship interior or prop, grounded military spacecraft design, "
    "worn metal panels, practical machinery, believable scale, restrained palette, "
    "cinematic lighting, high detail matte painting, realistic materials, "
    "no cute stylization, no cartoon outline"
)

REALISM_BASE_NEGATIVE_EXCLUSIONS = (
    "鐪熷疄鐓х墖璐ㄦ劅",
)

REALISM_NEGATIVE_PROMPT_PARTS = (
    "anime",
    "manga",
    "cartoon",
    "chibi",
    "cute",
    "cel shading",
    "thick outline",
    "flat color",
    "toy-like",
    "colorful mobile game icon",
    "stylized mobile game",
    "fantasy",
    "exaggerated proportions",
    "childish",
    "glossy toy plastic",
)
