from __future__ import annotations

from pathlib import Path

IMAGE_INPUT_EXTENSIONS = {
    ".bmp",
    ".jpeg",
    ".jpg",
    ".png",
    ".tga",
    ".tif",
    ".tiff",
    ".webp",
}
IMAGE_OUTPUT_EXTENSIONS = {
    ".bmp",
    ".jpeg",
    ".jpg",
    ".png",
    ".tga",
    ".tif",
    ".tiff",
    ".webp",
}
VIDEO_INPUT_EXTENSIONS = {".avi", ".gif", ".mkv", ".mov", ".mp4"}


def is_image_path(path: str | Path) -> bool:
    return Path(path).suffix.lower() in IMAGE_INPUT_EXTENSIONS


def is_video_path(path: str | Path) -> bool:
    return Path(path).suffix.lower() in VIDEO_INPUT_EXTENSIONS


def is_media_path(path: str | Path) -> bool:
    return is_image_path(path) or is_video_path(path)


def iter_image_files(directory: str | Path) -> list[Path]:
    folder = Path(directory)
    return sorted(
        (path for path in folder.iterdir() if path.is_file() and is_image_path(path)),
        key=lambda path: path.name.lower(),
    )
