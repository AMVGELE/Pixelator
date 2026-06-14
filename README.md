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

## Verification

After installation, run:

```bash
python -m pytest -v
pixelator outputs/sample.mp4 --mode fast --out outputs/sample-fast.mp4 --overwrite --no-audio
pixelator outputs/sample.mp4 --mode stable --out outputs/sample-stable.mp4 --overwrite --no-audio
```

Use `fast` while tuning parameters, then render `stable` for final output.

## Crop And Trim

```bash
pixelator input.mp4 --crop 80,40,480,360 --trim 1.5,8.0 --out output.mp4
```

Crop uses source-video pixel coordinates. Trim uses source-video seconds.

## Desktop GUI

```bash
pixelator-gui
```

The desktop GUI provides a restrained workstation layout with a queue panel, preview
area, render settings, trim controls, crop controls, and logs. It uses the same
Pixelator pipeline as the CLI.

The timeline sits above the preview. Moving the scrubber refreshes the displayed
source frame without changing the trim range. Crop can be adjusted either by
dragging the rectangle on the preview or by entering `X`, `Y`, `Width`, and
`Height` values; the GUI shows the output size beside those controls.

## Windows Portable Package

Build the local portable package with:

```powershell
.\scripts\package_windows.ps1
```

Run the packaged GUI with:

```powershell
.\dist\Pixelator\Pixelator.exe
```
