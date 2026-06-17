import json
import threading
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socket import timeout as SocketTimeout

import pytest
from PIL import Image

from pixelator.layering.archive import validate_layer_zip, write_layer_zip
from pixelator.layering.client import LayerSplitClient
from pixelator.layering.types import ErrorCode, LayeringError


class FakeLayerHandler(BaseHTTPRequestHandler):
    artifact_path: Path
    observed_authorization: str | None = None
    observed_content_type: str | None = None
    observed_body: bytes | None = None
    observed_file_name: str | None = None
    observed_image_bytes: bytes | None = None
    observed_image_content_type: str | None = None
    observed_form_fields: set[str] = set()
    observed_request_json: dict | None = None

    @classmethod
    def reset_observations(cls):
        cls.observed_authorization = None
        cls.observed_content_type = None
        cls.observed_body = None
        cls.observed_file_name = None
        cls.observed_image_bytes = None
        cls.observed_image_content_type = None
        cls.observed_form_fields = set()
        cls.observed_request_json = None

    def do_POST(self):
        if self.path != "/v1/layer-splits":
            self.send_error(404)
            return
        self.__class__.observed_authorization = self.headers.get("Authorization")
        self.__class__.observed_content_type = self.headers.get("Content-Type")
        content_length = int(self.headers.get("Content-Length", "0"))
        self.connection.settimeout(0.1)
        try:
            upload_body = self.rfile.read(content_length)
        except (OSError, SocketTimeout):
            self.send_error(400, "request body was not uploaded")
            return
        if len(upload_body) != content_length:
            self.send_error(400, "request body was truncated")
            return
        self.__class__.observed_body = upload_body
        self._parse_multipart(upload_body)
        body = json.dumps({"job_id": "job_123", "status": "queued"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/v1/layer-splits/job_123":
            body = json.dumps(
                {
                    "job_id": "job_123",
                    "status": "succeeded",
                    "artifact_url": "/v1/layer-splits/job_123/artifact",
                    "error": None,
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/v1/layer-splits/job_123/artifact":
            data = self.artifact_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_error(404)

    def log_message(self, format, *args):
        return

    def _parse_multipart(self, upload_body: bytes):
        content_type = self.headers.get("Content-Type", "")
        message = BytesParser(policy=policy.default).parsebytes(
            b"Content-Type: "
            + content_type.encode("utf-8")
            + b"\r\nMIME-Version: 1.0\r\n\r\n"
            + upload_body
        )
        for part in message.iter_parts():
            field_name = part.get_param("name", header="content-disposition")
            if field_name is None:
                continue
            self.__class__.observed_form_fields.add(field_name)
            if field_name == "image":
                self.__class__.observed_file_name = part.get_filename()
                self.__class__.observed_image_bytes = part.get_payload(decode=True)
                self.__class__.observed_image_content_type = part.get_content_type()
            if field_name == "request":
                payload = part.get_payload(decode=True) or b"{}"
                self.__class__.observed_request_json = json.loads(payload.decode("utf-8"))


def test_client_submits_polls_and_downloads_artifact(tmp_path: Path):
    source = tmp_path / "hero.png"
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(source)
    artifact = tmp_path / "artifact.zip"
    write_layer_zip(source, Image.open(source), [Image.open(source)], artifact, backend="mock", model_id="mock")
    FakeLayerHandler.artifact_path = artifact
    FakeLayerHandler.reset_observations()
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeLayerHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}"

    try:
        client = LayerSplitClient(endpoint=endpoint, api_key="secret", poll_interval=0.01, timeout=2.0)
        downloaded = client.split_image(source, tmp_path / "downloaded.zip", target_layers=4)
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert downloaded.source.file_name == "hero.png"
    assert (tmp_path / "downloaded.zip").exists()
    assert FakeLayerHandler.observed_authorization == "Bearer secret"
    assert FakeLayerHandler.observed_content_type is not None
    assert "multipart/form-data" in FakeLayerHandler.observed_content_type
    assert "boundary=" in FakeLayerHandler.observed_content_type
    assert FakeLayerHandler.observed_body
    assert FakeLayerHandler.observed_file_name == "hero.png"
    assert FakeLayerHandler.observed_image_bytes == source.read_bytes()
    assert FakeLayerHandler.observed_image_content_type == "image/png"
    assert {"image", "request"} <= FakeLayerHandler.observed_form_fields
    assert FakeLayerHandler.observed_request_json == {
        "target_layers": 4,
        "crop_alpha": True,
        "zip_result": True,
    }


def test_client_maps_auth_failure_to_auth_error(tmp_path: Path):
    class AuthHandler(FakeLayerHandler):
        def do_POST(self):
            content_length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(content_length)
            self.send_response(401)
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), AuthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    source = tmp_path / "hero.png"
    Image.new("RGBA", (2, 2), (0, 0, 0, 255)).save(source)

    try:
        client = LayerSplitClient(endpoint=f"http://127.0.0.1:{server.server_port}", api_key="bad", timeout=1.0)
        with pytest.raises(LayeringError) as exc_info:
            client.split_image(source, tmp_path / "out.zip")
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert exc_info.value.code == ErrorCode.AUTH_FAILED


def test_client_maps_413_to_input_too_large(tmp_path: Path):
    class TooLargeHandler(FakeLayerHandler):
        def do_POST(self):
            content_length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(content_length)
            body = json.dumps({"message": "image is too large"}).encode("utf-8")
            self.send_response(413)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    source = tmp_path / "hero.png"
    Image.new("RGBA", (2, 2), (0, 0, 0, 255)).save(source)
    server = ThreadingHTTPServer(("127.0.0.1", 0), TooLargeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        client = LayerSplitClient(endpoint=f"http://127.0.0.1:{server.server_port}", api_key="secret", timeout=1.0)
        with pytest.raises(LayeringError) as exc_info:
            client.split_image(source, tmp_path / "out.zip")
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert exc_info.value.code == ErrorCode.INPUT_TOO_LARGE
    assert "image is too large" in str(exc_info.value)


def test_client_surfaces_failed_job_error_message(tmp_path: Path):
    class FailedHandler(FakeLayerHandler):
        def do_GET(self):
            body = json.dumps({"job_id": "job_123", "status": "failed", "error": "layer model failed"}).encode(
                "utf-8"
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    source = tmp_path / "hero.png"
    Image.new("RGBA", (2, 2), (0, 0, 0, 255)).save(source)
    server = ThreadingHTTPServer(("127.0.0.1", 0), FailedHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        client = LayerSplitClient(
            endpoint=f"http://127.0.0.1:{server.server_port}",
            api_key="secret",
            poll_interval=0.01,
            timeout=1.0,
        )
        with pytest.raises(LayeringError) as exc_info:
            client.split_image(source, tmp_path / "out.zip")
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert exc_info.value.code == ErrorCode.JOB_FAILED
    assert "layer model failed" in str(exc_info.value)


def test_client_raises_timeout_when_job_never_finishes(tmp_path: Path):
    class RunningHandler(FakeLayerHandler):
        def do_GET(self):
            body = json.dumps({"job_id": "job_123", "status": "running"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    source = tmp_path / "hero.png"
    Image.new("RGBA", (2, 2), (0, 0, 0, 255)).save(source)
    server = ThreadingHTTPServer(("127.0.0.1", 0), RunningHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        client = LayerSplitClient(
            endpoint=f"http://127.0.0.1:{server.server_port}",
            api_key="secret",
            poll_interval=0.01,
            timeout=0.05,
        )
        with pytest.raises(LayeringError) as exc_info:
            client.split_image(source, tmp_path / "out.zip")
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert exc_info.value.code == ErrorCode.JOB_TIMEOUT


def test_cross_origin_artifact_download_omits_authorization(tmp_path: Path):
    class CrossOriginArtifactHandler(BaseHTTPRequestHandler):
        artifact_path: Path
        observed_authorization: str | None = None

        def do_GET(self):
            self.__class__.observed_authorization = self.headers.get("Authorization")
            data = self.__class__.artifact_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format, *args):
            return

    class CrossOriginJobHandler(FakeLayerHandler):
        artifact_url: str

        def do_GET(self):
            body = json.dumps(
                {
                    "job_id": "job_123",
                    "status": "succeeded",
                    "artifact_url": self.__class__.artifact_url,
                    "error": None,
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    source = tmp_path / "hero.png"
    Image.new("RGBA", (2, 2), (0, 0, 0, 255)).save(source)
    artifact = tmp_path / "artifact.zip"
    write_layer_zip(source, Image.open(source), [Image.open(source)], artifact, backend="mock", model_id="mock")
    CrossOriginArtifactHandler.artifact_path = artifact
    CrossOriginArtifactHandler.observed_authorization = None

    artifact_server = ThreadingHTTPServer(("127.0.0.1", 0), CrossOriginArtifactHandler)
    artifact_thread = threading.Thread(target=artifact_server.serve_forever, daemon=True)
    artifact_thread.start()
    CrossOriginJobHandler.artifact_url = f"http://127.0.0.1:{artifact_server.server_port}/artifact.zip"

    job_server = ThreadingHTTPServer(("127.0.0.1", 0), CrossOriginJobHandler)
    job_thread = threading.Thread(target=job_server.serve_forever, daemon=True)
    job_thread.start()

    try:
        client = LayerSplitClient(
            endpoint=f"http://127.0.0.1:{job_server.server_port}",
            api_key="secret",
            poll_interval=0.01,
            timeout=2.0,
        )
        client.split_image(source, tmp_path / "downloaded.zip")
    finally:
        job_server.shutdown()
        job_thread.join(timeout=2)
        artifact_server.shutdown()
        artifact_thread.join(timeout=2)

    assert CrossOriginArtifactHandler.observed_authorization is None


def test_invalid_downloaded_artifact_preserves_previous_valid_output(tmp_path: Path):
    class InvalidArtifactHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            data = b"not a zip"
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format, *args):
            return

    source = tmp_path / "hero.png"
    Image.new("RGBA", (2, 2), (0, 0, 0, 255)).save(source)
    output = tmp_path / "out.zip"
    write_layer_zip(source, Image.open(source), [Image.open(source)], output, backend="mock", model_id="mock")
    previous_bytes = output.read_bytes()

    server = ThreadingHTTPServer(("127.0.0.1", 0), InvalidArtifactHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        client = LayerSplitClient(endpoint=f"http://127.0.0.1:{server.server_port}", api_key="secret", timeout=1.0)
        with pytest.raises(LayeringError) as exc_info:
            client.download_artifact(f"http://127.0.0.1:{server.server_port}/artifact.zip", output)
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert exc_info.value.code == ErrorCode.ARTIFACT_INVALID
    assert output.read_bytes() == previous_bytes
    assert validate_layer_zip(output).source.file_name == "hero.png"


def test_client_source_does_not_use_raw_socket_peek():
    source = Path("src/pixelator/layering/client.py").read_text(encoding="utf-8")

    assert "MSG_PEEK" not in source
    assert "_peek_status_is_continue" not in source
