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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PIL import Image

from pixelator.ai.asset_store import AssetStore
from pixelator.config import CropConfig, TrimConfig
from pixelator.errors import PixelatorError
from pixelator.gui.ai_panel import AiAssetsPanel
from pixelator.gui.ai_worker import AiGenerationWorker
from pixelator.gui.models import JobQueue, JobStatus, PaletteSnapshot, RenderSettings, VideoJob
from pixelator.gui.palette_panel import PalettePanel
from pixelator.gui.preview import PreviewWidget, clamp_crop
from pixelator.gui.queue_panel import QueuePanel
from pixelator.gui.settings_panel import SettingsPanel
from pixelator.gui.worker import RenderWorker
from pixelator.image_io import load_static_image
from pixelator.media import iter_image_files, is_image_path, is_video_path
from pixelator.video import extract_frame, probe_video


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.queue = JobQueue()
        self._loading_job = False
        self._syncing_crop_controls = False
        self._syncing_settings = False
        self._syncing_palette_context = False
        self._current_preview_frame: Image.Image | None = None
        self._active_thread: QThread | None = None
        self._active_worker: RenderWorker | None = None
        self._ai_thread: QThread | None = None
        self._ai_worker: AiGenerationWorker | None = None
        self.queue_panel = QueuePanel()
        self.settings_panel = SettingsPanel()
        self.palette_panel = PalettePanel()
        self.ai_panel = AiAssetsPanel()
        self.preview_widget = PreviewWidget()
        self._global_render_settings = self.settings_panel.settings()
        self._shared_palette_snapshot = self.palette_panel.snapshot()

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
        self._load_ai_assets()
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

        self.right_tabs = QTabWidget()
        self.right_tabs.addTab(self.settings_panel, "Render")
        self.right_tabs.addTab(self.palette_panel, "Palette")
        self.right_tabs.addTab(self.ai_panel, "AI Assets")
        top_splitter.addWidget(self.right_tabs)
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
        self.add_media_paths(paths)

    def add_media_paths(self, paths: list[str | Path]) -> None:
        for raw_path in paths:
            path = Path(raw_path)
            if path.is_dir():
                image_paths = iter_image_files(path)
                if not image_paths:
                    self.append_log(f"No supported image files found in {path}")
                    continue
                for image_path in image_paths:
                    self._add_media_path(image_path)
                continue
            self._add_media_path(path)
        self._refresh_queue()
        if self.queue_panel.selected_job_id() is None and self.queue.jobs:
            self.queue_panel.list_widget.setCurrentRow(0)

    def _add_media_path(self, path: Path) -> None:
        try:
            if is_image_path(path):
                frame = load_static_image(path)
                job = VideoJob(
                    source_path=path,
                    width=frame.width,
                    height=frame.height,
                    media_type="image",
                )
                self.queue.add(job)
                self.append_log(f"Added image {path.name}")
                return
            if is_video_path(path):
                metadata = probe_video(path)
                job = VideoJob(
                    source_path=path,
                    duration=metadata.duration,
                    width=metadata.width,
                    height=metadata.height,
                    fps=metadata.fps,
                    media_type="video",
                )
                self.queue.add(job)
                self.append_log(f"Added {path.name}")
                return
            self.append_log(f"Unsupported media file: {path}")
        except PixelatorError as exc:
            self.append_log(f"Could not add {path}: {exc}")

    def _connect_signals(self) -> None:
        self.queue_panel.add_button.clicked.connect(self._choose_files)
        self.queue_panel.folder_button.clicked.connect(self._choose_folder)
        self.queue_panel.remove_button.clicked.connect(self._remove_selected_job)
        self.queue_panel.start_button.clicked.connect(self._start_queue)
        self.queue_panel.cancel_button.clicked.connect(self._cancel_selected_job)
        self.queue_panel.list_widget.currentItemChanged.connect(self._on_selected_job_changed)
        self.settings_panel.settingsChanged.connect(self._on_settings_changed)
        self.settings_panel.customize_button.clicked.connect(self._customize_selected_job_settings)
        self.settings_panel.use_global_button.clicked.connect(self._use_global_settings_for_selected_job)
        self.palette_panel.paletteChanged.connect(self._on_palette_changed)
        self.palette_panel.paletteModeChanged.connect(self._on_palette_mode_changed)
        self.palette_panel.extractCurrentFrameRequested.connect(self._extract_palette_from_current_frame)
        self.ai_panel.generateRequested.connect(self._start_ai_generation)
        self.ai_panel.addAssetToQueueRequested.connect(self._add_ai_asset_to_queue)
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
            "Add media",
            "",
            (
                "Media files (*.mp4 *.mov *.mkv *.avi *.gif *.png *.jpg *.jpeg *.webp *.bmp *.tga *.tif *.tiff);;"
                "Video and GIF files (*.mp4 *.mov *.mkv *.avi *.gif);;"
                "Image files (*.png *.jpg *.jpeg *.webp *.bmp *.tga *.tif *.tiff);;"
                "All files (*.*)"
            ),
        )
        if paths:
            self.add_media_paths(paths)

    def _choose_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Add image folder", "")
        if selected:
            self.add_media_paths([selected])

    def _remove_selected_job(self) -> None:
        selected = self.queue_panel.selected_job_id()
        if selected is None:
            return
        self._save_palette_context(selected)
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

    def _on_selected_job_changed(self, current, previous) -> None:
        previous_id = previous.data(Qt.ItemDataRole.UserRole) if previous is not None else None
        self._save_palette_context(str(previous_id) if previous_id else None)
        self._load_selected_job()

    def _load_selected_job(self) -> None:
        job_id = self.queue_panel.selected_job_id()
        job = self._job_by_id(job_id) if job_id else None
        if job is None:
            return
        self._loading_job = True
        try:
            self._load_settings_context(job)
            self._load_palette_context(job)
            if job.is_image:
                self.trim_start_spin.setEnabled(False)
                self.trim_end_spin.setEnabled(False)
                self.scrubber_slider.setEnabled(False)
                self.trim_start_spin.setRange(0.0, 0.001)
                self.trim_end_spin.setRange(0.0, 0.001)
                self.trim_start_spin.setValue(0.0)
                self.trim_end_spin.setValue(0.0)
                self.scrubber_slider.setValue(0)
                preview_seconds = 0.0
            else:
                self.trim_start_spin.setEnabled(True)
                self.trim_end_spin.setEnabled(True)
                self.scrubber_slider.setEnabled(True)
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
        job = self._job_by_id(job_id)
        if job is None or job.is_image:
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
        if job is None or job.is_image:
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
        job = self._job_by_id(self.queue_panel.selected_job_id())
        crop = clamp_crop(
            CropConfig(
                x=self.crop_x_spin.value(),
                y=self.crop_y_spin.value(),
                width=self.crop_width_spin.value(),
                height=self.crop_height_spin.value(),
            ),
            source_size,
            encoder_safe=not (job and job.is_image),
        )
        self.preview_widget.set_crop(crop)

    def _scrubber_seconds(self, job: VideoJob) -> float:
        if job.is_image:
            return 0.0
        duration = job.duration or 0.0
        if duration <= 0:
            return 0.0
        return duration * (self.scrubber_slider.value() / 1000.0)

    def _slider_value_for_seconds(self, job: VideoJob, seconds: float) -> int:
        if job.is_image:
            return 0
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
            self.preview_widget.set_encoder_safe_crop(not job.is_image)
            frame = load_static_image(job.source_path) if job.is_image else extract_frame(job.source_path, seconds)
            self._current_preview_frame = frame.copy()
            self.preview_widget.set_image(frame)
            if previous_crop is not None:
                self.preview_widget.set_crop(previous_crop)
            crop = self.preview_widget.crop()
            if crop is not None:
                self._set_crop_controls_from_crop(crop)
        finally:
            self._loading_job = was_loading

    def _extract_palette_from_current_frame(self, count: int, method: str, scope: str) -> None:
        if self._current_preview_frame is None:
            self.palette_panel.set_status_message("No current frame to extract")
            return
        frame = self._current_preview_frame
        source_label = "current frame"
        if scope == "crop":
            crop = self.preview_widget.crop()
            if crop is not None:
                frame = frame.crop((crop.x, crop.y, crop.x + crop.width, crop.y + crop.height))
                source_label = "current crop"
        self.palette_panel.extract_from_image(frame, source_label, count, method)
        self.right_tabs.setCurrentWidget(self.palette_panel)

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
        settings = job.settings_override or self._global_render_settings
        palette_snapshot = self._palette_snapshot_for_job(job)
        custom_palette = palette_snapshot.render_colors if len(palette_snapshot.render_colors) >= 2 else None
        source_palette = (
            palette_snapshot.source_colors
            if palette_snapshot.auto_match
            and len(palette_snapshot.source_colors) >= 2
            and len(palette_snapshot.render_colors) >= 2
            else None
        )
        palette_strategy = "auto_match" if custom_palette and source_palette else "custom"
        return replace(
            settings,
            crop=job.crop,
            trim=None if job.is_image else job.trim,
            keep_audio=False if job.is_image else settings.keep_audio,
            custom_palette=custom_palette,
            source_palette=source_palette,
            palette_strategy=palette_strategy,
            palette_match_sort=palette_snapshot.match_sort,
        )

    def _output_path_for_job(self, job: VideoJob) -> Path:
        output_dir = self.settings_panel.output_folder()
        output_dir.mkdir(parents=True, exist_ok=True)
        extension = "png" if job.is_image else self._settings_for_job(job).output_format
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

    def _start_ai_generation(self, request, config) -> None:
        if self._ai_thread is not None:
            self.append_log("AI generation already running.")
            return
        self.ai_panel.set_generating(True)
        thread = QThread(self)
        worker = AiGenerationWorker(request, config, self._ai_output_dir())
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.logMessage.connect(self.append_log)
        worker.generationCompleted.connect(self._on_ai_generation_completed)
        worker.generationFailed.connect(self._on_ai_generation_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_ai_thread_finished)
        self._ai_thread = thread
        self._ai_worker = worker
        thread.start()

    def _on_ai_generation_completed(self, records) -> None:
        self.ai_panel.add_asset_records(records)
        self.ai_panel.set_status_message(f"Saved {len(records)} AI asset(s)")
        self.append_log(f"Generated {len(records)} AI asset(s) in {self._ai_output_dir()}")

    def _on_ai_generation_failed(self, error: str) -> None:
        self.ai_panel.set_status_message(error)
        self.append_log(f"AI generation failed: {error}")

    def _on_ai_thread_finished(self) -> None:
        self._ai_thread = None
        self._ai_worker = None
        self.ai_panel.set_generating(False)

    def _add_ai_asset_to_queue(self, path: str) -> None:
        asset_path = Path(path)
        if not asset_path.exists():
            self.append_log(f"AI asset not found: {asset_path}")
            return
        self.add_media_paths([asset_path])
        self.append_log(f"Added AI asset to queue: {asset_path.name}")

    def _load_ai_assets(self) -> None:
        self.ai_panel.load_asset_records(AssetStore(self._ai_output_dir()).load_records())

    def _ai_output_dir(self) -> Path:
        return self.settings_panel.output_folder() / "ai-assets"

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

    def _load_settings_context(self, job: VideoJob) -> None:
        settings = job.settings_override or self._global_render_settings
        self._syncing_settings = True
        try:
            self.settings_panel.set_settings(settings)
            self.settings_panel.set_settings_scope(customized=job.settings_override is not None)
        finally:
            self._syncing_settings = False

    def _on_settings_changed(self) -> None:
        if self._syncing_settings or self._loading_job:
            return
        settings = self.settings_panel.settings()
        job = self._job_by_id(self.queue_panel.selected_job_id())
        if job is not None and job.settings_override is not None:
            self.queue.update(job.id, settings_override=settings)
            return
        self._global_render_settings = settings

    def _customize_selected_job_settings(self) -> None:
        job = self._job_by_id(self.queue_panel.selected_job_id())
        if job is None:
            return
        settings = self.settings_panel.settings()
        self.queue.update(job.id, settings_override=settings)
        self.settings_panel.set_settings_scope(customized=True)
        self._refresh_queue()

    def _use_global_settings_for_selected_job(self) -> None:
        job = self._job_by_id(self.queue_panel.selected_job_id())
        if job is None:
            return
        self.queue.update(job.id, settings_override=None)
        self._load_settings_context(self.queue.jobs[self._job_index(job.id)])
        self._refresh_queue()

    def _load_palette_context(self, job: VideoJob) -> None:
        self._syncing_palette_context = True
        try:
            self.palette_panel.set_palette_mode(job.palette_mode)
            self.palette_panel.load_snapshot(self._palette_snapshot_for_job(job))
        finally:
            self._syncing_palette_context = False

    def _palette_snapshot_for_job(self, job: VideoJob) -> PaletteSnapshot:
        if job.palette_mode == "item" and job.palette_snapshot is not None:
            return job.palette_snapshot
        return self._shared_palette_snapshot

    def _save_palette_context(self, job_id: str | None = None) -> None:
        if self._syncing_palette_context:
            return
        job = self._job_by_id(job_id) if job_id is not None else self._job_by_id(self.queue_panel.selected_job_id())
        snapshot = self.palette_panel.snapshot()
        if job is not None and job.palette_mode == "item":
            self.queue.update(job.id, palette_snapshot=snapshot)
            return
        self._shared_palette_snapshot = snapshot

    def _on_palette_changed(self) -> None:
        if self._syncing_palette_context:
            return
        self._save_palette_context()

    def _on_palette_mode_changed(self, mode: str) -> None:
        if self._syncing_palette_context:
            return
        job = self._job_by_id(self.queue_panel.selected_job_id())
        if job is None:
            self.palette_panel.set_palette_mode("shared")
            return
        if mode == "item":
            self.queue.update(job.id, palette_mode="item", palette_snapshot=self.palette_panel.snapshot())
            self._refresh_queue()
            return
        if job.palette_mode == "item":
            self.queue.update(job.id, palette_snapshot=self.palette_panel.snapshot())
        updated = self.queue.update(job.id, palette_mode="shared")
        self._load_palette_context(updated)
        self._refresh_queue()

    def _job_index(self, job_id: str) -> int:
        for index, job in enumerate(self.queue.jobs):
            if job.id == job_id:
                return index
        raise KeyError(job_id)

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
