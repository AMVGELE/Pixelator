from __future__ import annotations

from PySide6.QtCore import Qt
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


class QueuePanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.add_button = QPushButton("Add")
        self.remove_button = QPushButton("Remove")
        self.start_button = QPushButton("Start")
        self.cancel_button = QPushButton("Cancel")
        self.list_widget = QListWidget()

        title = QLabel("Queue")
        title.setObjectName("panelTitle")

        action_row = QHBoxLayout()
        action_row.addWidget(self.add_button)
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
            meta = ""
            if job.width and job.height:
                meta = f" {job.width}x{job.height}"
            item = QListWidgetItem(f"{name}{meta}\n{job.status.value} - {job.progress}%")
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
