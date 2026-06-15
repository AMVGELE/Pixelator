# Pixelator

Pixelator converts source videos and GIFs into a light pixel-art style.

## Install

```bash
python -m pip install -e ".[dev]"
```

## First Commands

```bash
pixelator input.mp4 --mode fast --out output-fast.mp4
pixelator input.mp4 --mode stable --out output-stable.mp4
pixelator input.mp4 --config presets/stable.yaml --out output-stable.mp4
pixelator input.gif --mode fast --out output-from-gif.mp4
pixelator input.mp4 --mode fast --out output.gif --no-audio
```

`fast` mode is for quick parameter previews. `stable` mode is for final renders with
reduced temporal color flicker.

Output format is inferred from `--out`. Use `.mp4` for video output or `.gif`
for animated GIF output. GIF output does not include audio.

## Verification

After installation, run:

```bash
python -m pytest -v
pixelator outputs/sample.mp4 --mode fast --out outputs/sample-fast.mp4 --overwrite --no-audio
pixelator outputs/sample.mp4 --mode stable --out outputs/sample-stable.mp4 --overwrite --no-audio
pixelator outputs/sample.gif --mode fast --out outputs/sample-gif-input.mp4 --overwrite --no-audio
pixelator outputs/sample.mp4 --mode fast --out outputs/sample-pixelated.gif --overwrite --no-audio
```

Use `fast` while tuning parameters, then render `stable` for final output.

## Crop And Trim

```bash
pixelator input.mp4 --crop 80,40,480,360 --trim 1.5,8.0 --out output.mp4
```

Crop uses source-video pixel coordinates. Trim uses source-video seconds.
H.264 `yuv420p` output requires even frame dimensions, so odd crop widths or
heights are snapped down by one pixel before encoding.

## Desktop GUI

```bash
pixelator-gui
```

The desktop GUI provides a restrained workstation layout with a queue panel, preview
area, render settings, trim controls, crop controls, and logs. It accepts common
video files and GIFs, and it uses the same Pixelator pipeline as the CLI.

Use the output format setting to choose MP4 or GIF for queued renders. MP4 remains
the default. GIF output is silent because the GIF format has no audio track.

The timeline sits above the preview. Moving the scrubber refreshes the displayed
source frame without changing the trim range. Crop can be adjusted either by
dragging the rectangle on the preview or by entering `X`, `Y`, `Width`, and
`Height` values; the GUI shows the output size beside those controls. Odd crop
widths or heights are snapped to even output dimensions for H.264 compatibility.

## Windows Portable Package

Build the local portable package with:

```powershell
.\scripts\package_windows.ps1
```

Run the packaged GUI with:

```powershell
.\dist\Pixelator\Pixelator.exe
```
