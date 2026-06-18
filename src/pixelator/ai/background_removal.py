from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import quote
from uuid import uuid4

from pixelator.ai.env import config_value

ALIYUN_IMAGESEG_ENDPOINT = "https://imageseg.cn-shanghai.aliyuncs.com/"
ALIYUN_IMAGESEG_VERSION = "2019-12-30"


class BackgroundRemovalError(RuntimeError):
    """Raised when Aliyun VIAPI background removal cannot complete."""


@dataclass(frozen=True)
class AliyunCredentials:
    access_key_id: str
    access_key_secret: str


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
    payload = _parse_response_payload(response.body)
    if response.status < 200 or response.status >= 300:
        raise BackgroundRemovalError(f"Aliyun image segmentation failed ({response.status}): {_format_error(payload)}")
    output_url = _extract_segmented_image_url(payload)
    if not output_url:
        raise BackgroundRemovalError("Aliyun image segmentation succeeded but returned no image URL.")
    return output_url


def read_aliyun_credentials() -> AliyunCredentials:
    raw_credentials = config_value("ALIYUN_VIAPI_CREDENTIALS")
    if not raw_credentials:
        raise BackgroundRemovalError("Transparent background post-processing requires ALIYUN_VIAPI_CREDENTIALS.")
    separator_index = raw_credentials.find(":")
    access_key_id = raw_credentials[:separator_index].strip()
    access_key_secret = raw_credentials[separator_index + 1 :].strip()
    if separator_index <= 0 or not access_key_id or not access_key_secret:
        raise BackgroundRemovalError("ALIYUN_VIAPI_CREDENTIALS must use the format AccessKeyId:AccessKeySecret.")
    return AliyunCredentials(access_key_id=access_key_id, access_key_secret=access_key_secret)


def build_signed_aliyun_url(
    credentials: AliyunCredentials,
    business_params: dict[str, str],
    now: datetime | None = None,
    nonce: str | None = None,
) -> str:
    params = {
        **business_params,
        "Format": "JSON",
        "Version": ALIYUN_IMAGESEG_VERSION,
        "AccessKeyId": credentials.access_key_id,
        "SignatureMethod": "HMAC-SHA1",
        "Timestamp": _format_aliyun_timestamp(now or datetime.now(UTC)),
        "SignatureVersion": "1.0",
        "SignatureNonce": nonce or uuid4().hex,
        "RegionId": "cn-shanghai",
    }
    canonical_query = _build_canonical_query(params)
    string_to_sign = f"POST&{_percent_encode('/')}&{_percent_encode(canonical_query)}"
    signature = base64.b64encode(
        hmac.new(
            f"{credentials.access_key_secret}&".encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha1,
        ).digest()
    ).decode("ascii")
    signed_query = f"Signature={_percent_encode(signature)}&{canonical_query}"
    return f"{ALIYUN_IMAGESEG_ENDPOINT}?{signed_query}"


def _build_canonical_query(params: dict[str, str]) -> str:
    return "&".join(f"{_percent_encode(key)}={_percent_encode(params[key])}" for key in sorted(params))


def _percent_encode(value: str) -> str:
    return quote(value, safe="~").replace("+", "%20").replace("*", "%2A")


def _format_aliyun_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_response_payload(body: bytes) -> Any:
    if not body:
        return None
    text = body.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _extract_segmented_image_url(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("Data")
    if not isinstance(data, dict):
        return None
    value = data.get("ImageURL")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _format_error(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("Message", "message", "Code", "code"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return "Unknown provider error"
