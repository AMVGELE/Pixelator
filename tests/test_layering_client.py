import json
import threading
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socket import timeout as SocketTimeout

import pytest
from PIL import Image

from pixelator.layering.archive import write_layer_zip
from pixelator.layering.client import LayerSplitClient
from pixelator.layering.types import ErrorCode, LayeringError


class FakeLayerHandler(BaseHTTPRequestHandler):
    artifact_path: Path
    observed_authorization: str | None = None
    observed_content_type: str | None = None
    observed_body: bytes | None = None
    observed_file_name: str | None = None
    observed_form_fields: set[str] = set()
    observed_request_json: dict | None = None

    @classmethod
    def reset_observations(cls):
        cls.observed_authorization = None
        cls.observed_content_type = None
        cls.observed_body = None
        cls.observed_file_name = None
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
    assert {"image", "request"} <= FakeLayerHandler.observed_form_fields
    assert FakeLayerHandler.observed_request_json == {
        "target_layers": 4,
        "crop_alpha": True,
        "zip_result": True,
    }


def test_client_maps_auth_failure_to_auth_error(tmp_path: Path):
    class AuthHandler(FakeLayerHandler):
        def do_POST(self):
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
