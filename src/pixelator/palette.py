from __future__ import annotations

from collections.abc import Iterable

from PIL import Image

from pixelator.config import PaletteConfig

RGB = tuple[int, int, int]


def quantize_per_frame(image: Image.Image, config: PaletteConfig) -> Image.Image:
    return (
        image.convert("RGB")
        .quantize(colors=config.colors, dither=Image.Dither.NONE)
        .convert("RGB")
    )


def build_global_palette(frames: Iterable[Image.Image], config: PaletteConfig) -> list[RGB]:
    prepared = [frame.convert("RGB").resize((64, 64), Image.Resampling.BOX) for frame in frames]
    if not prepared:
        return [(0, 0, 0)]
    atlas = Image.new("RGB", (64, 64 * len(prepared)))
    for index, frame in enumerate(prepared):
        atlas.paste(frame, (0, index * 64))
    quantized = atlas.quantize(colors=config.colors, dither=Image.Dither.NONE)
    raw_palette = quantized.getpalette() or []
    used_indices = sorted(set(quantized.getdata()))
    colors: list[RGB] = []
    for index in used_indices[: config.colors]:
        offset = index * 3
        colors.append(tuple(raw_palette[offset : offset + 3]))  # type: ignore[arg-type]
    return colors or [(0, 0, 0)]


def apply_palette(image: Image.Image, palette: list[RGB]) -> Image.Image:
    palette_image = Image.new("P", (1, 1))
    flat: list[int] = []
    for color in palette[:256]:
        flat.extend(color)
    flat.extend([0] * (768 - len(flat)))
    palette_image.putpalette(flat)
    return image.convert("RGB").quantize(palette=palette_image, dither=Image.Dither.NONE).convert("RGB")


def unique_rgb_count(image: Image.Image) -> int:
    return len(set(image.convert("RGB").getdata()))
