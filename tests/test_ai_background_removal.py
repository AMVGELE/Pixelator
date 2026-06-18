from datetime import UTC, datetime

import pytest

from pixelator.ai.background_removal import (
    AliyunCredentials,
    BackgroundRemovalError,
    build_signed_aliyun_url,
    read_aliyun_credentials,
    remove_image_background,
)
from pixelator.ai.dashscope_client import HttpResponse
from pixelator.ai.env import local_env_values


class FakeSegmentTransport:
    def __init__(self, response):
        self.response = response
        self.posts = []

    def post(self, url, headers, timeout):
        self.posts.append((url, headers, timeout))
        status, body = self.response
        return HttpResponse(status=status, body=body)


def test_build_signed_aliyun_url_contains_business_params_and_signature():
    url = build_signed_aliyun_url(
        AliyunCredentials("id", "secret"),
        {"Action": "SegmentCommonImage", "ImageURL": "https://example.test/a.png"},
        now=datetime(2026, 6, 17, 9, 0, 0, tzinfo=UTC),
        nonce="nonce",
    )

    assert url.startswith("https://imageseg.cn-shanghai.aliyuncs.com/?Signature=")
    assert "Action=SegmentCommonImage" in url
    assert "ImageURL=https%3A%2F%2Fexample.test%2Fa.png" in url
    assert "Timestamp=2026-06-17T09%3A00%3A00Z" in url


def test_remove_image_background_returns_segmented_url(monkeypatch):
    monkeypatch.setenv("ALIYUN_VIAPI_CREDENTIALS", "id:secret")
    transport = FakeSegmentTransport((200, b'{"Data":{"ImageURL":"https://example.test/out.png"}}'))

    output_url = remove_image_background("https://example.test/in.png", transport, 30)

    assert output_url == "https://example.test/out.png"
    assert transport.posts
    assert "SegmentCommonImage" in transport.posts[0][0]


def test_remove_image_background_reports_provider_errors(monkeypatch):
    monkeypatch.setenv("ALIYUN_VIAPI_CREDENTIALS", "id:secret")
    transport = FakeSegmentTransport((400, b'{"Message":"bad image"}'))

    with pytest.raises(BackgroundRemovalError, match="bad image"):
        remove_image_background("https://example.test/in.png", transport, 30)


def test_read_aliyun_credentials_requires_valid_format(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ALIYUN_VIAPI_CREDENTIALS", raising=False)
    local_env_values.cache_clear()

    with pytest.raises(BackgroundRemovalError, match="ALIYUN_VIAPI_CREDENTIALS"):
        read_aliyun_credentials()

    monkeypatch.setenv("ALIYUN_VIAPI_CREDENTIALS", "bad")
    with pytest.raises(BackgroundRemovalError, match="AccessKeyId:AccessKeySecret"):
        read_aliyun_credentials()
