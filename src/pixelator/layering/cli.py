from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from pixelator.layering.commands import SplitOptions, split_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pixelator-layer",
        description="Split images into layer ZIP archives with a Pixelator layering service.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    split_parser = subparsers.add_parser("split", help="Split one image or a folder of images into layer ZIPs.")
    split_parser.add_argument("input", type=Path, help="Input image path or folder of images.")
    split_parser.add_argument("--out", type=Path, required=True, help="Output directory for layer ZIP archives.")
    split_parser.add_argument("--endpoint", required=True, help="Layer split service endpoint URL.")
    split_parser.add_argument(
        "--api-key-env",
        default="PIXELATOR_LAYER_API_KEY",
        help="Environment variable containing the layer service API key.",
    )
    split_parser.add_argument("--layers", type=int, help="Requested target layer count.")
    split_parser.add_argument("--timeout", type=float, default=600.0, help="Maximum seconds to wait for each job.")
    split_parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds between job status polls.",
    )
    split_parser.add_argument("--overwrite", action="store_true", help="Allow replacing existing layer ZIPs.")
    split_parser.add_argument("--fail-fast", action="store_true", help="Stop the batch after the first failure.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)

    if args.command == "split":
        api_key = os.environ.get(args.api_key_env)
        if not api_key:
            print(f"pixelator-layer: error: {args.api_key_env} is not set", file=sys.stderr)
            return 1

        return split_path(
            SplitOptions(
                input_path=args.input,
                output_dir=args.out,
                endpoint=args.endpoint,
                api_key=api_key,
                target_layers=args.layers,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
                overwrite=args.overwrite,
                fail_fast=args.fail_fast,
            )
        )

    parser.error(f"unknown command: {args.command}")
    return 2
