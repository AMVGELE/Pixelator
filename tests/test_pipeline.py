from PIL import Image

from pixelator.config import CropConfig, RenderConfig, TrimConfig
from pixelator.pipeline import prepare_source_frames, process_frames
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


def test_prepare_source_frames_applies_crop():
    frames = [Image.new("RGB", (10, 8), (255, 0, 0))]
    frames[0].putpixel((7, 5), (0, 255, 0))
    config = RenderConfig(crop=CropConfig(x=5, y=4, width=3, height=2))
    metadata = VideoMetadata(width=10, height=8, fps=24.0)

    prepared, prepared_metadata = prepare_source_frames(frames, config, metadata)

    assert prepared_metadata.size == (3, 2)
    assert prepared[0].size == (3, 2)
    assert prepared[0].getpixel((2, 1)) == (0, 255, 0)


def test_prepare_source_frames_applies_trim_by_frame_range():
    frames = [Image.new("RGB", (4, 4), (index, 0, 0)) for index in range(10)]
    config = RenderConfig(trim=TrimConfig(start=0.2, end=0.5))
    metadata = VideoMetadata(width=4, height=4, fps=10.0, duration=1.0)

    prepared, prepared_metadata = prepare_source_frames(frames, config, metadata)

    assert prepared_metadata.duration == 0.3
    assert [frame.getpixel((0, 0))[0] for frame in prepared] == [2, 3, 4]
