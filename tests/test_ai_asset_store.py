from io import BytesIO

from PIL import Image

from pixelator.ai.asset_store import AssetStore
from pixelator.ai.prompt_builder import build_prompt
from pixelator.ai.types import AiGenerationRequest, DownloadedImage


def test_asset_store_saves_resized_png_and_assets_index(tmp_path):
    store = AssetStore(tmp_path)
    request = AiGenerationRequest(description="Fire slime", size="64x64")
    prompt = build_prompt(request)

    records = store.save_assets(request, prompt, [DownloadedImage(_png_bytes((16, 16)), "https://example.test/a.png")])

    assert len(records) == 1
    assert records[0].image_path.exists()
    assert (tmp_path / "assets.json").exists()
    assert Image.open(records[0].image_path).size == (64, 64)
    loaded = store.load_records()
    assert loaded[0].name == records[0].name
    assert loaded[0].prompt == prompt.positive_prompt


def test_asset_store_skips_records_when_image_file_is_missing(tmp_path):
    store = AssetStore(tmp_path)
    request = AiGenerationRequest(description="Fire slime")
    prompt = build_prompt(request)
    records = store.save_assets(request, prompt, [DownloadedImage(_png_bytes((8, 8)))])
    records[0].image_path.unlink()

    assert store.load_records() == []


def _png_bytes(size):
    buffer = BytesIO()
    Image.new("RGBA", size, (255, 0, 0, 255)).save(buffer, format="PNG")
    return buffer.getvalue()
