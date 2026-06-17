from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from pixelator.errors import ImageError, OutputError
from pixelator.media import IMAGE_OUTPUT_EXTENSIONS

_ALPHA_OUTPUT_EXTENSIONS = {".png", ".tga", ".tif", ".tiff", ".webp"}


def load_static_image(path: str | Path) -> Image.Image:
    image_path = Path(path)
    try:
        with Image.open(image_path) as opened:
            if getattr(opened, "is_animated", False):
                opened.seek(0)
            image = ImageOps.exif_transpose(opened)
            mode = "RGBA" if _has_alpha(image) else "RGB"
            return image.convert(mode).copy()
    except (OSError, UnidentifiedImageError) as exc:
        raise ImageError(f"Could not load image: {image_path}") from exc


def _has_alpha(image: Image.Image) -> bool:
    return "A" in image.getbands() or "transparency" in image.info


def save_static_image(image: Image.Image, output: str | Path) -> None:
    output_path = Path(output)
    suffix = output_path.suffix.lower()
    if suffix not in IMAGE_OUTPUT_EXTENSIONS:
        supported = ", ".join(sorted(IMAGE_OUTPUT_EXTENSIONS))
        raise OutputError(f"Unsupported image output format '{suffix}'. Use one of: {supported}")

    preserves_alpha = suffix in _ALPHA_OUTPUT_EXTENSIONS and "A" in image.getbands()
    frame = image.convert("RGBA") if preserves_alpha else image.convert("RGB")
    kwargs: dict[str, object] = {}
    if suffix in {".jpg", ".jpeg"}:
        kwargs.update({"quality": 95, "subsampling": 0})
    elif suffix == ".webp":
        kwargs.update({"quality": 95})

    try:
        frame.save(output_path, **kwargs)
    except OSError as exc:
        raise ImageError(f"Could not write image: {output_path}") from exc
