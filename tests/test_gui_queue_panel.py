import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtWidgets import QApplication

import pytest

from pixelator.gui.queue_panel import QueuePanel


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_queue_panel_filters_dropped_media_files(tmp_path: Path, qapp):
    image = tmp_path / "sprite.png"
    video = tmp_path / "clip.mp4"
    unsupported = tmp_path / "notes.txt"
    folder = tmp_path / "folder"
    nested_image = folder / "inside.png"

    image.write_bytes(b"fake")
    video.write_bytes(b"fake")
    unsupported.write_text("ignore", encoding="utf-8")
    folder.mkdir()
    nested_image.write_bytes(b"fake")

    mime_data = QMimeData()
    mime_data.setUrls(
        [
            QUrl.fromLocalFile(str(image)),
            QUrl.fromLocalFile(str(video)),
            QUrl.fromLocalFile(str(unsupported)),
            QUrl.fromLocalFile(str(folder)),
            QUrl("https://example.test/remote.png"),
        ]
    )

    panel = QueuePanel()

    assert panel._media_files_from_mime_data(mime_data) == [str(image), str(video), str(folder)]
