# Pixelator

Pixelator converts source videos into a light pixel-art video style.

## Install

```bash
python -m pip install -e ".[dev]"
```

## First Commands

```bash
pixelator input.mp4 --mode fast --out output-fast.mp4
pixelator input.mp4 --mode stable --out output-stable.mp4
pixelator input.mp4 --config presets/stable.yaml --out output-stable.mp4
```

`fast` mode is for quick parameter previews. `stable` mode is for final renders with
reduced temporal color flicker.
