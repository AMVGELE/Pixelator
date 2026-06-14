from __future__ import annotations

from pixelator.config import CropConfig


def fit_rect(source_size: tuple[int, int], widget_size: tuple[int, int]) -> tuple[int, int, int, int]:
    source_width, source_height = source_size
    widget_width, widget_height = widget_size
    scale = min(widget_width / source_width, widget_height / source_height)
    width = round(source_width * scale)
    height = round(source_height * scale)
    x = round((widget_width - width) / 2)
    y = round((widget_height - height) / 2)
    return x, y, width, height


def source_to_preview_crop(
    crop: CropConfig,
    source_size: tuple[int, int],
    widget_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    x, y, width, height = fit_rect(source_size, widget_size)
    scale = width / source_size[0]
    return (
        round(x + crop.x * scale),
        round(y + crop.y * scale),
        round(crop.width * scale),
        round(crop.height * scale),
    )


def preview_to_source_crop(
    preview_rect: tuple[int, int, int, int],
    source_size: tuple[int, int],
    widget_size: tuple[int, int],
) -> CropConfig:
    fit_x, fit_y, fit_width, fit_height = fit_rect(source_size, widget_size)
    x, y, width, height = preview_rect
    left = max(fit_x, x)
    top = max(fit_y, y)
    right = min(fit_x + fit_width, x + width)
    bottom = min(fit_y + fit_height, y + height)
    scale = source_size[0] / fit_width
    source_x = round((left - fit_x) * scale)
    source_y = round((top - fit_y) * scale)
    source_right = round((right - fit_x) * scale)
    source_bottom = round((bottom - fit_y) * scale)
    clamped_x = max(0, source_x)
    clamped_y = max(0, source_y)
    clamped_right = min(source_size[0], source_right)
    clamped_bottom = min(source_size[1], source_bottom)
    return CropConfig(
        x=clamped_x,
        y=clamped_y,
        width=max(1, clamped_right - clamped_x),
        height=max(1, clamped_bottom - clamped_y),
    )
