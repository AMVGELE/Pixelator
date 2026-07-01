from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, QSettings, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pixelator.ai.constants import (
    ART_STYLE_LABELS,
    ART_STYLES,
    ASSET_TYPE_LABELS,
    ASSET_TYPES,
    ASSET_VIEWS,
    DEFAULT_DASHSCOPE_IMAGE_ENDPOINT,
    DEFAULT_DASHSCOPE_TASK_ENDPOINT,
    DEFAULT_IMAGE_MODEL,
    GAME_GENRE_LABELS,
    GAME_GENRES,
    VIEW_LABELS,
)
from pixelator.ai.env import config_value, save_local_env_value
from pixelator.ai.prompt_builder import build_prompt
from pixelator.ai.types import AiAssetRecord, AiGenerationRequest, DashScopeConfig, PromptResult


class QwenLabPanel(QWidget):
    generateRequested = Signal(object, object, object)

    def __init__(self) -> None:
        super().__init__()
        self._settings = QSettings("Pixelator", "Pixelator")
        self._records: list[AiAssetRecord] = []
        self.description_edit = QPlainTextEdit()
        self.description_edit.setPlaceholderText("Clockwork owl familiar")
        self.description_edit.setFixedHeight(54)
        self.keywords_edit = QLineEdit()
        self.keywords_edit.setPlaceholderText("extra materials, silhouette, camera rules")

        self.asset_type_combo = self._combo(ASSET_TYPES, ASSET_TYPE_LABELS)
        self.style_combo = self._combo(ART_STYLES, ART_STYLE_LABELS)
        self.game_genre_combo = self._combo(GAME_GENRES, GAME_GENRE_LABELS)
        self.view_combo = self._combo(ASSET_VIEWS, VIEW_LABELS)

        self.positive_prompt_edit = QPlainTextEdit()
        self.positive_prompt_edit.setFixedHeight(118)
        self.negative_prompt_edit = QPlainTextEdit()
        self.negative_prompt_edit.setFixedHeight(82)
        self.rebuild_prompt_button = QPushButton("Rebuild Prompt")

        self.width_spin = QSpinBox()
        self.height_spin = QSpinBox()
        for spin in (self.width_spin, self.height_spin):
            spin.setRange(16, 4096)
            spin.setSingleStep(16)
            spin.setValue(512)
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 6)
        self.count_spin.setValue(1)
        self.background_combo = QComboBox()
        self.background_combo.addItem("Keep background", "scene")
        self.background_combo.addItem("Transparent cutout", "transparent")

        self.model_edit = QLineEdit(config_value("IMAGE_MODEL", DEFAULT_IMAGE_MODEL))
        self.endpoint_edit = QLineEdit(config_value("DASHSCOPE_IMAGE_ENDPOINT", DEFAULT_DASHSCOPE_IMAGE_ENDPOINT))
        self.task_endpoint_edit = QLineEdit(config_value("DASHSCOPE_TASK_ENDPOINT", DEFAULT_DASHSCOPE_TASK_ENDPOINT))
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("Uses DASHSCOPE_API_KEY or .env.local when empty")
        self.save_api_key_button = QPushButton("Save")
        self.key_source_label = QLabel(self._key_source_text())

        self.generate_button = QPushButton("Generate And Add")
        self.status_label = QLabel("Ready")
        self.result_list = QListWidget()
        self.result_list.setIconSize(QSize(48, 48))

        self._build_layout()
        self._connect_signals()
        self._load_settings()
        self._refresh_prompt_editor()

    def generation_request(self) -> tuple[AiGenerationRequest, PromptResult]:
        description = self._description()
        if len(description) < 2:
            raise ValueError("Description must be at least 2 characters.")
        self._validate_pixel_budget()
        prompt = PromptResult(
            positive_prompt=self._clean_multiline(self.positive_prompt_edit.toPlainText()),
            negative_prompt=self._clean_multiline(self.negative_prompt_edit.toPlainText()),
        )
        if not prompt.positive_prompt:
            raise ValueError("Positive prompt is required.")
        request = AiGenerationRequest(
            description=description,
            asset_type=str(self.asset_type_combo.currentData()),
            style=str(self.style_combo.currentData()),
            game_genre=str(self.game_genre_combo.currentData()),
            view=str(self.view_combo.currentData()),
            size=f"{self.width_spin.value()}x{self.height_spin.value()}",
            background=str(self.background_combo.currentData()),
            count=self.count_spin.value(),
        )
        request.validate()
        return request, prompt

    def config(self) -> DashScopeConfig:
        return DashScopeConfig(
            api_key=self.api_key_edit.text().strip(),
            model=self.model_edit.text().strip() or DEFAULT_IMAGE_MODEL,
            image_endpoint=self.endpoint_edit.text().strip() or DEFAULT_DASHSCOPE_IMAGE_ENDPOINT,
            task_endpoint=self.task_endpoint_edit.text().strip() or DEFAULT_DASHSCOPE_TASK_ENDPOINT,
        )

    def add_asset_records(self, records: list[AiAssetRecord]) -> None:
        self._records.extend(records)
        for record in records:
            item = QListWidgetItem(f"{record.name}\n{record.size} {record.background}")
            item.setData(Qt.ItemDataRole.UserRole, str(record.image_path))
            item.setToolTip(f"{record.prompt}\n\nNegative: {record.negative_prompt}")
            if record.image_path.exists():
                pixmap = QPixmap(str(record.image_path))
                if not pixmap.isNull():
                    item.setIcon(QIcon(pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio)))
            self.result_list.addItem(item)
        if records and self.result_list.currentRow() < 0:
            self.result_list.setCurrentRow(self.result_list.count() - len(records))

    def load_asset_records(self, records: list[AiAssetRecord]) -> None:
        self._records = []
        self.result_list.clear()
        self.add_asset_records(records)

    def latest_asset_path(self) -> Path | None:
        return self._records[-1].image_path if self._records else None

    def set_generating(self, generating: bool) -> None:
        self.generate_button.setEnabled(not generating)
        self.generate_button.setText("Generating..." if generating else "Generate And Add")
        if generating:
            self.status_label.setText("Generating")

    def set_status_message(self, message: str) -> None:
        self.status_label.setText(message)

    def _build_layout(self) -> None:
        title = QLabel("Qwen Lab")
        title.setObjectName("panelTitle")

        builder_group = QGroupBox("Prompt Builder")
        builder_form = QFormLayout(builder_group)
        builder_form.addRow("Description", self.description_edit)
        builder_form.addRow("Keywords", self.keywords_edit)
        builder_form.addRow("Asset type", self.asset_type_combo)
        builder_form.addRow("Style", self.style_combo)
        builder_form.addRow("Genre", self.game_genre_combo)
        builder_form.addRow("View", self.view_combo)
        builder_form.addRow("", self.rebuild_prompt_button)

        editor_group = QGroupBox("Prompt Editor")
        editor_form = QFormLayout(editor_group)
        editor_form.addRow("Positive", self.positive_prompt_edit)
        editor_form.addRow("Negative", self.negative_prompt_edit)

        generation_group = QGroupBox("Generation")
        generation_form = QFormLayout(generation_group)
        size_row = QHBoxLayout()
        size_row.addWidget(self.width_spin)
        size_row.addWidget(QLabel("x"))
        size_row.addWidget(self.height_spin)
        size_widget = QWidget()
        size_widget.setLayout(size_row)
        generation_form.addRow("Size", size_widget)
        generation_form.addRow("Count", self.count_spin)
        generation_form.addRow("Background", self.background_combo)
        generation_form.addRow("Qwen API key", self._api_key_row())
        generation_form.addRow("Key source", self.key_source_label)
        generation_form.addRow("Model", self.model_edit)
        generation_form.addRow("Endpoint", self.endpoint_edit)
        generation_form.addRow("Task endpoint", self.task_endpoint_edit)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.addWidget(builder_group)
        content_layout.addWidget(editor_group)
        content_layout.addWidget(generation_group)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        scroll.setMinimumHeight(360)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(scroll)
        layout.addWidget(self.generate_button)
        layout.addWidget(self.status_label)
        layout.addWidget(QLabel("Recent Outputs"))
        layout.addWidget(self.result_list, 1)

    def _connect_signals(self) -> None:
        self.generate_button.clicked.connect(self._on_generate_clicked)
        self.save_api_key_button.clicked.connect(self._on_save_api_key_clicked)
        self.rebuild_prompt_button.clicked.connect(self._refresh_prompt_editor)
        self.api_key_edit.textChanged.connect(lambda text: self.key_source_label.setText(self._key_source_text()))
        self.description_edit.textChanged.connect(self._refresh_prompt_editor)
        self.keywords_edit.textChanged.connect(lambda text: self._refresh_prompt_editor())
        for combo in (self.asset_type_combo, self.style_combo, self.game_genre_combo, self.view_combo):
            combo.currentIndexChanged.connect(lambda index: self._refresh_prompt_editor())

    def _on_generate_clicked(self) -> None:
        try:
            request, prompt = self.generation_request()
        except ValueError as exc:
            self.set_status_message(str(exc))
            return
        self._save_settings()
        self.generateRequested.emit(request, prompt, self.config())

    def _on_save_api_key_clicked(self) -> None:
        try:
            env_path = save_local_env_value("DASHSCOPE_API_KEY", self.api_key_edit.text())
        except (OSError, ValueError) as exc:
            self.set_status_message(f"Could not save Qwen API key: {exc}")
            return
        self.key_source_label.setText(f"Saved to {env_path.name}; CLI uses DASHSCOPE_API_KEY")
        self.set_status_message(f"Saved Qwen API key to {env_path}")

    def _refresh_prompt_editor(self) -> None:
        if len(self._description()) < 2:
            self.positive_prompt_edit.clear()
            self.negative_prompt_edit.clear()
            return
        try:
            prompt = build_prompt(self._builder_request())
        except ValueError as exc:
            self.positive_prompt_edit.setPlainText(str(exc))
            self.negative_prompt_edit.clear()
            return
        self.positive_prompt_edit.setPlainText(prompt.positive_prompt)
        self.negative_prompt_edit.setPlainText(prompt.negative_prompt)

    def _builder_request(self) -> AiGenerationRequest:
        description = self._description()
        keywords = self._clean_multiline(self.keywords_edit.text())
        prompt_description = ", ".join(part for part in (description, keywords) if part)
        return AiGenerationRequest(
            description=prompt_description,
            asset_type=str(self.asset_type_combo.currentData()),
            style=str(self.style_combo.currentData()),
            game_genre=str(self.game_genre_combo.currentData()),
            view=str(self.view_combo.currentData()),
            size=f"{self.width_spin.value()}x{self.height_spin.value()}",
            background=str(self.background_combo.currentData()),
            count=1,
        )

    def _validate_pixel_budget(self) -> None:
        pixels = self.width_spin.value() * self.height_spin.value()
        if pixels < 512 * 512 or pixels > 2048 * 2048:
            raise ValueError("Qwen Lab size must be between 512x512 and 2048x2048 total pixels.")

    def _load_settings(self) -> None:
        self._set_combo_value(self.asset_type_combo, self._settings.value("qwen_lab/asset_type", "character"))
        self._set_combo_value(self.style_combo, self._settings.value("qwen_lab/style", "pixel_art"))
        self._set_combo_value(self.game_genre_combo, self._settings.value("qwen_lab/game_genre", "rpg"))
        self._set_combo_value(self.view_combo, self._settings.value("qwen_lab/view", "front"))
        self.width_spin.setValue(int(self._settings.value("qwen_lab/width", 512)))
        self.height_spin.setValue(int(self._settings.value("qwen_lab/height", 512)))
        self.count_spin.setValue(int(self._settings.value("qwen_lab/count", 1)))
        self._set_combo_value(self.background_combo, self._settings.value("qwen_lab/background", "scene"))
        self.model_edit.setText(str(self._settings.value("qwen_lab/model", self.model_edit.text())))
        self.endpoint_edit.setText(str(self._settings.value("qwen_lab/endpoint", self.endpoint_edit.text())))
        self.task_endpoint_edit.setText(
            str(self._settings.value("qwen_lab/task_endpoint", self.task_endpoint_edit.text()))
        )

    def _save_settings(self) -> None:
        self._settings.setValue("qwen_lab/asset_type", self.asset_type_combo.currentData())
        self._settings.setValue("qwen_lab/style", self.style_combo.currentData())
        self._settings.setValue("qwen_lab/game_genre", self.game_genre_combo.currentData())
        self._settings.setValue("qwen_lab/view", self.view_combo.currentData())
        self._settings.setValue("qwen_lab/width", self.width_spin.value())
        self._settings.setValue("qwen_lab/height", self.height_spin.value())
        self._settings.setValue("qwen_lab/count", self.count_spin.value())
        self._settings.setValue("qwen_lab/background", self.background_combo.currentData())
        self._settings.setValue("qwen_lab/model", self.model_edit.text())
        self._settings.setValue("qwen_lab/endpoint", self.endpoint_edit.text())
        self._settings.setValue("qwen_lab/task_endpoint", self.task_endpoint_edit.text())

    def _description(self) -> str:
        return self._clean_multiline(self.description_edit.toPlainText())

    def _key_source_text(self) -> str:
        if hasattr(self, "api_key_edit") and self.api_key_edit.text().strip():
            return "Using key in field"
        if config_value("DASHSCOPE_API_KEY"):
            return "Configured from environment or .env.local"
        return "Not configured; paste a key above"

    def _api_key_row(self) -> QWidget:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.api_key_edit, 1)
        row.addWidget(self.save_api_key_button)
        widget = QWidget()
        widget.setLayout(row)
        return widget

    def _combo(self, values: tuple[str, ...], labels: dict[str, str]) -> QComboBox:
        combo = QComboBox()
        for value in values:
            combo.addItem(labels[value], value)
        return combo

    def _set_combo_value(self, combo: QComboBox, value: object) -> None:
        index = combo.findData(str(value))
        if index >= 0:
            combo.setCurrentIndex(index)

    def _clean_multiline(self, value: str) -> str:
        return "\n".join(line.strip() for line in value.strip().splitlines() if line.strip())
