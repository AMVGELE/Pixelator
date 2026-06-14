from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

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
    source_width = _even_encoder_dimension(max(1, clamped_right - clamped_x), source_size[0] - clamped_x)
    source_height = _even_encoder_dimension(max(1, clamped_bottom - clamped_y), source_size[1] - clamped_y)
    return CropConfig(
        x=clamped_x,
        y=clamped_y,
        width=source_width,
        height=source_height,
    )


class PreviewWidget(QWidget):
    cropChanged = Signal(CropConfig)

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(560, 360)
        self.setMouseTracking(True)
        self._pixmap: QPixmap | None = None
        self._source_size: tuple[int, int] | None = None
        self._crop: CropConfig | None = None
        self._drag_mode: str | None = None
        self._drag_start: QPoint | None = None
        self._drag_rect: tuple[int, int, int, int] | None = None

    def set_image(self, image: Image.Image) -> None:
        source = image.convert("RGB")
        self._source_size = source.size
        self._pixmap = QPixmap.fromImage(_pil_to_qimage(source))
        self._crop = CropConfig(x=0, y=0, width=source.width, height=source.height)
        self.cropChanged.emit(self._crop)
        self.update()

    def set_crop(self, crop: CropConfig | None) -> None:
        if self._source_size is None:
            return
        width, height = self._source_size
        if crop is None:
            crop = CropConfig(x=0, y=0, width=width, height=height)
        self._crop = clamp_crop(crop, self._source_size)
        self.cropChanged.emit(self._crop)
        self.update()

    def crop(self) -> CropConfig | None:
        return self._crop

    def source_size(self) -> tuple[int, int] | None:
        return self._source_size

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#151719"))
        if self._pixmap is None or self._source_size is None:
            painter.setPen(QColor("#8b949e"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No preview")
            return

        fit_x, fit_y, fit_width, fit_height = fit_rect(self._source_size, (self.width(), self.height()))
        painter.drawPixmap(QRect(fit_x, fit_y, fit_width, fit_height), self._pixmap)

        if self._crop is not None:
            crop_rect = QRect(*source_to_preview_crop(self._crop, self._source_size, (self.width(), self.height())))
            painter.setPen(QPen(QColor("#7dd3fc"), 2))
            painter.drawRect(crop_rect)
            painter.setBrush(QColor("#7dd3fc"))
            for handle in _handle_rects(crop_rect).values():
                painter.drawRect(handle)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._source_size is None:
            return
        self._drag_start = event.position().toPoint()
        self._drag_rect = self._preview_crop_rect()
        self._drag_mode = self._hit_test(self._drag_start)
        if self._drag_mode is None:
            self._drag_mode = "create"
            self._drag_rect = (self._drag_start.x(), self._drag_start.y(), 1, 1)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._source_size is None or self._drag_start is None or self._drag_rect is None or self._drag_mode is None:
            return
        current = event.position().toPoint()
        next_rect = self._dragged_rect(current)
        self._crop = preview_to_source_crop(next_rect, self._source_size, (self.width(), self.height()))
        self.cropChanged.emit(self._crop)
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_start = None
        self._drag_rect = None
        self._drag_mode = None

    def _preview_crop_rect(self) -> tuple[int, int, int, int]:
        if self._source_size is None or self._crop is None:
            return (0, 0, 1, 1)
        return source_to_preview_crop(self._crop, self._source_size, (self.width(), self.height()))

    def _hit_test(self, point: QPoint) -> str | None:
        rect = QRect(*self._preview_crop_rect())
        for name, handle in _handle_rects(rect).items():
            if handle.contains(point):
                return name
        if rect.contains(point):
            return "move"
        return None

    def _dragged_rect(self, current: QPoint) -> tuple[int, int, int, int]:
        assert self._drag_start is not None
        assert self._drag_rect is not None
        x, y, width, height = self._drag_rect
        left = x
        top = y
        right = x + width
        bottom = y + height
        dx = current.x() - self._drag_start.x()
        dy = current.y() - self._drag_start.y()

        mode = self._drag_mode or "move"
        if mode == "move":
            left += dx
            right += dx
            top += dy
            bottom += dy
        elif mode == "create":
            right = current.x()
            bottom = current.y()
        else:
            if "w" in mode:
                left += dx
            if "e" in mode:
                right += dx
            if "n" in mode:
                top += dy
            if "s" in mode:
                bottom += dy

        normalized_left = min(left, right)
        normalized_top = min(top, bottom)
        normalized_right = max(left, right)
        normalized_bottom = max(top, bottom)
        return (
            normalized_left,
            normalized_top,
            max(1, normalized_right - normalized_left),
            max(1, normalized_bottom - normalized_top),
        )


def _pil_to_qimage(image: Image.Image) -> QImage:
    data = image.tobytes("raw", "RGB")
    qimage = QImage(data, image.width, image.height, image.width * 3, QImage.Format.Format_RGB888)
    return qimage.copy()


def clamp_crop(crop: CropConfig, source_size: tuple[int, int]) -> CropConfig:
    width, height = source_size
    x = min(max(0, crop.x), width - 1)
    y = min(max(0, crop.y), height - 1)
    right = min(width, x + max(1, crop.width))
    bottom = min(height, y + max(1, crop.height))
    crop_width = _even_encoder_dimension(max(1, right - x), width - x)
    crop_height = _even_encoder_dimension(max(1, bottom - y), height - y)
    return CropConfig(x=x, y=y, width=crop_width, height=crop_height)


def _even_encoder_dimension(value: int, max_value: int) -> int:
    clamped = max(1, min(value, max_value))
    if clamped < 2 and max_value >= 2:
        return 2
    if clamped > 2 and clamped % 2 == 1:
        return clamped - 1
    return clamped


def _handle_rects(rect: QRect) -> dict[str, QRect]:
    size = 8
    half = size // 2
    cx = rect.center().x()
    cy = rect.center().y()
    points = {
        "nw": (rect.left(), rect.top()),
        "n": (cx, rect.top()),
        "ne": (rect.right(), rect.top()),
        "e": (rect.right(), cy),
        "se": (rect.right(), rect.bottom()),
        "s": (cx, rect.bottom()),
        "sw": (rect.left(), rect.bottom()),
        "w": (rect.left(), cy),
    }
    return {name: QRect(x - half, y - half, size, size) for name, (x, y) in points.items()}
