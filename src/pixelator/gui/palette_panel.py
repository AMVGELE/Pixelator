from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QSignalBlocker, QSize, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pixelator.errors import ConfigError
from pixelator.gui.models import PaletteSnapshot
from pixelator.palette_io import load_palette_file, normalize_hex_color, normalize_hex_colors, save_palette_file
from pixelator.palette_studio import (
    delete_palette_preset,
    extract_palette_from_image,
    auto_match_palette_pairs,
    hsv_position,
    list_palette_presets,
    load_lospec_palette_file,
    nearest_palette_color,
    perceptual_color_distance,
    rgb_distance,
    save_palette_preset,
    sort_palette_colors,
)


class PalettePanel(QWidget):
    paletteChanged = Signal()
    paletteModeChanged = Signal(str)
    extractCurrentFrameRequested = Signal(int, str, str)

    def __init__(self, preset_dir: str | Path | None = None) -> None:
        super().__init__()
        self._colors: list[str] = []
        self._source_colors: list[str] = []
        self._preset_dir = Path(preset_dir) if preset_dir is not None else None
        self._selected_source_index: int | None = None
        self._selected_render_index: int | None = None
        self._render_selection_manual = False
        self._syncing_selection = False
        self._syncing_palette_mode = False

        self.palette_mode_combo = QComboBox()
        self.palette_mode_combo.addItem("Shared Palette", "shared")
        self.palette_mode_combo.addItem("Per Item Palette", "item")

        self.extract_count_spin = QSpinBox()
        self.extract_count_spin.setRange(2, 256)
        self.extract_count_spin.setValue(32)
        self.extract_method_combo = QComboBox()
        self.extract_method_combo.addItem("Dominant Colors", "dominant")
        self.extract_method_combo.addItem("Balanced Hue", "balanced_hue")
        self.extract_method_combo.addItem("Shadows / Midtones / Highlights", "tonal")
        self.extract_scope_combo = QComboBox()
        self.extract_scope_combo.addItem("Full Frame", "full")
        self.extract_scope_combo.addItem("Current Crop", "crop")
        self.extract_current_frame_button = QPushButton("Current Frame")
        self.extract_image_button = QPushButton("Image...")

        self.preset_name_edit = QLineEdit()
        self.preset_name_edit.setPlaceholderText("Preset name")
        self.preset_combo = QComboBox()
        self.save_preset_button = QPushButton("Save")
        self.load_preset_button = QPushButton("Load")
        self.delete_preset_button = QPushButton("Delete")

        self.add_button = QPushButton("Add")
        self.delete_button = QPushButton("Delete")
        self.replace_button = QPushButton("Replace")
        self.up_button = QPushButton("Up")
        self.down_button = QPushButton("Down")
        self.load_button = QPushButton("Load YAML")
        self.save_button = QPushButton("Save YAML")
        self.import_lospec_button = QPushButton("Import Lospec")

        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Hue + Brightness", "hue_brightness")
        self.sort_combo.addItem("Original", "original")
        self.sort_combo.addItem("Brightness", "brightness")
        self.sort_combo.addItem("Hue", "hue")
        self.sort_combo.addItem("Saturation", "saturation")
        self.auto_match_check = QCheckBox("AutoMatch")
        self.auto_match_check.setChecked(True)
        self.apply_sort_button = QPushButton("Sort")

        self.match_board = ColorMatchBoard()
        self.mapping_view = ColorMappingView()
        self.color_space_widget = ColorSpaceWidget()

        self.hex_edit = QLineEdit("#000000")
        self.hex_edit.setMaxLength(7)
        self.status_label = QLabel("Automatic palette")

        self._build_layout()
        self._connect_signals()
        self._refresh_presets()
        self._refresh()

    def colors(self) -> list[str]:
        return list(self._colors)

    def source_colors(self) -> list[str]:
        return list(self._source_colors)

    def auto_match_enabled(self) -> bool:
        return self.auto_match_check.isChecked() and len(self._source_colors) >= 2 and len(self._colors) >= 2

    def match_sort_mode(self) -> str:
        return str(self.sort_combo.currentData() or "hue_brightness")

    def palette_mode(self) -> str:
        return str(self.palette_mode_combo.currentData() or "shared")

    def set_palette_mode(self, mode: str) -> None:
        blocker = QSignalBlocker(self.palette_mode_combo)
        try:
            self._set_combo_data(self.palette_mode_combo, mode)
        finally:
            del blocker

    def extract_method(self) -> str:
        return str(self.extract_method_combo.currentData() or "dominant")

    def extract_scope(self) -> str:
        return str(self.extract_scope_combo.currentData() or "full")

    def has_custom_palette(self) -> bool:
        return len(self._colors) >= 2

    def snapshot(self) -> PaletteSnapshot:
        return PaletteSnapshot(
            source_colors=self.source_colors(),
            render_colors=self.colors(),
            auto_match=self.auto_match_check.isChecked(),
            match_sort=self.match_sort_mode(),
        )

    def load_snapshot(self, snapshot: PaletteSnapshot, emit_changed: bool = False) -> None:
        normalized_source = normalize_hex_colors(snapshot.source_colors)
        normalized_render = normalize_hex_colors(snapshot.render_colors)
        blockers = [QSignalBlocker(self.auto_match_check), QSignalBlocker(self.sort_combo)]
        try:
            self._source_colors = list(normalized_source)
            self._colors = list(normalized_render)
            self.auto_match_check.setChecked(snapshot.auto_match)
            self._set_combo_data(self.sort_combo, snapshot.match_sort)
            self._selected_source_index = 0 if self._source_colors else None
            self._selected_render_index = 0 if self._colors else None
            self._render_selection_manual = False
        finally:
            del blockers
        self._sync_matched_render_selection()
        self._refresh()
        if emit_changed:
            self.paletteChanged.emit()

    def set_colors(self, colors: list[str]) -> None:
        self._colors = normalize_hex_colors(colors)
        self._selected_render_index = 0 if self._colors else None
        self._render_selection_manual = False
        self._sync_matched_render_selection()
        self._refresh()
        self.paletteChanged.emit()

    def set_source_and_render_colors(self, colors: list[str]) -> None:
        normalized = normalize_hex_colors(colors)
        self._source_colors = list(normalized)
        self._colors = list(normalized)
        self._selected_source_index = 0 if self._source_colors else None
        self._selected_render_index = 0 if self._colors else None
        self._render_selection_manual = False
        self._sync_matched_render_selection()
        self._refresh()
        self.paletteChanged.emit()

    def set_source_colors(self, colors: list[str]) -> None:
        normalized = normalize_hex_colors(colors)
        self._source_colors = list(normalized)
        self._selected_source_index = 0 if self._source_colors else None
        if not self._colors:
            self._colors = list(normalized)
            self._selected_render_index = 0 if self._colors else None
        self._render_selection_manual = False
        self._sync_matched_render_selection()
        self._refresh()
        self.paletteChanged.emit()

    def select_index(self, index: int) -> None:
        if 0 <= index < len(self._colors):
            self._selected_render_index = index
            self._render_selection_manual = True
            self._refresh()

    def select_source_index(self, index: int) -> None:
        if 0 <= index < len(self._source_colors):
            self._selected_source_index = index
            if not self._render_selection_manual:
                self._sync_matched_render_selection()
            self._refresh()

    def add_color(self, color: str) -> None:
        self._colors.append(normalize_hex_color(color))
        self._selected_render_index = len(self._colors) - 1
        self._render_selection_manual = True
        self._refresh()
        self.paletteChanged.emit()

    def delete_selected(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        del self._colors[index]
        if self._colors:
            self._selected_render_index = min(index, len(self._colors) - 1)
        else:
            self._selected_render_index = None
            self._render_selection_manual = False
        self._refresh()
        self.paletteChanged.emit()

    def move_selected_up(self) -> None:
        index = self._selected_index()
        if index is None or index <= 0:
            return
        self._colors[index - 1], self._colors[index] = self._colors[index], self._colors[index - 1]
        self._selected_render_index = index - 1
        self._render_selection_manual = True
        self._refresh()
        self.paletteChanged.emit()

    def move_selected_down(self) -> None:
        index = self._selected_index()
        if index is None or index >= len(self._colors) - 1:
            return
        self._colors[index + 1], self._colors[index] = self._colors[index], self._colors[index + 1]
        self._selected_render_index = index + 1
        self._render_selection_manual = True
        self._refresh()
        self.paletteChanged.emit()

    def apply_hex_to_selected(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        self.replace_selected_color(self.hex_edit.text().strip())

    def replace_selected_color(self, color: str) -> None:
        index = self._selected_index()
        if index is None:
            return
        try:
            self._colors[index] = normalize_hex_color(color)
        except ConfigError as exc:
            self._set_status(str(exc))
            return
        self._render_selection_manual = True
        self._refresh()
        self.paletteChanged.emit()

    def load_palette(self, path: str | Path | None = None) -> None:
        palette_path = Path(path) if path is not None else self._choose_load_path()
        if not palette_path:
            return
        try:
            loaded = load_palette_file(palette_path)
        except ConfigError as exc:
            self._set_status(str(exc))
            return
        self.set_colors(loaded.colors)
        self._set_status(f"Loaded {palette_path.name}")

    def save_palette(self, path: str | Path | None = None) -> None:
        palette_path = Path(path) if path is not None else self._choose_save_path()
        if not palette_path:
            return
        try:
            save_palette_file(palette_path, self._colors, name=palette_path.stem)
        except ConfigError as exc:
            self._set_status(str(exc))
            return
        self._set_status(f"Saved {palette_path.name}")

    def extract_from_image(
        self,
        image: Image.Image,
        source_label: str = "image",
        count: int | None = None,
        method: str | None = None,
    ) -> None:
        try:
            colors = extract_palette_from_image(
                image,
                count if count is not None else self.extract_count_spin.value(),
                method if method is not None else self.extract_method(),
            )
        except ConfigError as exc:
            self._set_status(str(exc))
            return
        self.set_source_colors(colors)
        self._set_status(f"Extracted {len(colors)} colors from {source_label}")

    def extract_from_image_file(self, path: str | Path | None = None) -> None:
        image_path = Path(path) if path is not None else self._choose_image_path()
        if not image_path:
            return
        try:
            with Image.open(image_path) as image:
                image.seek(0)
                self.extract_from_image(image.copy(), image_path.name)
        except (OSError, ConfigError) as exc:
            self._set_status(f"Could not extract palette: {exc}")

    def import_lospec_palette(self, path: str | Path | None = None) -> None:
        palette_path = Path(path) if path is not None else self._choose_lospec_path()
        if not palette_path:
            return
        try:
            colors = load_lospec_palette_file(palette_path)
        except ConfigError as exc:
            self._set_status(str(exc))
            return
        self.set_source_and_render_colors(colors)
        self._set_status(f"Imported {palette_path.name}")

    def save_preset(self, name: str | None = None) -> None:
        preset_name = (name if name is not None else self.preset_name_edit.text()).strip()
        try:
            path = save_palette_preset(preset_name, self._colors, self._preset_dir)
        except ConfigError as exc:
            self._set_status(str(exc))
            return
        self._refresh_presets(select_path=path)
        self._set_status(f"Saved preset {preset_name}")

    def load_selected_preset(self) -> None:
        path = self._selected_preset_path()
        if path is None:
            return
        try:
            loaded = load_palette_file(path)
        except ConfigError as exc:
            self._set_status(str(exc))
            return
        self.set_colors(loaded.colors)
        if loaded.name:
            self.preset_name_edit.setText(loaded.name)
        self._set_status(f"Loaded preset {loaded.name or path.stem}")

    def delete_selected_preset(self, confirm: bool = True) -> None:
        path = self._selected_preset_path()
        if path is None:
            return
        name = self.preset_combo.currentText()
        if confirm:
            result = QMessageBox.question(
                self,
                "Delete preset",
                f"Delete palette preset '{name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if result != QMessageBox.StandardButton.Yes:
                return
        try:
            delete_palette_preset(path)
        except ConfigError as exc:
            self._set_status(str(exc))
            return
        self._refresh_presets()
        self._set_status(f"Deleted preset {name}")

    def apply_sort(self) -> None:
        try:
            self.set_colors(sort_palette_colors(self._colors, self.sort_combo.currentData()))
        except ConfigError as exc:
            self._set_status(str(exc))
            return
        self._set_status(f"Sorted by {self.sort_combo.currentText().lower()}")

    def set_status_message(self, message: str) -> None:
        self._set_status(message)

    def _build_layout(self) -> None:
        title = QLabel("Palette")
        title.setObjectName("panelTitle")

        tool_row = QGridLayout()
        tool_row.addWidget(QLabel("Palette"), 0, 0)
        tool_row.addWidget(self.palette_mode_combo, 0, 1, 1, 3)
        tool_row.addWidget(QLabel("Extract"), 1, 0)
        tool_row.addWidget(self.extract_count_spin, 1, 1)
        tool_row.addWidget(self.extract_current_frame_button, 1, 2)
        tool_row.addWidget(self.extract_image_button, 1, 3)
        tool_row.addWidget(QLabel("Method"), 2, 0)
        tool_row.addWidget(self.extract_method_combo, 2, 1, 1, 2)
        tool_row.addWidget(self.extract_scope_combo, 2, 3)
        tool_row.addWidget(QLabel("Preset"), 3, 0)
        tool_row.addWidget(self.preset_combo, 3, 1, 1, 2)
        tool_row.addWidget(self.load_preset_button, 3, 3)
        tool_row.addWidget(self.preset_name_edit, 4, 0, 1, 2)
        tool_row.addWidget(self.save_preset_button, 4, 2)
        tool_row.addWidget(self.delete_preset_button, 4, 3)
        tool_row.addWidget(self.load_button, 5, 0)
        tool_row.addWidget(self.save_button, 5, 1)
        tool_row.addWidget(self.import_lospec_button, 5, 2)
        tool_row.addWidget(self.apply_sort_button, 5, 3)
        tool_row.addWidget(QLabel("Sort"), 6, 0)
        tool_row.addWidget(self.sort_combo, 6, 1, 1, 2)
        tool_row.addWidget(self.auto_match_check, 6, 3)

        render_actions = QGridLayout()
        for index, button in enumerate(
            (
                self.add_button,
                self.replace_button,
                self.delete_button,
                self.up_button,
                self.down_button,
            )
        ):
            render_actions.addWidget(button, index // 3, index % 3)

        hex_row = QHBoxLayout()
        hex_row.addWidget(QLabel("Precise Hex"))
        hex_row.addWidget(self.hex_edit, 1)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.addWidget(title)
        layout.addLayout(tool_row)
        layout.addWidget(_section_label("Source -> Render Board"))
        layout.addWidget(self.match_board)
        layout.addLayout(render_actions)
        layout.addLayout(hex_row)
        layout.addWidget(_section_label("A -> B Mapping"))
        layout.addWidget(self.mapping_view)
        layout.addWidget(_section_label("Color Space"))
        layout.addWidget(self.color_space_widget)
        layout.addWidget(self.status_label)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

    def _connect_signals(self) -> None:
        self.match_board.sourceClicked.connect(self._on_source_color_clicked)
        self.match_board.renderClicked.connect(self._on_render_color_clicked)
        self.match_board.renderDoubleClicked.connect(self._on_render_color_double_clicked)
        self.hex_edit.editingFinished.connect(self.apply_hex_to_selected)
        self.palette_mode_combo.currentIndexChanged.connect(self._on_palette_mode_changed)
        self.extract_current_frame_button.clicked.connect(
            lambda: self.extractCurrentFrameRequested.emit(
                self.extract_count_spin.value(),
                self.extract_method(),
                self.extract_scope(),
            )
        )
        self.extract_image_button.clicked.connect(lambda: self.extract_from_image_file())
        self.add_button.clicked.connect(self._add_with_color_dialog)
        self.delete_button.clicked.connect(self.delete_selected)
        self.replace_button.clicked.connect(self._replace_with_color_dialog)
        self.up_button.clicked.connect(self.move_selected_up)
        self.down_button.clicked.connect(self.move_selected_down)
        self.load_button.clicked.connect(lambda: self.load_palette())
        self.save_button.clicked.connect(lambda: self.save_palette())
        self.import_lospec_button.clicked.connect(lambda: self.import_lospec_palette())
        self.save_preset_button.clicked.connect(lambda: self.save_preset())
        self.load_preset_button.clicked.connect(self.load_selected_preset)
        self.delete_preset_button.clicked.connect(lambda: self.delete_selected_preset())
        self.apply_sort_button.clicked.connect(self.apply_sort)
        self.auto_match_check.toggled.connect(self._on_auto_match_toggled)
        self.sort_combo.currentIndexChanged.connect(lambda index: self._on_sort_mode_changed())

    def _refresh(self) -> None:
        if not self._render_selection_manual:
            self._sync_matched_render_selection()
        self.match_board.set_rows(
            self._match_rows(),
            self._selected_source_index,
            self._selected_render_index,
            self.auto_match_enabled(),
        )
        self.color_space_widget.set_palettes(
            self._source_colors,
            self._colors,
            self._selected_source_index,
            self._selected_render_index,
        )
        self._sync_hex_edit()
        self._update_mapping_view()
        if self.auto_match_enabled():
            self._set_status("AutoMatch palette")
        else:
            self._set_status("Custom palette" if self.has_custom_palette() else "Automatic palette")

    def _on_source_color_clicked(self, index: int) -> None:
        self._selected_source_index = index
        if not self._render_selection_manual:
            self._sync_nearest_render_selection()
        self._refresh()

    def _on_render_color_clicked(self, index: int) -> None:
        self._selected_render_index = index
        self._render_selection_manual = True
        self._refresh()

    def _on_render_color_double_clicked(self, index: int) -> None:
        self._selected_render_index = index
        self._render_selection_manual = True
        self._replace_with_color_dialog()

    def _on_auto_match_toggled(self, checked: bool) -> None:
        self._render_selection_manual = False
        self._sync_matched_render_selection()
        self._refresh()
        self.paletteChanged.emit()

    def _on_sort_mode_changed(self) -> None:
        self._refresh()
        self.paletteChanged.emit()

    def _on_palette_mode_changed(self, index: int) -> None:
        if self._syncing_palette_mode:
            return
        self.paletteModeChanged.emit(self.palette_mode())

    def _add_with_color_dialog(self) -> None:
        default = self._colors[self._selected_render_index] if self._selected_index() is not None else "#000000"
        selected = QColorDialog.getColor(QColor(default), self, "Add render palette color")
        if not selected.isValid():
            return
        self.add_color(selected.name())

    def _replace_with_color_dialog(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        selected = QColorDialog.getColor(QColor(self._colors[index]), self, "Replace render palette color")
        if not selected.isValid():
            return
        self.replace_selected_color(selected.name())

    def _choose_load_path(self) -> Path | None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Load palette",
            "",
            "Palette files (*.yaml *.yml);;All files (*.*)",
        )
        return Path(selected) if selected else None

    def _choose_save_path(self) -> Path | None:
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Save palette",
            "palette.yaml",
            "Palette files (*.yaml *.yml);;All files (*.*)",
        )
        return Path(selected) if selected else None

    def _choose_image_path(self) -> Path | None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Extract palette from image",
            "",
            "Image files (*.png *.jpg *.jpeg *.webp *.bmp *.gif);;All files (*.*)",
        )
        return Path(selected) if selected else None

    def _choose_lospec_path(self) -> Path | None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Import Lospec palette",
            "",
            "Palette text files (*.hex *.txt);;All files (*.*)",
        )
        return Path(selected) if selected else None

    def _refresh_presets(self, select_path: str | Path | None = None) -> None:
        selected = str(Path(select_path)) if select_path is not None else str(self._selected_preset_path() or "")
        self.preset_combo.clear()
        for preset in list_palette_presets(self._preset_dir):
            self.preset_combo.addItem(preset.name, str(preset.path))
            if str(preset.path) == selected:
                self.preset_combo.setCurrentIndex(self.preset_combo.count() - 1)

    def _selected_preset_path(self) -> Path | None:
        data = self.preset_combo.currentData()
        if not data:
            return None
        return Path(str(data))

    def _selected_index(self) -> int | None:
        index = self._selected_render_index
        return index if index is not None and 0 <= index < len(self._colors) else None

    def _sync_hex_edit(self) -> None:
        if self._syncing_selection:
            return
        self._syncing_selection = True
        try:
            index = self._selected_index()
            self.hex_edit.setText(self._colors[index] if index is not None else "#000000")
            self.hex_edit.setEnabled(index is not None)
        finally:
            self._syncing_selection = False

    def _sync_matched_render_selection(self) -> None:
        source = self._selected_source_color()
        if source is None:
            return
        matched = self._matched_render_index(source)
        if matched is not None:
            self._selected_render_index = matched

    def _sync_nearest_render_selection(self) -> None:
        self._sync_matched_render_selection()

    def _matched_render_index(self, source: str) -> int | None:
        if self.auto_match_enabled():
            for source_color, target_color in auto_match_palette_pairs(
                self._source_colors,
                self._colors,
                self.match_sort_mode(),
            ):
                if source_color == source:
                    return self._color_index(self._colors, target_color)
            return None
        return self._nearest_render_index(source)

    def _nearest_render_index(self, source: str) -> int | None:
        nearest = nearest_palette_color(source, self._colors)
        if nearest is None:
            return None
        return self._color_index(self._colors, nearest)

    def _selected_source_color(self) -> str | None:
        index = self._selected_source_index
        if index is None or not 0 <= index < len(self._source_colors):
            return None
        return self._source_colors[index]

    def _selected_render_color(self) -> str | None:
        index = self._selected_index()
        if index is None:
            return None
        return self._colors[index]

    def _update_mapping_view(self) -> None:
        source = self._selected_source_color()
        target = self._selected_render_color()
        if source is not None and target is None:
            matched = self._matched_render_index(source)
            target = self._colors[matched] if matched is not None else None
        mode = "manual" if self._render_selection_manual else ("automatch" if self.auto_match_enabled() else "nearest")
        self.mapping_view.set_mapping(source, target, mode)

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)

    def _match_rows(self) -> list[MatchBoardRow]:
        if self._source_colors and self._colors:
            rows = self._auto_match_rows() if self.auto_match_enabled() else self._nearest_match_rows()
            used_render_indices = {row.render_index for row in rows if row.render_index is not None}
            for render_index, render_color in enumerate(self._colors):
                if render_index not in used_render_indices:
                    rows.append(MatchBoardRow(None, None, render_index, render_color, "extra"))
            return rows
        if self._source_colors:
            return [
                MatchBoardRow(source_index, source_color, None, None, "source")
                for source_index, source_color in enumerate(self._source_colors)
            ]
        return [
            MatchBoardRow(None, None, render_index, render_color, "render")
            for render_index, render_color in enumerate(self._colors)
        ]

    def _auto_match_rows(self) -> list["MatchBoardRow"]:
        rows: list[MatchBoardRow] = []
        for source_color, render_color in auto_match_palette_pairs(
            self._source_colors,
            self._colors,
            self.match_sort_mode(),
        ):
            rows.append(
                MatchBoardRow(
                    self._color_index(self._source_colors, source_color),
                    source_color,
                    self._color_index(self._colors, render_color),
                    render_color,
                    "auto",
                    perceptual_color_distance(source_color, render_color),
                )
            )
        return rows

    def _nearest_match_rows(self) -> list["MatchBoardRow"]:
        rows: list[MatchBoardRow] = []
        for source_index, source_color in enumerate(self._source_colors):
            render_index = self._nearest_render_index(source_color)
            render_color = self._colors[render_index] if render_index is not None else None
            distance = rgb_distance(source_color, render_color) if render_color is not None else None
            rows.append(MatchBoardRow(source_index, source_color, render_index, render_color, "nearest", distance))
        return rows

    def _color_index(self, colors: list[str], color: str) -> int | None:
        try:
            return colors.index(color)
        except ValueError:
            return None

    def _set_combo_data(self, combo: QComboBox, value: str) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return


@dataclass(frozen=True)
class MatchBoardRow:
    source_index: int | None
    source_color: str | None
    render_index: int | None
    render_color: str | None
    mode: str
    distance: float | None = None


class ColorMatchBoard(QWidget):
    sourceClicked = Signal(int)
    renderClicked = Signal(int)
    renderDoubleClicked = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(6)
        self._layout.setVerticalSpacing(5)
        self._row_count = 0

    def set_rows(
        self,
        rows: list[MatchBoardRow],
        selected_source_index: int | None,
        selected_render_index: int | None,
        auto_match_enabled: bool,
    ) -> None:
        self._clear()
        self._row_count = len(rows)
        if not rows:
            empty = QLabel("Extract source colors or add render colors to build a comparison board")
            empty.setWordWrap(True)
            empty.setStyleSheet("color: #8b949e; padding: 8px; background: #151719; border: 1px solid #3a3f45;")
            self._layout.addWidget(empty, 0, 0, 1, 3)
            return

        for column, title in enumerate(("Source", "Match", "Render")):
            header = QLabel(title)
            header.setStyleSheet("color: #8b949e; font-weight: 600;")
            self._layout.addWidget(header, 0, column)

        for row_index, row in enumerate(rows, start=1):
            self._layout.addWidget(
                self._source_widget(row, selected_source_index),
                row_index,
                0,
            )
            relation = QLabel(self._relation_text(row, auto_match_enabled))
            relation.setAlignment(Qt.AlignmentFlag.AlignCenter)
            relation.setStyleSheet("color: #cbd5e1; font-size: 10px;")
            self._layout.addWidget(relation, row_index, 1)
            self._layout.addWidget(
                self._render_widget(row, selected_render_index),
                row_index,
                2,
            )

    def row_count(self) -> int:
        return self._row_count

    def _source_widget(self, row: MatchBoardRow, selected_source_index: int | None) -> QWidget:
        if row.source_color is None or row.source_index is None:
            return _empty_match_cell("no source")
        button = MatchSwatchButton(row.source_index, row.source_color, selected_source_index == row.source_index)
        button.clicked.connect(lambda checked=False, value=row.source_index: self.sourceClicked.emit(value))
        return button

    def _render_widget(self, row: MatchBoardRow, selected_render_index: int | None) -> QWidget:
        if row.render_color is None or row.render_index is None:
            return _empty_match_cell("no render")
        button = MatchSwatchButton(row.render_index, row.render_color, selected_render_index == row.render_index)
        button.clicked.connect(lambda checked=False, value=row.render_index: self.renderClicked.emit(value))
        button.doubleClicked.connect(lambda value: self.renderDoubleClicked.emit(value))
        return button

    def _relation_text(self, row: MatchBoardRow, auto_match_enabled: bool) -> str:
        if row.source_index is None:
            return "render only"
        if row.render_index is None:
            return "unmatched"
        mode = "perceptual" if auto_match_enabled and row.mode == "auto" else row.mode
        distance = "" if row.distance is None else f"\n{row.distance:.3f}"
        return f"{mode}\n#{row.source_index + 1} -> #{row.render_index + 1}{distance}"

    def _clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._row_count = 0


class MatchSwatchButton(QPushButton):
    doubleClicked = Signal(int)

    def __init__(self, index: int, color: str, selected: bool) -> None:
        super().__init__()
        self.index = index
        self.setText(f"{index + 1}\n{color[1:]}")
        self.setFixedSize(QSize(90, 40))
        self.setToolTip(color)
        self.setStyleSheet(_swatch_stylesheet(color, selected))

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self.doubleClicked.emit(self.index)
        super().mouseDoubleClickEvent(event)


class ColorSwatchGrid(QWidget):
    colorClicked = Signal(int)
    colorDoubleClicked = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(6)
        self._layout.setVerticalSpacing(6)
        self._buttons: list[ColorSwatchButton] = []

    def set_colors(self, colors: list[str], selected_index: int | None, badges: list[str] | None = None) -> None:
        self._clear()
        badges = badges or [""] * len(colors)
        for index, color in enumerate(colors):
            badge = badges[index] if index < len(badges) else ""
            button = ColorSwatchButton(index, color, selected_index == index, badge)
            button.clicked.connect(lambda checked=False, value=index: self.colorClicked.emit(value))
            button.doubleClicked.connect(lambda value: self.colorDoubleClicked.emit(value))
            self._layout.addWidget(button, index // 3, index % 3)
            self._buttons.append(button)

    def button_count(self) -> int:
        return len(self._buttons)

    def _clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._buttons = []


class ColorSwatchButton(QPushButton):
    doubleClicked = Signal(int)

    def __init__(self, index: int, color: str, selected: bool, badge: str = "") -> None:
        super().__init__()
        self.index = index
        self.color = color
        label = f"{index + 1}\n{color[1:]}"
        if badge:
            label = f"{label}\n{badge}"
        self.setText(label)
        self.setFixedSize(QSize(82, 58))
        self.setToolTip(color)
        self.setStyleSheet(_swatch_stylesheet(color, selected))

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self.doubleClicked.emit(self.index)
        super().mouseDoubleClickEvent(event)


class ColorMappingView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.source_chip = QLabel()
        self.target_chip = QLabel()
        self.mapping_label = QLabel("Select a source color to see nearest render color")
        self.mapping_label.setWordWrap(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.source_chip)
        layout.addWidget(self.target_chip)
        layout.addWidget(self.mapping_label, 1)
        self.set_mapping(None, None, "nearest")

    def set_mapping(self, source: str | None, target: str | None, mode: str) -> None:
        self._set_chip(self.source_chip, source)
        self._set_chip(self.target_chip, target)
        if source is None or target is None:
            self.mapping_label.setText("Select a source color to see its render pairing")
            return
        label = {
            "manual": "manual reference",
            "automatch": "AutoMatch perceptual",
            "nearest": "nearest color",
        }.get(mode, mode)
        if mode == "automatch":
            distance = perceptual_color_distance(source, target)
            self.mapping_label.setText(f"{source} -> {target} ({label}, perceptual distance {distance:.3f})")
            return
        distance = rgb_distance(source, target)
        self.mapping_label.setText(f"{source} -> {target} ({label}, RGB distance {distance:.1f})")

    def _set_chip(self, label: QLabel, color: str | None) -> None:
        label.setFixedSize(QSize(48, 42))
        if color is None:
            label.setText("-")
            label.setStyleSheet("background: #151719; border: 1px solid #3a3f45; color: #8b949e;")
            return
        label.setText(color[1:])
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(_label_swatch_stylesheet(color))


class ColorSpaceWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(120)
        self._source_colors: list[str] = []
        self._render_colors: list[str] = []
        self._selected_source_index: int | None = None
        self._selected_render_index: int | None = None

    def set_palettes(
        self,
        source_colors: list[str],
        render_colors: list[str],
        selected_source_index: int | None,
        selected_render_index: int | None,
    ) -> None:
        self._source_colors = list(source_colors)
        self._render_colors = list(render_colors)
        self._selected_source_index = selected_source_index
        self._selected_render_index = selected_render_index
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#151719"))
        painter.setPen(QPen(QColor("#3a3f45"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        painter.setPen(QColor("#8b949e"))
        painter.drawText(8, 16, "Hue -> / Brightness")

        self._paint_points(painter, self._source_colors, QColor("#fbbf24"), square=True)
        self._paint_points(painter, self._render_colors, QColor("#7dd3fc"), square=False)

    def _paint_points(self, painter: QPainter, colors: list[str], outline: QColor, square: bool) -> None:
        width = max(1, self.width() - 24)
        height = max(1, self.height() - 34)
        for index, color in enumerate(colors):
            hue, value = hsv_position(color)
            x = 12 + round(hue * width)
            y = 24 + round((1.0 - value) * height)
            selected = (
                square and index == self._selected_source_index
                or not square and index == self._selected_render_index
            )
            radius = 6 if selected else 4
            painter.setBrush(QColor(color))
            painter.setPen(QPen(outline, 3 if selected else 1))
            if square:
                painter.drawRect(x - radius, y - radius, radius * 2, radius * 2)
            else:
                painter.drawEllipse(x - radius, y - radius, radius * 2, radius * 2)


def _section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("panelTitle")
    return label


def _empty_match_cell(text: str) -> QLabel:
    label = QLabel(text)
    label.setFixedSize(QSize(90, 40))
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet("background: #151719; color: #8b949e; border: 1px solid #3a3f45; font-size: 10px;")
    return label


def _swatch_stylesheet(color: str, selected: bool) -> str:
    text = "#111111" if _luminance(QColor(color)) > 150 else "#ffffff"
    border = "#7dd3fc" if selected else "#3a3f45"
    return (
        "QPushButton {"
        f"background: {color}; color: {text}; border: 3px solid {border};"
        "font-size: 10px; font-weight: 600; padding: 2px;"
        "}"
    )


def _label_swatch_stylesheet(color: str) -> str:
    text = "#111111" if _luminance(QColor(color)) > 150 else "#ffffff"
    return f"background: {color}; color: {text}; border: 1px solid #3a3f45; font-size: 9px;"


def _luminance(color: QColor) -> float:
    return (0.299 * color.red()) + (0.587 * color.green()) + (0.114 * color.blue())
