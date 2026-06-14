from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pixelator.config import ConfigError, CropConfig, RenderConfig, TrimConfig, load_config, merge_cli_overrides
from pixelator.errors import PixelatorError
from pixelator.pipeline import render_video


def _parse_crop(value: str) -> CropConfig:
    parts = value.split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("--crop must use x,y,width,height")
    try:
        x, y, width, height = [int(part.strip()) for part in parts]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--crop values must be integers") from exc
    return CropConfig(x=x, y=y, width=width, height=height)


def _parse_trim(value: str) -> TrimConfig:
    parts = value.split(",")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("--trim must use start,end")
    try:
        start = float(parts[0].strip())
        end_text = parts[1].strip()
        end = None if end_text == "" else float(end_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--trim values must be seconds") from exc
    return TrimConfig(start=start, end=end)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pixelator",
        description="Convert videos into a light pixel-art style.",
    )
    parser.add_argument("input", type=Path, help="Input video path.")
    parser.add_argument("--out", type=Path, required=True, help="Output video path.")
    parser.add_argument("--config", type=Path, help="YAML config path.")
    parser.add_argument("--mode", choices=["fast", "stable"], help="Render mode.")
    parser.add_argument("--pixel-scale", type=int, help="Pixel scale factor.")
    parser.add_argument("--colors", type=int, help="Palette color count.")
    parser.add_argument("--crop", type=_parse_crop, help="Crop rectangle as x,y,width,height in source pixels.")
    parser.add_argument("--trim", type=_parse_trim, help="Trim range as start,end seconds.")
    parser.add_argument("--no-audio", action="store_true", help="Do not preserve source audio.")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing an existing output file.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        config = load_config(args.config) if args.config else RenderConfig()
        overrides = {
            "mode": args.mode,
            "pixel.scale": args.pixel_scale,
            "palette.colors": args.colors,
            "crop": args.crop,
            "trim": args.trim,
            "output.keep_audio": False if args.no_audio else None,
            "output.overwrite": True if args.overwrite else None,
        }
        config = merge_cli_overrides(config, overrides)
        output = render_video(args.input, args.out, config)
    except SystemExit as exc:
        return int(exc.code)
    except (PixelatorError, ConfigError) as exc:
        print(f"pixelator: error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {output}")
    return 0
