from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pixelator.config import ConfigError, RenderConfig, load_config, merge_cli_overrides
from pixelator.errors import PixelatorError
from pixelator.pipeline import render_video


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
