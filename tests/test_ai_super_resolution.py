from __future__ import annotations

from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from PIL import Image

from pixelator.ai.dashscope_client import HttpResponse
from pixelator.ai.env import local_env_values
from pixelator.ai.super_resolution import (
    SuperResolutionClient,
    SuperResolutionError,
    SuperResolutionOptions,
    make_super_resolution_image_url,
    _redact_credentials,
)


class FakeSuperResolutionTransport:
    def __init__(self, post_response=(200, b'{"Data":{"Url":"https://example.test/out.png"}}'), get_body=None):
        self.post_response = post_response
        self.get_body = get_body if get_body is not None else _image_bytes(size=(8, 8))
        self.posts = []
        self.gets = []

    def post(self, url, headers, timeout):
        self.posts.append((url, headers, timeout))
        status, body = self.post_response
        return HttpResponse(status=status, body=body)

    def get(self, url, headers, timeout):
        self.gets.append((url, headers, timeout))
        return HttpResponse(status=200, body=self.get_body)


class FakeSdkRunner:
    def __init__(self, output_url="https://example.test/sr.png"):
        self.output_url = output_url
        self.calls = []

    def upscale_local(self, source_path, upscale_factor, output_format, output_quality, timeout):
        self.calls.append((source_path, upscale_factor, output_format, output_quality, timeout))
        return self.output_url


def test_make_super_resolution_image_url_signs_imageenhan_request(monkeypatch):
    monkeypatch.setenv("ALIYUN_VIAPI_CREDENTIALS", "id:secret")
    transport = FakeSuperResolutionTransport()

    output_url = make_super_resolution_image_url(
        "https://example.test/in.png",
        upscale_factor=3,
        output_format="jpg",
        output_quality=95,
        transport=transport,
        timeout=15,
    )

    assert output_url == "https://example.test/out.png"
    assert transport.posts[0][1] is None
    assert transport.posts[0][2] == 15
    parsed = urlparse(transport.posts[0][0])
    params = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "imageenhan.cn-shanghai.aliyuncs.com"
    assert params["Action"] == ["MakeSuperResolutionImage"]
    assert params["Url"] == ["https://example.test/in.png"]
    assert params["UpscaleFactor"] == ["3"]
    assert params["OutputFormat"] == ["jpg"]
    assert params["OutputQuality"] == ["95"]
    assert "Signature" in params


def test_make_super_resolution_image_url_rejects_non_http_input(monkeypatch):
    monkeypatch.setenv("ALIYUN_VIAPI_CREDENTIALS", "id:secret")

    with pytest.raises(SuperResolutionError, match="http image URL"):
        make_super_resolution_image_url(r"D:\local\image.png")


def test_make_super_resolution_image_url_reports_provider_error(monkeypatch):
    monkeypatch.setenv("ALIYUN_VIAPI_CREDENTIALS", "id:secret")
    transport = FakeSuperResolutionTransport(post_response=(400, b'{"Message":"bad image"}'))

    with pytest.raises(SuperResolutionError, match="bad image"):
        make_super_resolution_image_url("https://example.test/in.png", transport=transport)


def test_make_super_resolution_image_url_requires_data_url(monkeypatch):
    monkeypatch.setenv("ALIYUN_VIAPI_CREDENTIALS", "id:secret")
    transport = FakeSuperResolutionTransport(post_response=(200, b'{"Data":{}}'))

    with pytest.raises(SuperResolutionError, match="Data.Url"):
        make_super_resolution_image_url("https://example.test/in.png", transport=transport)


def test_super_resolution_client_uses_sdk_for_local_file_and_downloads_output(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ALIYUN_VIAPI_CREDENTIALS", raising=False)
    local_env_values.cache_clear()
    source = tmp_path / "source.png"
    Image.new("RGB", (4, 4), (255, 0, 0)).save(source)
    transport = FakeSuperResolutionTransport(get_body=_image_bytes(size=(12, 12)))
    sdk_runner = FakeSdkRunner()
    client = SuperResolutionClient(transport=transport, sdk_runner=sdk_runner, timeout=20)

    result = client.upscale(
        SuperResolutionOptions(source_path=source, upscale_factor=3, output_format="png", jpg_quality=95),
        tmp_path / "outputs",
    )

    assert sdk_runner.calls == [(source, 3, "png", None, 20)]
    assert transport.gets[0][0] == "https://example.test/sr.png"
    assert result.source_path == source
    assert result.before_size == (4, 4)
    assert result.after_size == (12, 12)
    assert result.output_path.exists()
    assert result.output_path.parent == tmp_path / "outputs"


def test_super_resolution_errors_redact_aliyun_credentials():
    message = _redact_credentials("bad id secret", "id", "secret")

    assert message == "bad <redacted> <redacted>"


def _image_bytes(size=(4, 4)) -> bytes:
    image = Image.new("RGB", size, (0, 128, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
