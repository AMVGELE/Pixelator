from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon


def app_icon_path() -> Path:
    return Path(__file__).resolve().parent / "assets" / "pixelator_icon.png"


def app_icon() -> QIcon:
    return QIcon(str(app_icon_path()))
