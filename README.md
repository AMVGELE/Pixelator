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

## Custom Palettes

Use a custom palette when you want the final render to use an explicit set of
colors:

```yaml
palette:
  strategy: custom
  custom_colors:
    - "#1a1c2c"
    - "#5d275d"
    - "#b13e53"
    - "#ef7d57"
```

```bash
pixelator input.mp4 --config presets/my-palette.yaml --out output.mp4
```

Custom colors must use `#RRGGBB` hex values. When a custom palette is active,
Pixelator maps the final processed frame back to those colors, including after
CRT or VHS effects.

For palette reuse across different source material, the GUI can create an
AutoMatch palette config. AutoMatch keeps a Source palette and a Render palette,
then maps each source color to the perceptually closest render color:

```yaml
palette:
  strategy: auto_match
  match_sort: hue_brightness
  source_colors:
    - "#ff0000"
    - "#0000ff"
  custom_colors:
    - "#1a1c2c"
    - "#f4f4f4"
```

AutoMatch still outputs only Render palette colors. It is an automatic
perceptual pairing mode, not a saved manual per-color remap matrix. If a pixel
is too far from every Source color, AutoMatch falls back to the nearest Render
color so uncovered highlights or background colors do not collapse into dark
blocks.

## Desktop GUI

```bash
pixelator-gui
```

The desktop GUI provides a restrained workstation layout with a queue panel, preview
area, render settings, trim controls, crop controls, and logs. It accepts common
video files and GIFs, and it uses the same Pixelator pipeline as the CLI.

Use the output format setting to choose MP4 or GIF for queued renders. MP4 remains
the default. GIF output is silent because the GIF format has no audio track.

The right side of the GUI is split into Render and Palette tabs. Render keeps the
automatic `Colors` count and output controls; Palette provides a Source -> Render
comparison board for custom colors. Source is the latest extracted or imported
reference palette; Render is the palette that will actually be used for output.

Palette Studio tools in the Palette tab can extract colors from the current
preview frame or from an image file, save and load local presets, import local
Lospec-style `.hex` or `.txt` files, and sort colors by brightness, hue, or
saturation. Sorting organizes the Render palette view; AutoMatch uses perceptual
color distance for actual pairing. Lospec support in this version is local file
import only; it does not search or sync with the Lospec website.

Click Source and Render chips in the comparison board to inspect a pair. With
AutoMatch enabled, extracting a new Source palette preserves the current Render
palette, then re-pairs the two palettes by perceptual color distance. Turning
AutoMatch off falls back to nearest-color visual comparison. The `A -> B` panel
shows the active pair and RGB distance, and the Color Space view plots source and
render colors by hue and brightness. Add and Replace open the system color
picker, with Hex retained as a precise advanced edit field.

The timeline sits above the preview. Moving the scrubber refreshes the displayed
source frame without changing the trim range. Crop can be adjusted either by
dragging the rectangle on the preview or by entering `X`, `Y`, `Width`, and
`Height` values; the GUI shows the output size beside those controls. Odd crop
widths or heights are snapped to even output dimensions for H.264 compatibility.

CRT and VHS are optional style effects. The default render is clean pixel art.
VHS light uses low-frequency luminance variation instead of per-pixel color
noise, so it should not shatter solid pixel blocks.

## Windows Portable Package

Build the local portable package with:

```powershell
.\scripts\package_windows.ps1
```

Run the packaged GUI with:

```powershell
.\dist\Pixelator\Pixelator.exe
```
