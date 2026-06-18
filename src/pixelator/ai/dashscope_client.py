from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import unquote_to_bytes
from urllib.request import Request, urlopen

from pixelator.ai.background_removal import remove_image_background
from pixelator.ai.constants import (
    ASSET_SIZES,
    DEFAULT_DASHSCOPE_IMAGE_ENDPOINT,
    DEFAULT_DASHSCOPE_TASK_ENDPOINT,
    DEFAULT_IMAGE_MODEL,
    DEFAULT_TASK_POLL_ATTEMPTS,
    DEFAULT_TASK_POLL_INTERVAL_SECONDS,
)
from pixelator.ai.env import config_value
from pixelator.ai.types import AiGenerationRequest, DashScopeConfig, DownloadedImage, PromptResult


class DashScopeError(RuntimeError):
    """Raised for DashScope configuration, provider, or download failures."""


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes
    headers: dict[str, str] | None = None


class HttpTransport(Protocol):
    def request_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout: float,
    ) -> HttpResponse: ...

    def get(self, url: str, headers: dict[str, str] | None, timeout: float) -> HttpResponse: ...

    def post(self, url: str, headers: dict[str, str] | None, timeout: float) -> HttpResponse: ...


class UrllibTransport:
    def request_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout: float,
    ) -> HttpResponse:
        body = json.dumps(payload).encode("utf-8")
        request = Request(url, data=body, headers=headers, method="POST")
        return self._open(request, timeout)

    def get(self, url: str, headers: dict[str, str] | None, timeout: float) -> HttpResponse:
        return self._open(Request(url, headers=headers or {}, method="GET"), timeout)

    def post(self, url: str, headers: dict[str, str] | None, timeout: float) -> HttpResponse:
        return self._open(Request(url, data=b"", headers=headers or {}, method="POST"), timeout)

    def _open(self, request: Request, timeout: float) -> HttpResponse:
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310 - user-configured trusted endpoints.
                return HttpResponse(
                    status=response.status,
                    body=response.read(),
                    headers={key: value for key, value in response.headers.items()},
                )
        except HTTPError as exc:
            return HttpResponse(status=exc.code, body=exc.read(), headers=dict(exc.headers.items()))
        except URLError as exc:
            raise DashScopeError(f"DashScope network error: {exc.reason}") from exc


class DashScopeClient:
    def __init__(
        self,
        config: DashScopeConfig | None = None,
        transport: HttpTransport | None = None,
        sleeper=time.sleep,
    ) -> None:
        self.config = config or DashScopeConfig()
        self.transport = transport or UrllibTransport()
        self.sleeper = sleeper

    def generate(self, request: AiGenerationRequest, prompt: PromptResult) -> list[DownloadedImage]:
        request.validate()
        api_key = self._api_key()
        model = self._model()
        downloads: list[DownloadedImage] = []
        for _index in range(request.count):
            downloads.extend(self._generate_once(api_key, model, request, prompt))
        return downloads[: request.count]

    def _generate_once(
        self,
        api_key: str,
        model: str,
        request: AiGenerationRequest,
        prompt: PromptResult,
    ) -> list[DownloadedImage]:
        payload = self._request_payload(model, request, prompt, count=1)
        response = self.transport.request_json(
            self._image_endpoint(),
            payload,
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            self.config.timeout_seconds,
        )
        body = _parse_json_response(response.body)
        if response.status < 200 or response.status >= 300:
            raise DashScopeError(f"DashScope image generation failed ({response.status}): {_format_error(body)}")

        images = _extract_generated_images(body)
        if not images:
            task_id = _task_id(body)
            if task_id:
                images = _extract_generated_images(self._poll_task(task_id, api_key))
        if not images:
            raise DashScopeError("DashScope image generation succeeded but returned no image URL.")
        if request.background == "transparent":
            images = [self._remove_image_background(image) for image in images]
        return [self._download_image(image) for image in images[:1]]

    def _remove_image_background(self, image: dict[str, str | None]) -> dict[str, str | None]:
        url = image.get("url") or ""
        return {
            **image,
            "url": remove_image_background(url, self.transport, self.config.timeout_seconds),
        }

    def _poll_task(self, task_id: str, api_key: str) -> Any:
        endpoint = self._task_endpoint().rstrip("/")
        attempts = self._poll_attempts()
        interval = self._poll_interval_seconds()
        for index in range(attempts):
            if index > 0 and interval:
                self.sleeper(interval)
            response = self.transport.get(
                f"{endpoint}/{task_id}",
                {"Authorization": f"Bearer {api_key}"},
                self.config.timeout_seconds,
            )
            body = _parse_json_response(response.body)
            if response.status < 200 or response.status >= 300:
                raise DashScopeError(f"DashScope task polling failed ({response.status}): {_format_error(body)}")
            status = (_task_status(body) or "").upper()
            if status == "SUCCEEDED":
                return body
            if status in {"FAILED", "CANCELED", "SUSPENDED"}:
                raise DashScopeError(f"DashScope task {status.lower()}: {_format_error(body)}")
            if _extract_generated_images(body):
                return body
        raise DashScopeError("DashScope task polling timed out before image generation completed.")

    def _download_image(self, image: dict[str, str | None]) -> DownloadedImage:
        url = image.get("url") or ""
        if url.startswith("data:image/"):
            return DownloadedImage(data=_decode_data_url(url), source_url=url, seed=image.get("seed"))
        if not (url.startswith("http://") or url.startswith("https://")):
            raise DashScopeError("Unsupported generated image URL format.")
        response = self.transport.get(url, None, self.config.timeout_seconds)
        if response.status < 200 or response.status >= 300:
            raise DashScopeError(f"Failed to download generated image ({response.status}).")
        if not response.body:
            raise DashScopeError("Generated image response is empty.")
        return DownloadedImage(data=response.body, source_url=url, seed=image.get("seed"))

    def _request_payload(
        self,
        model: str,
        request: AiGenerationRequest,
        prompt: PromptResult,
        count: int,
    ) -> dict[str, Any]:
        return {
            "model": model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": prompt.positive_prompt}],
                    }
                ]
            },
            "parameters": {
                "negative_prompt": prompt.negative_prompt,
                "prompt_extend": False,
                "watermark": False,
                "size": _dashscope_size(request.size),
                "n": count,
            },
        }

    def _api_key(self) -> str:
        api_key = self.config.api_key.strip() or config_value("DASHSCOPE_API_KEY")
        if not api_key:
            raise DashScopeError("DASHSCOPE_API_KEY is not configured.")
        return api_key

    def _model(self) -> str:
        return self.config.model.strip() or config_value("IMAGE_MODEL", DEFAULT_IMAGE_MODEL)

    def _image_endpoint(self) -> str:
        return (
            self.config.image_endpoint.strip()
            or config_value("DASHSCOPE_IMAGE_ENDPOINT", DEFAULT_DASHSCOPE_IMAGE_ENDPOINT)
        )

    def _task_endpoint(self) -> str:
        return (
            self.config.task_endpoint.strip()
            or config_value("DASHSCOPE_TASK_ENDPOINT", DEFAULT_DASHSCOPE_TASK_ENDPOINT)
        )

    def _poll_attempts(self) -> int:
        env_value = config_value("DASHSCOPE_TASK_POLL_ATTEMPTS")
        if env_value:
            try:
                return max(1, int(env_value))
            except ValueError:
                pass
        return max(1, self.config.poll_attempts or DEFAULT_TASK_POLL_ATTEMPTS)

    def _poll_interval_seconds(self) -> float:
        env_value = config_value("DASHSCOPE_TASK_POLL_INTERVAL_MS")
        if env_value:
            try:
                return max(0.0, int(env_value) / 1000)
            except ValueError:
                pass
        return max(0.0, self.config.poll_interval_seconds or DEFAULT_TASK_POLL_INTERVAL_SECONDS)


def _dashscope_size(size: str) -> str:
    width, height = [int(part) for part in size.split("x", 1)]
    if size in ASSET_SIZES:
        return f"{max(width, 512)}*{max(height, 512)}"
    return f"{width}*{height}"


def _parse_json_response(body: bytes) -> Any:
    if not body:
        return None
    text = body.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _extract_generated_images(payload: Any) -> list[dict[str, str | None]]:
    images: list[dict[str, str | None]] = []
    _collect_image_urls(payload, images)
    deduped: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for image in images:
        url = image.get("url") or ""
        if url not in seen:
            deduped.append(image)
            seen.add(url)
    return deduped


def _collect_image_urls(value: Any, images: list[dict[str, str | None]]) -> None:
    if isinstance(value, str) and _is_generated_image_url(value):
        images.append({"url": value, "seed": None})
        return
    if isinstance(value, list):
        for item in value:
            _collect_image_urls(item, images)
        return
    if not isinstance(value, dict):
        return
    seed = _string_value(value.get("seed"))
    url = (
        _string_value(value.get("url"))
        or _string_value(value.get("image_url"))
        or _string_value(value.get("output_image_url"))
        or _string_value(value.get("image"))
    )
    if url and _is_generated_image_url(url):
        images.append({"url": url, "seed": seed})
    for item in value.values():
        _collect_image_urls(item, images)


def _is_generated_image_url(value: str) -> bool:
    return value.startswith(("http://", "https://", "data:image/"))


def _task_id(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    output = payload.get("output")
    if not isinstance(output, dict):
        return None
    return _string_value(output.get("task_id"))


def _task_status(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    output = payload.get("output")
    if not isinstance(output, dict):
        return None
    return _string_value(output.get("task_status"))


def _format_error(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("message", "error", "code"):
            value = _string_value(payload.get(key))
            if value:
                return value
        output = payload.get("output")
        if isinstance(output, dict):
            for key in ("message", "error", "code"):
                value = _string_value(output.get(key))
                if value:
                    return value
    return "Unknown provider error"


def _string_value(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    return None


def _decode_data_url(data_url: str) -> bytes:
    header, _, payload = data_url.partition(",")
    if not payload:
        raise DashScopeError("Unsupported generated image data URL format.")
    if ";base64" in header:
        return base64.b64decode(payload)
    return unquote_to_bytes(payload)
