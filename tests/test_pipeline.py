from PIL import Image

from pixelator.config import RenderConfig
from pixelator.pipeline import process_frames
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
