# Pixelator

Pixelator converts source videos, GIFs, and texture images into a light pixel-art style.

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
pixelator texture.png --mode fast --out texture-pixelated.png
```

`fast` mode is for quick parameter previews. `stable` mode is for final renders with
reduced temporal color flicker.

Output format is inferred from `--out`. Use `.mp4` for video output, `.gif`
for animated GIF output, or an image extension such as `.png`, `.jpg`, `.webp`,
`.bmp`, `.tga`, or `.tif` for texture output. GIF output does not include audio.
Texture outputs preserve source alpha when saved as `.png`, `.webp`, `.tga`,
`.tif`, or `.tiff`; use those formats for cutout sprites and transparent assets.

## Verification

After installation, run:

```bash
python -m pytest -v
pixelator outputs/sample.mp4 --mode fast --out outputs/sample-fast.mp4 --overwrite --no-audio
pixelator outputs/sample.mp4 --mode stable --out outputs/sample-stable.mp4 --overwrite --no-audio
pixelator outputs/sample.gif --mode fast --out outputs/sample-gif-input.mp4 --overwrite --no-audio
pixelator outputs/sample.mp4 --mode fast --out outputs/sample-pixelated.gif --overwrite --no-audio
pixelator outputs/sample.png --mode fast --out outputs/sample-pixelated.png --overwrite
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

## AI Layer Split CLI

`pixelator-layer` sends AI art images to a cloud layer-splitting service. Each
source image produces one ZIP archive.

The ZIP contains transparent PNG layers, `manifest.json`, and
`preview/composite.png`.

```powershell
$env:PIXELATOR_LAYER_API_KEY="your-service-token"
pixelator-layer split .\inputs --out .\outputs\layers --endpoint https://your-layer-service --overwrite
```

The default Pixelator install does not include Qwen model weights or GPU
dependencies. For the Aliyun/Bailian deployment path, see
`docs/layer-split-aliyun.md`.

## Desktop GUI

```bash
pixelator-gui
```

The desktop GUI provides a restrained workstation layout with a queue panel, preview
area, render settings, trim controls, crop controls, and logs. It accepts common
video files, GIFs, and image/texture files, and it uses the same Pixelator
pipeline as the CLI.

Use the output format setting to choose MP4 or GIF for queued renders. MP4 remains
the default. GIF output is silent because the GIF format has no audio track.
Image jobs are written as `source-pixelated.png` so texture batches keep a
lossless image output by default.

Use Add to import individual videos, GIFs, or texture images. Use Folder to add
all supported image files from a directory as a batch; unsupported files in that
folder are ignored.

Render settings are shared by default across the queue. Select a queued item and
use `Customize This Item` when one resource needs its own pixel scale, color
count, image adjustment, effects, or output format. `Use Global` returns that
item to the shared default settings. Crop and trim remain per item.

The right side of the GUI is split into Render and Palette tabs. Render keeps the
automatic `Colors` count and output controls; Palette provides a Source -> Render
comparison board for custom colors. Source is the latest extracted or imported
reference palette; Render is the palette that will actually be used for output.

The `AI Assets` tab can generate new 2D game assets through DashScope Qwen-Image
and save them as PNG files under `outputs/ai-assets`. Set `DASHSCOPE_API_KEY` in
the environment, keep it in `.env.local`, or paste it into `AI Assets` ->
`Provider Settings` -> `Qwen API key` for the current session. The model defaults
to `qwen-image-2.0`, and the endpoint defaults to the Beijing DashScope image
generation endpoint. When Background is `Transparent`, the GUI uses
`ALIYUN_VIAPI_CREDENTIALS` to run Aliyun VIAPI background removal before saving
the PNG. The Aliyun account must have the visual segmentation `SegmentCommonImage`
API enabled, otherwise Aliyun returns a provider error before Pixelator can save
the transparent result. Generated PNG assets can be added back into the normal
Pixelator queue with `Add To Queue`, then cropped, palette matched, pixelated,
and exported like any other image input.

Palette Studio tools in the Palette tab can extract colors from the current
preview frame or from an image file, save and load local presets, import local
Lospec-style `.hex` or `.txt` files, and sort colors by brightness, hue, or
saturation. Extract supports dominant colors, balanced hue coverage, and tonal
shadow/midtone/highlight sampling. Current-frame extraction can use the full
frame or the current crop; image-file extraction always uses the full selected
image. Sorting organizes the Render palette view; AutoMatch uses perceptual color
distance for actual pairing. Lospec support in this version is local file import
only; it does not search or sync with the Lospec website.

Palette is shared by default, so a Render palette can be reused across many
resources. Switch a selected item to `Per Item Palette` when it needs its own
Source/Render snapshot; switching back to `Shared Palette` restores the shared
palette context.

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
Image jobs do not use the timeline and keep exact crop dimensions, including odd
texture sizes.

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
