from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from pixelator.ai.aliyun_rpc import (
    AliyunCredentials,
    AliyunCredentialsError,
    build_signed_aliyun_url as _build_signed_aliyun_url,
    format_provider_error,
    parse_response_payload,
    read_aliyun_credentials as _read_aliyun_credentials,
)

ALIYUN_IMAGESEG_ENDPOINT = "https://imageseg.cn-shanghai.aliyuncs.com/"
ALIYUN_IMAGESEG_VERSION = "2019-12-30"


class BackgroundRemovalError(RuntimeError):
    """Raised when Aliyun VIAPI background removal cannot complete."""


class BackgroundRemovalTransport(Protocol):
    def post(self, url: str, headers: dict[str, str] | None, timeout: float): ...


def remove_image_background(image_url: str, transport: BackgroundRemovalTransport, timeout: float) -> str:
    credentials = read_aliyun_credentials()
    if not image_url.startswith(("http://", "https://")):
        raise BackgroundRemovalError("Transparent background post-processing requires an http image URL.")
    request_url = build_signed_aliyun_url(
        credentials,
        {
            "Action": "SegmentCommonImage",
            "ImageURL": image_url,
        },
    )
    response = transport.post(request_url, None, timeout)
    payload = parse_response_payload(response.body)
    if response.status < 200 or response.status >= 300:
        raise BackgroundRemovalError(
            f"Aliyun image segmentation failed ({response.status}): {format_provider_error(payload)}"
        )
    output_url = _extract_segmented_image_url(payload)
    if not output_url:
        raise BackgroundRemovalError("Aliyun image segmentation succeeded but returned no image URL.")
    return output_url


def read_aliyun_credentials() -> AliyunCredentials:
    try:
        return _read_aliyun_credentials()
    except AliyunCredentialsError as exc:
        message = str(exc)
        if "not configured" in message:
            message = "Transparent background post-processing requires ALIYUN_VIAPI_CREDENTIALS."
        raise BackgroundRemovalError(message) from exc


def build_signed_aliyun_url(
    credentials: AliyunCredentials,
    business_params: dict[str, str],
    now: datetime | None = None,
    nonce: str | None = None,
) -> str:
    return _build_signed_aliyun_url(
        credentials,
        business_params,
        endpoint=ALIYUN_IMAGESEG_ENDPOINT,
        version=ALIYUN_IMAGESEG_VERSION,
        now=now,
        nonce=nonce,
    )


def _extract_segmented_image_url(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("Data")
    if not isinstance(data, dict):
        return None
    value = data.get("ImageURL")
    return value.strip() if isinstance(value, str) and value.strip() else None
