from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from PIL import Image, UnidentifiedImageError

from pixelator.ai.aliyun_rpc import (
    AliyunCredentialsError,
    build_signed_aliyun_url,
    format_provider_error,
    parse_response_payload,
    read_aliyun_credentials,
)
from pixelator.ai.dashscope_client import HttpTransport, UrllibTransport

ALIYUN_IMAGEENHAN_ENDPOINT = "https://imageenhan.cn-shanghai.aliyuncs.com/"
ALIYUN_IMAGEENHAN_SDK_ENDPOINT = "imageenhan.cn-shanghai.aliyuncs.com"
ALIYUN_IMAGEENHAN_VERSION = "2019-09-30"
SUPER_RESOLUTION_ACTION = "MakeSuperResolutionImage"
SUPER_RESOLUTION_FORMATS = ("png", "jpg", "bmp")


class SuperResolutionError(RuntimeError):
    """Raised when Aliyun image super-resolution cannot complete."""


@dataclass(frozen=True)
class SuperResolutionOptions:
    source_path: Path
    upscale_factor: int = 2
    output_format: str = "png"
    jpg_quality: int = 95


@dataclass(frozen=True)
class SuperResolutionResult:
    source_path: Path
    output_path: Path
    source_url: str | None
    output_url: str
    before_size: tuple[int, int]
    after_size: tuple[int, int]
    upscale_factor: int
    output_format: str


class SuperResolutionSdkRunner(Protocol):
    def upscale_local(
        self,
        source_path: Path,
        upscale_factor: int,
        output_format: str,
        output_quality: int | None,
        timeout: float,
    ) -> str: ...


class SuperResolutionClient:
    def __init__(
        self,
        transport: HttpTransport | None = None,
        sdk_runner: SuperResolutionSdkRunner | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.transport = transport or UrllibTransport()
        self.sdk_runner = sdk_runner
        self.timeout = timeout

    def upscale(self, options: SuperResolutionOptions, output_dir: Path) -> SuperResolutionResult:
        _validate_options(options.upscale_factor, options.output_format, options.jpg_quality)
        source_path = options.source_path
        if not source_path.exists() or not source_path.is_file():
            raise SuperResolutionError(f"Source image does not exist: {source_path}")
        before_size = _image_size(source_path)
        output_quality = options.jpg_quality if options.output_format == "jpg" else None
        output_url = self._upscale_local_image(
            source_path,
            options.upscale_factor,
            options.output_format,
            output_quality,
        )
        output_path = self._download_output(
            output_url,
            output_dir,
            source_path.stem,
            options.upscale_factor,
            options.output_format,
        )
        return SuperResolutionResult(
            source_path=source_path,
            output_path=output_path,
            source_url=None,
            output_url=output_url,
            before_size=before_size,
            after_size=_image_size(output_path),
            upscale_factor=options.upscale_factor,
            output_format=options.output_format,
        )

    def upscale_url(
        self,
        image_url: str,
        output_dir: Path,
        *,
        source_label: str = "remote_image",
        upscale_factor: int = 2,
        output_format: str = "png",
        jpg_quality: int = 95,
    ) -> Path:
        _validate_options(upscale_factor, output_format, jpg_quality)
        output_quality = jpg_quality if output_format == "jpg" else None
        output_url = make_super_resolution_image_url(
            image_url,
            upscale_factor=upscale_factor,
            output_format=output_format,
            output_quality=output_quality,
            transport=self.transport,
            timeout=self.timeout,
        )
        return self._download_output(output_url, output_dir, source_label, upscale_factor, output_format)

    def _upscale_local_image(
        self,
        source_path: Path,
        upscale_factor: int,
        output_format: str,
        output_quality: int | None,
    ) -> str:
        runner = self.sdk_runner or _AliyunImageEnhancementSdkRunner()
        try:
            return runner.upscale_local(source_path, upscale_factor, output_format, output_quality, self.timeout)
        except AliyunCredentialsError as exc:
            raise SuperResolutionError("ALIYUN_VIAPI_CREDENTIALS is required for super resolution.") from exc

    def _download_output(
        self,
        output_url: str,
        output_dir: Path,
        source_stem: str,
        upscale_factor: int,
        output_format: str,
    ) -> Path:
        if not output_url.startswith(("http://", "https://")):
            raise SuperResolutionError("Aliyun super-resolution returned an unsupported output URL.")
        response = self.transport.get(output_url, None, self.timeout)
        if response.status < 200 or response.status >= 300:
            payload = parse_response_payload(response.body)
            raise SuperResolutionError(f"Failed to download super-resolution output: {format_provider_error(payload)}")
        if not response.body:
            raise SuperResolutionError("Super-resolution output response is empty.")

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / _output_filename(source_stem, upscale_factor, output_format)
        output_path.write_bytes(response.body)
        return output_path


def make_super_resolution_image_url(
    image_url: str,
    *,
    upscale_factor: int = 2,
    output_format: str = "png",
    output_quality: int | None = None,
    transport: HttpTransport | None = None,
    timeout: float = 120.0,
) -> str:
    if not image_url.startswith(("http://", "https://")):
        raise SuperResolutionError("Aliyun super-resolution RPC requires an http image URL.")
    _validate_options(upscale_factor, output_format, output_quality or 95)
    try:
        credentials = read_aliyun_credentials()
    except AliyunCredentialsError as exc:
        raise SuperResolutionError("ALIYUN_VIAPI_CREDENTIALS is required for super resolution.") from exc

    business_params = {
        "Action": SUPER_RESOLUTION_ACTION,
        "Url": image_url,
        "UpscaleFactor": str(upscale_factor),
        "OutputFormat": output_format,
    }
    if output_quality is not None:
        business_params["OutputQuality"] = str(output_quality)
    request_url = build_signed_aliyun_url(
        credentials,
        business_params,
        endpoint=ALIYUN_IMAGEENHAN_ENDPOINT,
        version=ALIYUN_IMAGEENHAN_VERSION,
    )
    response = (transport or UrllibTransport()).post(request_url, None, timeout)
    payload = parse_response_payload(response.body)
    if response.status < 200 or response.status >= 300:
        raise SuperResolutionError(f"Aliyun super-resolution failed ({response.status}): {format_provider_error(payload)}")
    output_url = _extract_data_url(payload)
    if not output_url:
        raise SuperResolutionError("Aliyun super-resolution succeeded but returned no Data.Url.")
    return output_url


class _AliyunImageEnhancementSdkRunner:
    def upscale_local(
        self,
        source_path: Path,
        upscale_factor: int,
        output_format: str,
        output_quality: int | None,
        timeout: float,
    ) -> str:
        credentials = read_aliyun_credentials()
        try:
            from alibabacloud_imageenhan20190930.client import Client
            from alibabacloud_imageenhan20190930 import models as imageenhan_models
            from alibabacloud_tea_openapi import models as open_api_models
            from alibabacloud_tea_util import models as util_models
        except ImportError as exc:
            raise SuperResolutionError("Aliyun imageenhan SDK is required for local-file super resolution.") from exc

        config = open_api_models.Config(
            access_key_id=credentials.access_key_id,
            access_key_secret=credentials.access_key_secret,
            endpoint=ALIYUN_IMAGEENHAN_SDK_ENDPOINT,
        )
        runtime = util_models.RuntimeOptions(
            connect_timeout=max(1, int(timeout * 1000)),
            read_timeout=max(1, int(timeout * 1000)),
        )
        with source_path.open("rb") as stream:
            request = imageenhan_models.MakeSuperResolutionImageAdvanceRequest(
                url_object=stream,
                upscale_factor=upscale_factor,
                output_format=output_format,
                output_quality=output_quality,
            )
            try:
                response = Client(config).make_super_resolution_image_advance(request, runtime)
            except Exception as exc:  # noqa: BLE001 - SDK exceptions vary by provider response.
                message = _redact_credentials(str(exc), credentials.access_key_id, credentials.access_key_secret)
                raise SuperResolutionError(f"Aliyun super-resolution failed: {message}") from exc
        output_url = _extract_sdk_data_url(response)
        if not output_url:
            raise SuperResolutionError("Aliyun super-resolution succeeded but returned no Data.Url.")
        return output_url


def _validate_options(upscale_factor: int, output_format: str, jpg_quality: int) -> None:
    if upscale_factor not in {1, 2, 3, 4}:
        raise SuperResolutionError("UpscaleFactor must be 1, 2, 3, or 4.")
    if output_format not in SUPER_RESOLUTION_FORMATS:
        raise SuperResolutionError("OutputFormat must be png, jpg, or bmp.")
    if not 1 <= jpg_quality <= 100:
        raise SuperResolutionError("jpg quality must be between 1 and 100.")


def _extract_data_url(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("Data")
    if not isinstance(data, dict):
        return None
    value = data.get("Url")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _extract_sdk_data_url(response: Any) -> str | None:
    body = getattr(response, "body", None)
    data = getattr(body, "data", None)
    value = getattr(data, "url", None)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _image_size(path: Path) -> tuple[int, int]:
    try:
        with Image.open(path) as image:
            return image.size
    except (OSError, UnidentifiedImageError) as exc:
        raise SuperResolutionError(f"Could not read image dimensions: {path}") from exc


def _output_filename(source_stem: str, upscale_factor: int, output_format: str) -> str:
    safe_stem = "".join(char if char.isalnum() or char in "-_" else "_" for char in source_stem).strip("_")
    safe_stem = safe_stem[:48] or "super_resolution"
    return f"{safe_stem}_sr{upscale_factor}x_{time.time_ns():x}.{output_format}"


def _redact_credentials(message: str, access_key_id: str, access_key_secret: str) -> str:
    redacted = message
    for value in (access_key_id, access_key_secret):
        if value:
            redacted = redacted.replace(value, "<redacted>")
    return redacted
