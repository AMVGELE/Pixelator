from __future__ import annotations

import base64
from io import BytesIO

import pytest
from PIL import Image

from pixelator.ai.dashscope_client import DashScopeClient, DashScopeError, HttpResponse
from pixelator.ai.env import local_env_values
from pixelator.ai.prompt_builder import build_prompt
from pixelator.ai.types import AiGenerationRequest, DashScopeConfig


class FakeTransport:
    def __init__(self, post_response, get_responses=None, segment_responses=None):
        self.post_response = post_response
        self.get_responses = list(get_responses or [])
        self.segment_responses = list(segment_responses or [])
        self.posts = []
        self.gets = []
        self.segment_posts = []

    def request_json(self, url, payload, headers, timeout):
        self.posts.append((url, payload, headers, timeout))
        status, body = self.post_response
        return HttpResponse(status=status, body=body)

    def get(self, url, headers, timeout):
        self.gets.append((url, headers, timeout))
        if not self.get_responses:
            raise AssertionError(f"Unexpected GET {url}")
        status, body = self.get_responses.pop(0)
        return HttpResponse(status=status, body=body)

    def post(self, url, headers, timeout):
        self.segment_posts.append((url, headers, timeout))
        if not self.segment_responses:
            raise AssertionError(f"Unexpected POST {url}")
        status, body = self.segment_responses.pop(0)
        return HttpResponse(status=status, body=body)


def test_dashscope_client_downloads_direct_image_and_normalizes_request_size():
    image_bytes = _png_bytes()
    transport = FakeTransport(
        (200, b'{"output":{"results":[{"url":"https://example.test/image.png","seed":"42"}]}}'),
        [(200, image_bytes)],
    )
    request = AiGenerationRequest(description="Fire slime", size="64x64", background="solid")
    client = DashScopeClient(
        DashScopeConfig(api_key="key", model="qwen-image-2.0", poll_interval_seconds=0),
        transport=transport,
    )

    images = client.generate(request, build_prompt(request))

    assert images[0].data == image_bytes
    assert images[0].source_url == "https://example.test/image.png"
    assert transport.posts[0][1]["parameters"]["size"] == "512*512"


def test_dashscope_client_polls_async_task_until_image_is_available():
    image_bytes = _png_bytes((0, 255, 0, 255))
    transport = FakeTransport(
        (200, b'{"output":{"task_id":"task_1","task_status":"PENDING"}}'),
        [
            (200, b'{"output":{"task_status":"RUNNING"}}'),
            (200, b'{"output":{"task_status":"SUCCEEDED","results":[{"url":"data:image/png;base64,'
            + base64.b64encode(image_bytes)
            + b'"}]}}'),
        ],
    )
    request = AiGenerationRequest(description="Blue potion", background="solid")
    client = DashScopeClient(
        DashScopeConfig(api_key="key", poll_attempts=2, poll_interval_seconds=0),
        transport=transport,
    )

    images = client.generate(request, build_prompt(request))

    assert images[0].data == image_bytes
    assert transport.gets[0][0].endswith("/task_1")


def test_dashscope_client_reports_http_errors():
    transport = FakeTransport((502, b'{"message":"provider exploded"}'))
    request = AiGenerationRequest(description="Fire slime", background="solid")
    client = DashScopeClient(DashScopeConfig(api_key="key"), transport=transport)

    with pytest.raises(DashScopeError, match="provider exploded"):
        client.generate(request, build_prompt(request))


def test_dashscope_client_requires_api_key(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    local_env_values.cache_clear()
    request = AiGenerationRequest(description="Fire slime")

    with pytest.raises(DashScopeError, match="DASHSCOPE_API_KEY"):
        DashScopeClient(DashScopeConfig(api_key="")).generate(request, build_prompt(request))


def test_dashscope_client_reports_missing_image_url():
    transport = FakeTransport((200, b'{"output":{"results":[]}}'))
    request = AiGenerationRequest(description="Fire slime", background="solid")
    client = DashScopeClient(DashScopeConfig(api_key="key"), transport=transport)

    with pytest.raises(DashScopeError, match="no image URL"):
        client.generate(request, build_prompt(request))


def test_dashscope_client_removes_background_for_transparent_assets(monkeypatch):
    monkeypatch.setenv("ALIYUN_VIAPI_CREDENTIALS", "access:secret")
    image_bytes = _png_bytes()
    transport = FakeTransport(
        (200, b'{"output":{"results":[{"url":"https://example.test/source.png"}]}}'),
        [(200, image_bytes)],
        [(200, b'{"Data":{"ImageURL":"https://example.test/segmented.png"}}')],
    )
    request = AiGenerationRequest(description="Fire slime", background="transparent")
    client = DashScopeClient(DashScopeConfig(api_key="key"), transport=transport)

    images = client.generate(request, build_prompt(request))

    assert images[0].data == image_bytes
    assert images[0].source_url == "https://example.test/segmented.png"
    assert transport.segment_posts
    assert "SegmentCommonImage" in transport.segment_posts[0][0]
    assert "source.png" in transport.segment_posts[0][0]


def _png_bytes(color=(255, 0, 0, 255)):
    buffer = BytesIO()
    Image.new("RGBA", (4, 4), color).save(buffer, format="PNG")
    return buffer.getvalue()
