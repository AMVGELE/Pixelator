from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QMimeData, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelator.gui.models import VideoJob
from pixelator.media import is_media_path


class QueuePanel(QWidget):
    mediaFilesDropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.add_button = QPushButton("添加")
        self.folder_button = QPushButton("文件夹")
        self.remove_button = QPushButton("移除")
        self.start_button = QPushButton("开始")
        self.cancel_button = QPushButton("取消")
        self.list_widget = QListWidget()
        self.list_widget.setAcceptDrops(True)
        self.list_widget.viewport().setAcceptDrops(True)
        self.list_widget.installEventFilter(self)
        self.list_widget.viewport().installEventFilter(self)

        title = QLabel("队列")
        title.setObjectName("panelTitle")

        action_row = QHBoxLayout()
        action_row.addWidget(self.add_button)
        action_row.addWidget(self.folder_button)
        action_row.addWidget(self.remove_button)

        render_row = QHBoxLayout()
        render_row.addWidget(self.start_button)
        render_row.addWidget(self.cancel_button)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(action_row)
        layout.addLayout(render_row)
        layout.addWidget(self.list_widget, 1)

    def set_jobs(self, jobs: list[VideoJob]) -> None:
        selected = self.selected_job_id()
        self.list_widget.clear()
        for job in jobs:
            name = job.source_path.name
            kind = "图像" if job.is_image else "视频"
            meta = ""
            if job.width and job.height:
                meta = f" {job.width}x{job.height}"
            item = QListWidgetItem(f"{name}{meta} [{kind}]\n{_status_text(job.status.value)} - {job.progress}%")
            item.setData(Qt.ItemDataRole.UserRole, job.id)
            if job.error:
                item.setToolTip(job.error)
            self.list_widget.addItem(item)
            if selected == job.id:
                self.list_widget.setCurrentItem(item)

    def selected_job_id(self) -> str | None:
        item = self.list_widget.currentItem()
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return str(value) if value else None

    def dragEnterEvent(self, event) -> None:
        self._handle_drag_event(event)

    def dragMoveEvent(self, event) -> None:
        self._handle_drag_event(event)

    def dropEvent(self, event) -> None:
        self._handle_drop_event(event)

    def eventFilter(self, watched, event) -> bool:
        if watched in (self.list_widget, self.list_widget.viewport()):
            if event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
                return self._handle_drag_event(event)
            if event.type() == QEvent.Type.Drop:
                return self._handle_drop_event(event)
        return super().eventFilter(watched, event)

    def _handle_drag_event(self, event) -> bool:
        if self._media_files_from_mime_data(event.mimeData()):
            event.acceptProposedAction()
            return True
        event.ignore()
        return False

    def _handle_drop_event(self, event) -> bool:
        paths = self._media_files_from_mime_data(event.mimeData())
        if not paths:
            event.ignore()
            return False
        self.mediaFilesDropped.emit(paths)
        event.acceptProposedAction()
        return True

    def _media_files_from_mime_data(self, mime_data: QMimeData) -> list[str]:
        if not mime_data.hasUrls():
            return []
        paths = []
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.is_dir() or (path.is_file() and is_media_path(path)):
                paths.append(str(path))
        return paths
def _status_text(status: str) -> str:
    return {
        "queued": "排队",
        "running": "运行",
        "completed": "完成",
        "failed": "失败",
        "cancelled": "已取消",
    }.get(status, status)
