from PIL import Image

from pixelator.config import CropConfig, EffectsConfig, OutputConfig, PaletteConfig, PixelConfig, RenderConfig, TrimConfig
from pixelator.pipeline import prepare_source_frames, process_frames, render_video
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
