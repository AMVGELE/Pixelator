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
    ASSET_SIZES,
    ASSET_TYPE_LABELS,
    ASSET_TYPES,
    ASSET_VIEWS,
    BACKGROUND_LABELS,
    BACKGROUND_MODES,
    DEFAULT_DASHSCOPE_IMAGE_ENDPOINT,
    DEFAULT_DASHSCOPE_TASK_ENDPOINT,
    DEFAULT_IMAGE_MODEL,
    GAME_GENRE_LABELS,
    GAME_GENRES,
    VIEW_LABELS,
)
from pixelator.ai.env import config_value, save_local_env_value
from pixelator.ai.prompt_builder import build_prompt
from pixelator.ai.types import AiAssetRecord, AiGenerationRequest, DashScopeConfig, StyleProfile


class AiAssetsPanel(QWidget):
    generateRequested = Signal(object, object)
    addAssetToQueueRequested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._settings = QSettings("Pixelator", "Pixelator")
        self._records: list[AiAssetRecord] = []
        self.description_edit = QPlainTextEdit()
        self.description_edit.setPlaceholderText("火焰史莱姆怪物")
        self.description_edit.setFixedHeight(54)

        self.asset_type_combo = self._combo(ASSET_TYPES, ASSET_TYPE_LABELS)
        self.style_combo = self._combo(ART_STYLES, ART_STYLE_LABELS)
        self.game_genre_combo = self._combo(GAME_GENRES, GAME_GENRE_LABELS)
        self.view_combo = self._combo(ASSET_VIEWS, VIEW_LABELS)
        self.size_combo = QComboBox()
        self.size_combo.addItems(ASSET_SIZES)
        self.background_combo = self._combo(BACKGROUND_MODES, BACKGROUND_LABELS)
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 6)
        self.count_spin.setValue(1)

        self.project_name_edit = QLineEdit()
        self.palette_edit = QLineEdit()
        self.line_style_edit = QLineEdit()
        self.lighting_edit = QLineEdit()
        self.view_rule_edit = QLineEdit()
        self.avoid_elements_edit = QLineEdit()

        self.model_edit = QLineEdit(config_value("IMAGE_MODEL", DEFAULT_IMAGE_MODEL))
        self.endpoint_edit = QLineEdit(config_value("DASHSCOPE_IMAGE_ENDPOINT", DEFAULT_DASHSCOPE_IMAGE_ENDPOINT))
        self.task_endpoint_edit = QLineEdit(config_value("DASHSCOPE_TASK_ENDPOINT", DEFAULT_DASHSCOPE_TASK_ENDPOINT))
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("留空时使用 DASHSCOPE_API_KEY 或 .env.local")
        self.save_api_key_button = QPushButton("保存")
        self.key_source_label = QLabel(self._key_source_text())

        self.prompt_preview = QPlainTextEdit()
        self.prompt_preview.setReadOnly(True)
        self.prompt_preview.setFixedHeight(108)

        self.generate_button = QPushButton("生成")
        self.add_to_queue_button = QPushButton("加入队列")
        self.add_to_queue_button.setEnabled(False)
        self.status_label = QLabel("就绪")
        self.result_list = QListWidget()
        self.result_list.setIconSize(QSize(48, 48))

        self._build_layout()
        self._connect_signals()
        self._load_settings()
        self._refresh_prompt_preview()

    def request(self) -> AiGenerationRequest:
        request = AiGenerationRequest(
            description=self.description_edit.toPlainText(),
            asset_type=str(self.asset_type_combo.currentData()),
            style=str(self.style_combo.currentData()),
            game_genre=str(self.game_genre_combo.currentData()),
            view=str(self.view_combo.currentData()),
            size=self.size_combo.currentText(),
            background=str(self.background_combo.currentData()),
            count=self.count_spin.value(),
            style_profile=StyleProfile(
                project_name=self.project_name_edit.text(),
                palette=self.palette_edit.text(),
                line_style=self.line_style_edit.text(),
                lighting=self.lighting_edit.text(),
                view_rule=self.view_rule_edit.text(),
                avoid_elements=self.avoid_elements_edit.text(),
            ),
        )
        request.validate()
        return request

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
            item = QListWidgetItem(f"{record.name}\n{record.size} {record.asset_type}")
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
        self.generate_button.setText("生成中..." if generating else "生成")
        if generating:
            self.status_label.setText("生成中")

    def set_status_message(self, message: str) -> None:
        self.status_label.setText(message)

    def _build_layout(self) -> None:
        title = QLabel("AI 资产生成")
        title.setObjectName("panelTitle")

        provider_group = QGroupBox("服务设置")
        provider_form = QFormLayout(provider_group)
        provider_form.addRow("Qwen API key", self._api_key_row())
        provider_form.addRow("密钥来源", self.key_source_label)
        provider_form.addRow("模型", self.model_edit)
        provider_form.addRow("接口", self.endpoint_edit)
        provider_form.addRow("任务接口", self.task_endpoint_edit)

        form = QFormLayout()
        form.addRow("描述", self.description_edit)
        form.addRow("资产类型", self.asset_type_combo)
        form.addRow("风格", self.style_combo)
        form.addRow("游戏类型", self.game_genre_combo)
        form.addRow("视角", self.view_combo)
        form.addRow("尺寸", self.size_combo)
        form.addRow("背景", self.background_combo)
        form.addRow("数量", self.count_spin)
        form.addRow("项目", self.project_name_edit)
        form.addRow("色盘", self.palette_edit)
        form.addRow("线条风格", self.line_style_edit)
        form.addRow("光照", self.lighting_edit)
        form.addRow("视角规则", self.view_rule_edit)
        form.addRow("避免元素", self.avoid_elements_edit)
        form_widget = QWidget()
        form_widget.setLayout(form)
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setWidget(form_widget)
        form_scroll.setMinimumHeight(220)

        action_row = QHBoxLayout()
        action_row.addWidget(self.generate_button)
        action_row.addWidget(self.add_to_queue_button)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(provider_group)
        layout.addWidget(form_scroll)
        layout.addWidget(QLabel("提示词预览"))
        layout.addWidget(self.prompt_preview)
        layout.addLayout(action_row)
        layout.addWidget(self.status_label)
        layout.addWidget(QLabel("已生成资产"))
        layout.addWidget(self.result_list, 1)

    def _connect_signals(self) -> None:
        self.generate_button.clicked.connect(self._on_generate_clicked)
        self.save_api_key_button.clicked.connect(self._on_save_api_key_clicked)
        self.add_to_queue_button.clicked.connect(self._on_add_to_queue_clicked)
        self.result_list.currentItemChanged.connect(lambda current, previous: self._on_selection_changed())
        self.description_edit.textChanged.connect(self._refresh_prompt_preview)
        self.api_key_edit.textChanged.connect(lambda text: self.key_source_label.setText(self._key_source_text()))
        for combo in (
            self.asset_type_combo,
            self.style_combo,
            self.game_genre_combo,
            self.view_combo,
            self.size_combo,
            self.background_combo,
        ):
            combo.currentIndexChanged.connect(lambda index: self._refresh_prompt_preview())
        for spin in (self.count_spin,):
            spin.valueChanged.connect(lambda value: self._refresh_prompt_preview())
        for edit in (
            self.project_name_edit,
            self.palette_edit,
            self.line_style_edit,
            self.lighting_edit,
            self.view_rule_edit,
            self.avoid_elements_edit,
        ):
            edit.textChanged.connect(lambda text: self._refresh_prompt_preview())

    def _on_generate_clicked(self) -> None:
        try:
            request = self.request()
        except ValueError as exc:
            self.set_status_message(str(exc))
            return
        self._save_settings()
        self.generateRequested.emit(request, self.config())

    def _on_save_api_key_clicked(self) -> None:
        try:
            env_path = save_local_env_value("DASHSCOPE_API_KEY", self.api_key_edit.text())
        except (OSError, ValueError) as exc:
            self.set_status_message(f"无法保存 Qwen API key：{exc}")
            return
        self.key_source_label.setText(f"已保存到 {env_path.name}；CLI 使用 DASHSCOPE_API_KEY")
        self.set_status_message(f"已保存 Qwen API key 到 {env_path}")

    def _on_add_to_queue_clicked(self) -> None:
        item = self.result_list.currentItem()
        if item is None:
            return
        path = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if path:
            self.addAssetToQueueRequested.emit(path)

    def _on_selection_changed(self) -> None:
        self.add_to_queue_button.setEnabled(self.result_list.currentItem() is not None)

    def _refresh_prompt_preview(self) -> None:
        try:
            prompt = build_prompt(self.request())
        except ValueError as exc:
            self.prompt_preview.setPlainText(str(exc))
            return
        self.prompt_preview.setPlainText(
            f"正向：\n{prompt.positive_prompt}\n\n反向：\n{prompt.negative_prompt}"
        )

    def _load_settings(self) -> None:
        self._set_combo_value(self.asset_type_combo, self._settings.value("ai/asset_type", "character"))
        self._set_combo_value(self.style_combo, self._settings.value("ai/style", "pixel_art"))
        self._set_combo_value(self.game_genre_combo, self._settings.value("ai/game_genre", "rpg"))
        self._set_combo_value(self.view_combo, self._settings.value("ai/view", "front"))
        self.size_combo.setCurrentText(str(self._settings.value("ai/size", "128x128")))
        self._set_combo_value(self.background_combo, self._settings.value("ai/background", "transparent"))
        self.count_spin.setValue(int(self._settings.value("ai/count", 1)))
        self.project_name_edit.setText(str(self._settings.value("ai/project_name", "")))
        self.palette_edit.setText(str(self._settings.value("ai/palette", "")))
        self.line_style_edit.setText(str(self._settings.value("ai/line_style", "")))
        self.lighting_edit.setText(str(self._settings.value("ai/lighting", "")))
        self.view_rule_edit.setText(str(self._settings.value("ai/view_rule", "")))
        self.avoid_elements_edit.setText(str(self._settings.value("ai/avoid_elements", "")))
        self.model_edit.setText(str(self._settings.value("ai/model", self.model_edit.text())))
        self.endpoint_edit.setText(str(self._settings.value("ai/endpoint", self.endpoint_edit.text())))
        self.task_endpoint_edit.setText(str(self._settings.value("ai/task_endpoint", self.task_endpoint_edit.text())))

    def _save_settings(self) -> None:
        self._settings.setValue("ai/asset_type", self.asset_type_combo.currentData())
        self._settings.setValue("ai/style", self.style_combo.currentData())
        self._settings.setValue("ai/game_genre", self.game_genre_combo.currentData())
        self._settings.setValue("ai/view", self.view_combo.currentData())
        self._settings.setValue("ai/size", self.size_combo.currentText())
        self._settings.setValue("ai/background", self.background_combo.currentData())
        self._settings.setValue("ai/count", self.count_spin.value())
        self._settings.setValue("ai/project_name", self.project_name_edit.text())
        self._settings.setValue("ai/palette", self.palette_edit.text())
        self._settings.setValue("ai/line_style", self.line_style_edit.text())
        self._settings.setValue("ai/lighting", self.lighting_edit.text())
        self._settings.setValue("ai/view_rule", self.view_rule_edit.text())
        self._settings.setValue("ai/avoid_elements", self.avoid_elements_edit.text())
        self._settings.setValue("ai/model", self.model_edit.text())
        self._settings.setValue("ai/endpoint", self.endpoint_edit.text())
        self._settings.setValue("ai/task_endpoint", self.task_endpoint_edit.text())

    def _key_source_text(self) -> str:
        if hasattr(self, "api_key_edit") and self.api_key_edit.text().strip():
            return "使用本次粘贴的密钥"
        if config_value("DASHSCOPE_API_KEY"):
            return "来自环境变量或 .env.local"
        return "未配置，请在上方粘贴密钥"

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
