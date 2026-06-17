from __future__ import annotations

import http.client
import json
import mimetypes
import select
import socket
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen

from pixelator.layering.archive import validate_layer_zip
from pixelator.layering.types import ErrorCode, JobStatus, LayerManifest, LayeringError


class LayerSplitClient:
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        poll_interval: float = 2.0,
        timeout: float = 600.0,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.poll_interval = poll_interval
        self.timeout = timeout

    def split_image(
        self,
        image_path: str | Path,
        output_path: str | Path,
        target_layers: int | None = None,
    ) -> LayerManifest:
        job_id = self.submit_split(image_path, target_layers=target_layers)
        artifact_url = self.wait_for_artifact(job_id)
        self.download_artifact(artifact_url, output_path)
        return validate_layer_zip(output_path)

    def submit_split(self, image_path: str | Path, target_layers: int | None = None) -> str:
        image = Path(image_path)
        request_json = {
            "target_layers": target_layers,
            "crop_alpha": True,
            "zip_result": True,
        }
        content_type = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
        body, multipart_type = _multipart_body(
            fields={"request": (json.dumps(request_json).encode("utf-8"), "application/json")},
            files={
                "image": (
                    image.name,
                    image.read_bytes(),
                    content_type,
                )
            },
        )
        response = self._request_json(
            "POST",
            "/v1/layer-splits",
            body=body,
            headers={
                "Content-Type": multipart_type,
                "Expect": "100-continue",
            },
        )
        job_id = response.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            raise LayeringError(ErrorCode.JOB_FAILED, "layer split response is missing job_id")
        return job_id

    def wait_for_artifact(self, job_id: str) -> str:
        deadline = time.monotonic() + self.timeout
        job_path = f"/v1/layer-splits/{quote(job_id, safe='')}"
        artifact_path = f"{job_path}/artifact"

        while True:
            if time.monotonic() >= deadline:
                raise LayeringError(ErrorCode.JOB_TIMEOUT, f"layer split job timed out: {job_id}")

            response = self._request_json("GET", job_path)
            status = _job_status(response.get("status"))

            if status == JobStatus.SUCCEEDED:
                artifact_url = response.get("artifact_url") or artifact_path
                if not isinstance(artifact_url, str) or not artifact_url:
                    raise LayeringError(ErrorCode.JOB_FAILED, f"layer split job has invalid artifact URL: {job_id}")
                return artifact_url

            if status in {JobStatus.FAILED, JobStatus.CANCELED, JobStatus.UNKNOWN}:
                detail = _response_detail(response) or f"layer split job {status.value}: {job_id}"
                raise LayeringError(ErrorCode.JOB_FAILED, detail)

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LayeringError(ErrorCode.JOB_TIMEOUT, f"layer split job timed out: {job_id}")
            time.sleep(min(self.poll_interval, remaining))

    def download_artifact(self, artifact_url: str, output_path: str | Path) -> Path:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        request = self._request("GET", self._resolve_url(artifact_url), headers={"Accept": "application/zip"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                destination.write_bytes(response.read())
        except HTTPError as exc:
            raise _http_error(exc) from exc
        except (OSError, URLError) as exc:
            raise LayeringError(ErrorCode.JOB_FAILED, f"failed to download layer artifact: {exc}") from exc

        validate_layer_zip(destination)
        return destination

    def _request_json(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = self._resolve_url(path)
        request_headers = {"Accept": "application/json", **(headers or {})}
        if method == "POST" and body is not None and request_headers.get("Expect") == "100-continue":
            data = self._post_with_continue(url, body, request_headers)
        else:
            request = self._request(method, url, body=body, headers=request_headers)
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    data = response.read()
            except HTTPError as exc:
                raise _http_error(exc) from exc
            except (OSError, URLError) as exc:
                raise LayeringError(ErrorCode.JOB_FAILED, f"layer split request failed: {exc}") from exc

        if not data:
            return {}

        try:
            decoded = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LayeringError(ErrorCode.JOB_FAILED, "layer split response is invalid JSON") from exc

        if not isinstance(decoded, dict):
            raise LayeringError(ErrorCode.JOB_FAILED, "layer split response must be a JSON object")
        return decoded

    def _request(
        self,
        method: str,
        url: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> Request:
        request_headers = {
            "Authorization": f"Bearer {self.api_key}",
            **(headers or {}),
        }
        return Request(url, data=body, headers=request_headers, method=method)

    def _resolve_url(self, url_or_path: str) -> str:
        parsed = urlparse(url_or_path)
        if parsed.scheme and parsed.netloc:
            return url_or_path
        return urljoin(f"{self.endpoint}/", url_or_path)

    def _post_with_continue(self, url: str, body: bytes, headers: dict[str, str]) -> bytes:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
            raise LayeringError(ErrorCode.JOB_FAILED, f"unsupported layer split endpoint: {url}")

        connection_type = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        request_headers = {
            "Authorization": f"Bearer {self.api_key}",
            **headers,
            "Content-Length": str(len(body)),
            "Connection": "close",
        }
        connection = connection_type(parsed.hostname, port=parsed.port, timeout=self.timeout)

        try:
            connection.putrequest("POST", path)
            for name, value in request_headers.items():
                connection.putheader(name, value)
            connection.endheaders()

            sock = connection.sock
            if sock is None:
                raise LayeringError(ErrorCode.JOB_FAILED, "layer split connection was not opened")
            early_response_wait = min(0.2, max(0.0, self.timeout))
            if not _socket_has_early_response(sock, early_response_wait):
                sock.sendall(body)
            elif _peek_status_is_continue(sock):
                sock.sendall(body)

            response = connection.getresponse()
            data = response.read()
            if response.status >= 400:
                raise _status_error(response.status, response.reason, response.headers, data)
            return data
        except LayeringError:
            raise
        except (OSError, http.client.HTTPException) as exc:
            raise LayeringError(ErrorCode.JOB_FAILED, f"layer split request failed: {exc}") from exc
        finally:
            connection.close()


def _multipart_body(
    fields: dict[str, tuple[bytes, str]],
    files: dict[str, tuple[str, bytes, str]],
) -> tuple[bytes, str]:
    boundary = f"----pixelator-layering-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for name, (value, content_type) in fields.items():
        chunks.append(f"--{boundary}\r\n".encode("ascii"))
        chunks.append(f'Content-Disposition: form-data; name="{_escape_header(name)}"\r\n'.encode("utf-8"))
        chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode("ascii"))
        chunks.append(value)
        chunks.append(b"\r\n")

    for name, (filename, content, content_type) in files.items():
        chunks.append(f"--{boundary}\r\n".encode("ascii"))
        chunks.append(
            (
                f'Content-Disposition: form-data; name="{_escape_header(name)}"; '
                f'filename="{_escape_header(filename)}"\r\n'
            ).encode("utf-8")
        )
        chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode("ascii"))
        chunks.append(content)
        chunks.append(b"\r\n")

    chunks.append(f"--{boundary}--\r\n".encode("ascii"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _http_error(error: HTTPError) -> LayeringError:
    return _status_error(error.code, error.reason, error.headers, error.read())


def _status_error(status: int, reason: str, headers: Any, body: bytes) -> LayeringError:
    detail = _response_detail(_decode_error_body(body))
    message = detail or reason or f"HTTP {status}"
    request_id = headers.get("X-Request-ID") or headers.get("X-Request-Id")

    if status in {401, 403}:
        return LayeringError(ErrorCode.AUTH_FAILED, message, request_id=request_id)
    if status == 413:
        return LayeringError(ErrorCode.INPUT_TOO_LARGE, message, request_id=request_id)
    return LayeringError(ErrorCode.JOB_FAILED, message, request_id=request_id)


def _decode_error_body(body: bytes) -> Any:
    if not body:
        return {}

    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return {}

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text.strip()


def _response_detail(data: Any) -> str | None:
    if isinstance(data, str):
        return data or None
    if not isinstance(data, dict):
        return None

    for key in ("detail", "message"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value

    error = data.get("error")
    if isinstance(error, str) and error:
        return error
    if isinstance(error, dict):
        return _response_detail(error)

    return None


def _job_status(value: Any) -> JobStatus:
    if not isinstance(value, str):
        return JobStatus.UNKNOWN
    try:
        return JobStatus(value)
    except ValueError:
        return JobStatus.UNKNOWN


def _escape_header(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _socket_has_early_response(sock: socket.socket | None, wait_seconds: float) -> bool:
    if sock is None:
        return False
    readable, _, _ = select.select([sock], [], [], wait_seconds)
    return bool(readable)


def _peek_status_is_continue(sock: socket.socket | None) -> bool:
    if sock is None:
        return False
    try:
        data = sock.recv(64, socket.MSG_PEEK)
    except OSError:
        return False
    status_line = data.split(b"\r\n", 1)[0]
    parts = status_line.split(None, 2)
    return len(parts) >= 2 and parts[1] == b"100"
