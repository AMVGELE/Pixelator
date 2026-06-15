from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QSlider,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from pixelator.config import CropConfig, TrimConfig
from pixelator.errors import PixelatorError
from pixelator.gui.models import JobQueue, JobStatus, RenderSettings, VideoJob
from pixelator.gui.preview import PreviewWidget, clamp_crop
from pixelator.gui.queue_panel import QueuePanel
from pixelator.gui.settings_panel import SettingsPanel
from pixelator.gui.worker import RenderWorker
from pixelator.video import extract_frame, probe_video


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.queue = JobQueue()
        self._loading_job = False
        self._syncing_crop_controls = False
        self._active_thread: QThread | None = None
        self._active_worker: RenderWorker | None = None
        self.queue_panel = QueuePanel()
        self.settings_panel = SettingsPanel()
        self.preview_widget = PreviewWidget()

        self.trim_start_spin = QDoubleSpinBox()
        self.trim_start_spin.setRange(0.0, 24 * 60 * 60.0)
        self.trim_start_spin.setDecimals(3)
        self.trim_start_spin.setSuffix(" s")

        self.trim_end_spin = QDoubleSpinBox()
        self.trim_end_spin.setRange(0.0, 24 * 60 * 60.0)
        self.trim_end_spin.setDecimals(3)
        self.trim_end_spin.setSuffix(" s")

        self.scrubber_slider = QSlider(Qt.Orientation.Horizontal)
        self.scrubber_slider.setRange(0, 1000)

        self.crop_x_spin = QSpinBox()
        self.crop_y_spin = QSpinBox()
        self.crop_width_spin = QSpinBox()
        self.crop_height_spin = QSpinBox()
        for spin in (self.crop_x_spin, self.crop_y_spin):
            spin.setRange(0, 0)
            spin.setEnabled(False)
        for spin in (self.crop_width_spin, self.crop_height_spin):
            spin.setRange(1, 1)
            spin.setEnabled(False)
        self.crop_dimensions_label = QLabel("Output: - x -")

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)

        self._build_layout()
        self._connect_signals()
        self._apply_style()
        self.setWindowTitle("Pixelator Desktop")
        self.setMinimumSize(1280, 720)
        self.statusBar().showMessage("Ready")

    def _build_layout(self) -> None:
        timeline_row = QHBoxLayout()
        timeline_row.addWidget(QLabel("Timeline"))
        timeline_row.addWidget(self.scrubber_slider, 1)
        timeline_row.addWidget(QLabel("Start"))
        timeline_row.addWidget(self.trim_start_spin)
        timeline_row.addWidget(QLabel("End"))
        timeline_row.addWidget(self.trim_end_spin)

        crop_grid = QGridLayout()
        crop_grid.addWidget(QLabel("Crop"), 0, 0)
        crop_grid.addWidget(QLabel("X"), 0, 1)
        crop_grid.addWidget(self.crop_x_spin, 0, 2)
        crop_grid.addWidget(QLabel("Y"), 0, 3)
        crop_grid.addWidget(self.crop_y_spin, 0, 4)
        crop_grid.addWidget(QLabel("Width"), 1, 1)
        crop_grid.addWidget(self.crop_width_spin, 1, 2)
        crop_grid.addWidget(QLabel("Height"), 1, 3)
        crop_grid.addWidget(self.crop_height_spin, 1, 4)
        crop_grid.addWidget(self.crop_dimensions_label, 1, 5)
        crop_grid.setColumnStretch(5, 1)

        preview_layout = QVBoxLayout()
        preview_layout.addWidget(QLabel("Preview"))
        preview_layout.addLayout(timeline_row)
        preview_layout.addWidget(self.preview_widget, 1)
        preview_layout.addLayout(crop_grid)

        preview_widget = QWidget()
        preview_widget.setLayout(preview_layout)

        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.addWidget(self.queue_panel)
        top_splitter.addWidget(preview_widget)
        top_splitter.addWidget(self.settings_panel)
        top_splitter.setSizes([260, 680, 320])

        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(self.log_view)
        main_splitter.setSizes([560, 160])

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.addWidget(main_splitter)
        self.setCentralWidget(root)

    def append_log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def add_video_paths(self, paths: list[str | Path]) -> None:
        for raw_path in paths:
            path = Path(raw_path)
            try:
                metadata = probe_video(path)
                job = VideoJob(
                    source_path=path,
                    duration=metadata.duration,
                    width=metadata.width,
                    height=metadata.height,
                    fps=metadata.fps,
                )
                self.queue.add(job)
                self.append_log(f"Added {path.name}")
            except PixelatorError as exc:
                self.append_log(f"Could not add {path}: {exc}")
        self._refresh_queue()
        if self.queue_panel.selected_job_id() is None and self.queue.jobs:
            self.queue_panel.list_widget.setCurrentRow(0)

    def _connect_signals(self) -> None:
        self.queue_panel.add_button.clicked.connect(self._choose_files)
        self.queue_panel.remove_button.clicked.connect(self._remove_selected_job)
        self.queue_panel.start_button.clicked.connect(self._start_queue)
        self.queue_panel.cancel_button.clicked.connect(self._cancel_selected_job)
        self.queue_panel.list_widget.currentItemChanged.connect(lambda current, previous: self._load_selected_job())
        self.preview_widget.cropChanged.connect(self._on_crop_changed)
        self.trim_start_spin.valueChanged.connect(lambda value: self._on_trim_changed())
        self.trim_end_spin.valueChanged.connect(lambda value: self._on_trim_changed())
        self.scrubber_slider.valueChanged.connect(lambda value: self._on_scrubber_changed())
        for spin in (
            self.crop_x_spin,
            self.crop_y_spin,
            self.crop_width_spin,
            self.crop_height_spin,
        ):
            spin.valueChanged.connect(lambda value: self._on_crop_spin_changed())

    def _choose_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add videos",
            "",
            "Media files (*.mp4 *.mov *.mkv *.avi *.gif);;Video files (*.mp4 *.mov *.mkv *.avi);;GIF files (*.gif);;All files (*.*)",
        )
        if paths:
            self.add_video_paths(paths)

    def _remove_selected_job(self) -> None:
        selected = self.queue_panel.selected_job_id()
        if selected is None:
            return
        self.queue.jobs = [job for job in self.queue.jobs if job.id != selected]
        self._refresh_queue()

    def _cancel_selected_job(self) -> None:
        selected = self.queue_panel.selected_job_id()
        if selected is None:
            return
        job = self._job_by_id(selected)
        if job is None:
            return
        if job.status == JobStatus.RUNNING:
            self.append_log("Running jobs will stop after the current render in this version.")
            return
        self.queue.mark_cancelled(selected)
        self._refresh_queue()

    def _load_selected_job(self) -> None:
        job_id = self.queue_panel.selected_job_id()
        job = self._job_by_id(job_id) if job_id else None
        if job is None:
            return
        self._loading_job = True
        try:
            duration = job.duration or 0.0
            self.trim_start_spin.setRange(0.0, max(duration, 0.001))
            self.trim_end_spin.setRange(0.0, max(duration, 0.001))
            self.trim_start_spin.setValue(job.trim.start if job.trim else 0.0)
            self.trim_end_spin.setValue(job.trim.end if job.trim and job.trim.end is not None else duration)
            preview_seconds = job.trim.start if job.trim else 0.0
            self.scrubber_slider.setValue(self._slider_value_for_seconds(job, preview_seconds))
            self._load_preview_frame(job, preview_seconds, preserve_current_crop=False)
            self.statusBar().showMessage(str(job.source_path))
        except PixelatorError as exc:
            self.append_log(f"Could not load preview: {exc}")
        finally:
            self._loading_job = False

    def _on_crop_changed(self, crop) -> None:
        if self._loading_job:
            return
        self._set_crop_controls_from_crop(crop)
        job_id = self.queue_panel.selected_job_id()
        if job_id:
            self.queue.update(job_id, crop=crop)

    def _on_trim_changed(self) -> None:
        if self._loading_job:
            return
        job_id = self.queue_panel.selected_job_id()
        if job_id is None:
            return
        start = self.trim_start_spin.value()
        end = self.trim_end_spin.value()
        if end <= start:
            end = start + 0.001
            self.trim_end_spin.setValue(end)
        self.queue.update(job_id, trim=TrimConfig(start=start, end=end))
        self._refresh_queue()

    def _on_scrubber_changed(self) -> None:
        if self._loading_job:
            return
        job = self._job_by_id(self.queue_panel.selected_job_id())
        if job is None:
            return
        seconds = self._scrubber_seconds(job)
        try:
            self._load_preview_frame(job, seconds, preserve_current_crop=True)
        except PixelatorError as exc:
            self.append_log(f"Could not load preview: {exc}")

    def _on_crop_spin_changed(self) -> None:
        if self._loading_job or self._syncing_crop_controls:
            return
        source_size = self.preview_widget.source_size()
        if source_size is None:
            return
        crop = clamp_crop(
            CropConfig(
                x=self.crop_x_spin.value(),
                y=self.crop_y_spin.value(),
                width=self.crop_width_spin.value(),
                height=self.crop_height_spin.value(),
            ),
            source_size,
        )
        self.preview_widget.set_crop(crop)

    def _scrubber_seconds(self, job: VideoJob) -> float:
        duration = job.duration or 0.0
        if duration <= 0:
            return 0.0
        return duration * (self.scrubber_slider.value() / 1000.0)

    def _slider_value_for_seconds(self, job: VideoJob, seconds: float) -> int:
        duration = job.duration or 0.0
        if duration <= 0:
            return 0
        return max(0, min(1000, round((seconds / duration) * 1000)))

    def _load_preview_frame(self, job: VideoJob, seconds: float, preserve_current_crop: bool) -> None:
        previous_crop = job.crop
        if previous_crop is None and preserve_current_crop:
            previous_crop = self.preview_widget.crop()
        was_loading = self._loading_job
        self._loading_job = True
        try:
            frame = extract_frame(job.source_path, seconds)
            self.preview_widget.set_image(frame)
            if previous_crop is not None:
                self.preview_widget.set_crop(previous_crop)
            crop = self.preview_widget.crop()
            if crop is not None:
                self._set_crop_controls_from_crop(crop)
        finally:
            self._loading_job = was_loading

    def _set_crop_controls_from_crop(self, crop: CropConfig) -> None:
        source_size = self.preview_widget.source_size()
        if source_size is None:
            self._set_crop_controls_enabled(False)
            return
        self._syncing_crop_controls = True
        try:
            source_width, source_height = source_size
            self._set_crop_controls_enabled(True)
            self.crop_x_spin.setRange(0, max(0, source_width - 1))
            self.crop_y_spin.setRange(0, max(0, source_height - 1))
            self.crop_x_spin.setValue(crop.x)
            self.crop_y_spin.setValue(crop.y)
            self.crop_width_spin.setRange(1, max(1, source_width - crop.x))
            self.crop_height_spin.setRange(1, max(1, source_height - crop.y))
            self.crop_width_spin.setValue(crop.width)
            self.crop_height_spin.setValue(crop.height)
            self._update_crop_dimensions(crop)
        finally:
            self._syncing_crop_controls = False

    def _set_crop_controls_enabled(self, enabled: bool) -> None:
        for spin in (
            self.crop_x_spin,
            self.crop_y_spin,
            self.crop_width_spin,
            self.crop_height_spin,
        ):
            spin.setEnabled(enabled)

    def _update_crop_dimensions(self, crop: CropConfig) -> None:
        self.crop_dimensions_label.setText(f"Output: {crop.width} x {crop.height}")

    def _start_queue(self) -> None:
        if self._active_thread is not None:
            self.append_log("Render already running.")
            return
        if not any(job.status == JobStatus.QUEUED for job in self.queue.jobs):
            selected = self.queue_panel.selected_job_id()
            if selected and self.queue.requeue_finished(selected) is not None:
                self.append_log("Requeued selected job.")
                self._refresh_queue()
        self._run_next_job()

    def _run_next_job(self) -> None:
        next_job = next((job for job in self.queue.jobs if job.status == JobStatus.QUEUED), None)
        if next_job is None:
            self.statusBar().showMessage("Queue complete")
            return

        settings = self._settings_for_job(next_job)
        output_path = self._output_path_for_job(next_job)
        self.queue.mark_running(next_job.id)
        self._refresh_queue()

        thread = QThread(self)
        worker = RenderWorker(next_job, output_path, settings)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progressChanged.connect(self._on_worker_progress)
        worker.logMessage.connect(self.append_log)
        worker.jobCompleted.connect(self._on_worker_completed)
        worker.jobFailed.connect(self._on_worker_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        self._active_thread = thread
        self._active_worker = worker
        thread.start()

    def _settings_for_job(self, job: VideoJob) -> RenderSettings:
        settings = self.settings_panel.settings()
        return replace(settings, crop=job.crop, trim=job.trim)

    def _output_path_for_job(self, job: VideoJob) -> Path:
        output_dir = self.settings_panel.output_folder()
        output_dir.mkdir(parents=True, exist_ok=True)
        extension = self.settings_panel.settings().output_format
        return output_dir / f"{job.source_path.stem}-pixelated.{extension}"

    def _on_worker_progress(self, job_id: str, progress: int) -> None:
        self.queue.mark_progress(job_id, progress)
        self._refresh_queue()

    def _on_worker_completed(self, job_id: str, output_path: Path) -> None:
        self.queue.mark_completed(job_id, output_path)
        self.append_log(f"Wrote {output_path}")
        self._refresh_queue()

    def _on_worker_failed(self, job_id: str, error: str) -> None:
        self.queue.mark_failed(job_id, error)
        self.append_log(f"Render failed: {error}")
        self._refresh_queue()

    def _on_thread_finished(self) -> None:
        self._active_thread = None
        self._active_worker = None
        self._run_next_job()

    def _refresh_queue(self) -> None:
        selected = self.queue_panel.selected_job_id()
        self.queue_panel.set_jobs(self.queue.jobs)
        if selected:
            for index in range(self.queue_panel.list_widget.count()):
                item = self.queue_panel.list_widget.item(index)
                if item.data(Qt.ItemDataRole.UserRole) == selected:
                    self.queue_panel.list_widget.setCurrentItem(item)
                    break

    def _job_by_id(self, job_id: str | None) -> VideoJob | None:
        if job_id is None:
            return None
        return next((job for job in self.queue.jobs if job.id == job_id), None)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #202326;
                color: #e5e7eb;
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 12px;
            }
            QLabel#panelTitle {
                font-weight: 600;
                padding: 2px 0 6px 0;
            }
            QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
                min-height: 24px;
            }
            QPlainTextEdit, QListWidget, QLabel[frameShape="6"] {
                background: #151719;
                border: 1px solid #3a3f45;
            }
            """
        )
