from PIL import Image
import pytest

from pixelator.config import (
    CropConfig,
    EffectsConfig,
    ImageConfig,
    OutputConfig,
    PaletteConfig,
    PixelConfig,
    RenderConfig,
    TrimConfig,
)
from pixelator.errors import MediaError, OutputError
from pixelator.pipeline import prepare_source_frames, process_frames, render_image, render_media, render_video
from pixelator.video import VideoMetadata


def test_process_frames_fast_limits_colors_and_preserves_size():
    frames = [Image.linear_gradient("L").resize((16, 16)).convert("RGB") for _ in range(2)]
    config = RenderConfig(mode="fast")
    metadata = VideoMetadata(width=16, height=16, fps=24.0)

    result = list(process_frames(frames, config, metadata))

    assert len(result) == 2
    assert result[0].size == (16, 16)


def test_process_frames_stable_uses_shared_palette():
    frames = [
        Image.new("RGB", (8, 8), (255, 0, 0)),
        Image.new("RGB", (8, 8), (250, 0, 0)),
    ]
    config = RenderConfig(mode="stable")
    metadata = VideoMetadata(width=8, height=8, fps=24.0)

    result = list(process_frames(frames, config, metadata))

    assert len(result) == 2
    assert result[0].size == (8, 8)
    assert result[1].size == (8, 8)


def test_process_frames_custom_palette_overrides_fast_quantization():
    frames = [Image.linear_gradient("L").resize((16, 16)).convert("RGB")]
    config = RenderConfig(
        mode="fast",
        palette=PaletteConfig(strategy="custom", custom_colors=["#000000", "#ffffff"]),
        effects=EffectsConfig(crt="off", vhs="off"),
    )
    metadata = VideoMetadata(width=16, height=16, fps=24.0)

    result = list(process_frames(frames, config, metadata))

    assert set(result[0].getdata()).issubset({(0, 0, 0), (255, 255, 255)})


def test_process_frames_custom_palette_applies_after_effects():
    frames = [Image.linear_gradient("L").resize((16, 16)).convert("RGB")]
    config = RenderConfig(
        mode="stable",
        palette=PaletteConfig(strategy="custom", custom_colors=["#000000", "#ffffff"]),
        effects=EffectsConfig(crt="subtle", vhs="light"),
    )
    metadata = VideoMetadata(width=16, height=16, fps=24.0)

    result = list(process_frames(frames, config, metadata))

    assert set(result[0].getdata()).issubset({(0, 0, 0), (255, 255, 255)})


def test_process_frames_auto_match_palette_applies_in_fast_and_stable_modes():
    frame = Image.new("RGB", (4, 4))
    frame.putdata([(250, 0, 0)] * 8 + [(0, 0, 250)] * 8)
    metadata = VideoMetadata(width=4, height=4, fps=24.0)

    for mode in ("fast", "stable"):
        config = RenderConfig(
            mode=mode,
            pixel=PixelConfig(scale=1),
            palette=PaletteConfig(
                strategy="auto_match",
                source_colors=["#ff0000", "#0000ff"],
                custom_colors=["#0000cc", "#ff3300"],
                match_sort="original",
            ),
            effects=EffectsConfig(crt="subtle", vhs="light"),
        )

        result = list(process_frames([frame], config, metadata))

        assert set(result[0].getdata()).issubset({(0, 0, 204), (255, 51, 0)})


def test_process_frames_auto_match_uses_direct_render_fallback_for_uncovered_colors():
    frame = Image.new("RGB", (2, 1))
    frame.putdata([(240, 240, 240), (34, 34, 40)])
    config = RenderConfig(
        mode="fast",
        pixel=PixelConfig(scale=1),
        palette=PaletteConfig(
            strategy="auto_match",
            source_colors=["#202020", "#303038"],
            custom_colors=["#000000", "#eeeeee"],
            match_sort="original",
        ),
        effects=EffectsConfig(crt="off", vhs="off"),
    )

    result = list(process_frames([frame], config, VideoMetadata(width=2, height=1, fps=24.0)))

    assert list(result[0].getdata()) == [(238, 238, 238), (0, 0, 0)]


def test_process_frames_original_palette_skips_quantization():
    colors = [(index * 20, 255 - index * 20, index * 10) for index in range(8)]
    frame = Image.new("RGB", (8, 1))
    frame.putdata(colors)
    config = RenderConfig(
        mode="stable",
        pixel=PixelConfig(scale=1),
        palette=PaletteConfig(strategy="original", colors=2),
        image=ImageConfig(brightness=1.0, sharpness=1.0, saturation=1.0),
        effects=EffectsConfig(crt="off", vhs="off"),
    )

    result = list(process_frames([frame], config, VideoMetadata(width=8, height=1, fps=24.0)))

    assert list(result[0].getdata()) == colors


def test_prepare_source_frames_applies_crop():
    frames = [Image.new("RGB", (10, 8), (255, 0, 0))]
    frames[0].putpixel((8, 5), (0, 255, 0))
    config = RenderConfig(crop=CropConfig(x=5, y=4, width=4, height=2))
    metadata = VideoMetadata(width=10, height=8, fps=24.0)

    prepared, prepared_metadata = prepare_source_frames(frames, config, metadata)

    assert prepared_metadata.size == (4, 2)
    assert prepared[0].size == (4, 2)
    assert prepared[0].getpixel((3, 1)) == (0, 255, 0)


def test_prepare_source_frames_makes_crop_dimensions_even_for_h264():
    frames = [Image.new("RGB", (10, 8), (255, 0, 0))]
    config = RenderConfig(crop=CropConfig(x=5, y=4, width=3, height=3))
    metadata = VideoMetadata(width=10, height=8, fps=24.0)

    prepared, prepared_metadata = prepare_source_frames(frames, config, metadata)

    assert prepared_metadata.size == (2, 2)
    assert prepared[0].size == (2, 2)


def test_prepare_source_frames_can_preserve_odd_dimensions_for_gif():
    frames = [Image.new("RGB", (10, 8), (255, 0, 0))]
    config = RenderConfig(crop=CropConfig(x=5, y=4, width=3, height=3))
    metadata = VideoMetadata(width=10, height=8, fps=24.0)

    prepared, prepared_metadata = prepare_source_frames(frames, config, metadata, encoder_safe=False)

    assert prepared_metadata.size == (3, 3)
    assert prepared[0].size == (3, 3)


def test_prepare_source_frames_applies_trim_by_frame_range():
    frames = [Image.new("RGB", (4, 4), (index, 0, 0)) for index in range(10)]
    config = RenderConfig(trim=TrimConfig(start=0.2, end=0.5))
    metadata = VideoMetadata(width=4, height=4, fps=10.0, duration=1.0)

    prepared, prepared_metadata = prepare_source_frames(frames, config, metadata)

    assert prepared_metadata.duration == 0.3
    assert [frame.getpixel((0, 0))[0] for frame in prepared] == [2, 3, 4]


def test_render_video_writes_real_gif_and_skips_audio_mux(monkeypatch, tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"fake")
    output = tmp_path / "pixelated.gif"
    frames = [
        Image.new("RGB", (3, 3), (255, 0, 0)),
        Image.new("RGB", (3, 3), (0, 0, 255)),
    ]

    monkeypatch.setattr(
        "pixelator.pipeline.probe_video",
        lambda path: VideoMetadata(width=3, height=3, fps=12.0, duration=2 / 12.0),
    )
    monkeypatch.setattr("pixelator.pipeline.iter_frames", lambda path: iter(frames))
    monkeypatch.setattr(
        "pixelator.pipeline.mux_audio",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("GIF output must not mux audio")),
    )

    result = render_video(
        source,
        output,
        RenderConfig(
            mode="fast",
            pixel=PixelConfig(scale=1),
            effects=EffectsConfig(crt="off", vhs="off"),
            output=OutputConfig(keep_audio=True, overwrite=True),
        ),
    )

    assert result == output
    with Image.open(output) as gif:
        assert gif.format == "GIF"
        assert gif.size == (3, 3)
        assert gif.n_frames == 2


def test_render_gif_input_to_video_skips_audio_mux(monkeypatch, tmp_path):
    source = tmp_path / "source.gif"
    source.write_bytes(b"fake")
    output = tmp_path / "pixelated.mp4"
    frames = [Image.new("RGB", (4, 4), (255, 0, 0))]
    calls = {}

    monkeypatch.setattr(
        "pixelator.pipeline.probe_video",
        lambda path: VideoMetadata(width=4, height=4, fps=12.0, duration=1 / 12.0),
    )
    monkeypatch.setattr("pixelator.pipeline.iter_frames", lambda path: iter(frames))

    def fake_write_video(processed, silent_output, metadata, codec):
        calls["write_video"] = (list(processed), silent_output, metadata, codec)
        silent_output.write_bytes(b"video")

    monkeypatch.setattr("pixelator.pipeline.write_video", fake_write_video)
    monkeypatch.setattr(
        "pixelator.pipeline.mux_audio",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("GIF input has no audio to mux")),
    )

    render_video(source, output, RenderConfig(output=OutputConfig(keep_audio=True, overwrite=True)))

    assert output.read_bytes() == b"video"
    assert "write_video" in calls


def test_render_image_writes_pixelated_png(tmp_path):
    source = tmp_path / "texture.png"
    output = tmp_path / "texture-pixelated.png"
    image = Image.new("RGB", (5, 3), (255, 0, 0))
    image.putpixel((4, 2), (0, 0, 255))
    image.save(source)

    result = render_image(
        source,
        output,
        RenderConfig(
            mode="fast",
            pixel=PixelConfig(scale=1),
            effects=EffectsConfig(crt="off", vhs="off"),
            output=OutputConfig(overwrite=True),
        ),
    )

    assert result == output
    with Image.open(output) as rendered:
        assert rendered.format == "PNG"
        assert rendered.size == (5, 3)


def test_render_image_preserves_alpha_for_png_output(tmp_path):
    source = tmp_path / "cutout.png"
    output = tmp_path / "cutout-pixelated.png"
    image = Image.new("RGBA", (4, 3), (255, 0, 0, 0))
    for x in range(4):
        image.putpixel((x, 2), (0, 255, 0, 255))
    image.save(source)

    render_image(
        source,
        output,
        RenderConfig(
            mode="fast",
            pixel=PixelConfig(scale=1),
            palette=PaletteConfig(strategy="custom", custom_colors=["#000000", "#ffffff"]),
            effects=EffectsConfig(crt="off", vhs="off"),
            output=OutputConfig(overwrite=True),
        ),
    )

    with Image.open(output) as rendered:
        rgba = rendered.convert("RGBA")
        assert rgba.getpixel((0, 0))[3] == 0
        assert rgba.getpixel((3, 1))[3] == 0
        assert rgba.getpixel((0, 2))[3] == 255
        assert rgba.getpixel((3, 2))[3] == 255


def test_render_image_preserves_cropped_alpha_mask(tmp_path):
    source = tmp_path / "alpha-crop.png"
    output = tmp_path / "alpha-crop-pixelated.png"
    image = Image.new("RGBA", (4, 4), (32, 64, 96, 0))
    crop_alphas = [0, 64, 128, 255]
    for index, alpha in enumerate(crop_alphas):
        x = 1 + index % 2
        y = 1 + index // 2
        image.putpixel((x, y), (200, 180, 160, alpha))
    image.save(source)

    render_image(
        source,
        output,
        RenderConfig(
            mode="fast",
            pixel=PixelConfig(scale=1),
            crop=CropConfig(x=1, y=1, width=2, height=2),
            effects=EffectsConfig(crt="off", vhs="off"),
            output=OutputConfig(overwrite=True),
        ),
    )

    with Image.open(output) as rendered:
        alpha = list(rendered.convert("RGBA").getchannel("A").getdata())
        assert rendered.size == (2, 2)
        assert alpha == crop_alphas


def test_render_image_preserves_odd_crop_dimensions(tmp_path):
    source = tmp_path / "texture.png"
    output = tmp_path / "cropped.png"
    Image.new("RGB", (7, 5), (255, 0, 0)).save(source)

    render_image(
        source,
        output,
        RenderConfig(
            mode="fast",
            pixel=PixelConfig(scale=1),
            crop=CropConfig(x=1, y=1, width=3, height=3),
            effects=EffectsConfig(crt="off", vhs="off"),
            output=OutputConfig(overwrite=True),
        ),
    )

    with Image.open(output) as rendered:
        assert rendered.size == (3, 3)


def test_render_image_rejects_video_output_extension(tmp_path):
    source = tmp_path / "texture.png"
    Image.new("RGB", (4, 4), (255, 0, 0)).save(source)

    with pytest.raises(OutputError, match="Unsupported image output format"):
        render_image(
            source,
            tmp_path / "texture.mp4",
            RenderConfig(output=OutputConfig(overwrite=True)),
        )


def test_render_media_dispatches_images(monkeypatch, tmp_path):
    source = tmp_path / "texture.png"
    output = tmp_path / "texture-pixelated.png"
    calls = {}

    def fake_render_image(input_file, output_file, config):
        calls["image"] = (input_file, output_file, config)
        return output

    monkeypatch.setattr("pixelator.pipeline.render_image", fake_render_image)

    result = render_media(source, output, RenderConfig())

    assert result == output
    assert calls["image"][0] == source


def test_render_media_rejects_unknown_input_extension(tmp_path):
    with pytest.raises(MediaError, match="Unsupported input media type"):
        render_media(tmp_path / "source.txt", tmp_path / "out.png", RenderConfig())
