"""Reusable provider settings widget for the writing assistant views."""

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from storyplanner.assistant import test_connection
from storyplanner.providers import (
    PROVIDER_CAPABILITIES,
    PROVIDER_NAMES,
    ProviderConfig,
    default_config,
    validate_provider,
)
from storyplanner.ui import theme


class _TestWorker(QThread):
    finished = Signal(bool, str)

    def __init__(self, provider: ProviderConfig) -> None:
        super().__init__()
        self._provider = provider

    def run(self) -> None:
        ok, msg = test_connection(self._provider)
        self.finished.emit(ok, msg)


class ProviderSettingsWidget(QWidget):
    def __init__(self, compact: bool = False) -> None:
        super().__init__()
        self._test_worker: _TestWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Row 1: provider + model + defaults
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Provider:"))
        self._provider_combo = QComboBox()
        for name in PROVIDER_NAMES:
            self._provider_combo.addItem(name)
        self._provider_combo.currentTextChanged.connect(self._on_provider_changed)
        row1.addWidget(self._provider_combo)

        row1.addWidget(QLabel("Model:"))
        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        self._model_combo.setMaximumWidth(200)
        row1.addWidget(self._model_combo)

        self._defaults_btn = QPushButton("Defaults")
        self._defaults_btn.setMaximumWidth(70)
        self._defaults_btn.clicked.connect(self._load_defaults)
        row1.addWidget(self._defaults_btn)
        row1.addStretch()
        layout.addLayout(row1)

        # Row 2: URL + API key + test
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("URL:"))
        self._url_input = QLineEdit()
        self._url_input.setMaximumWidth(300)
        row2.addWidget(self._url_input)

        self._key_label = QLabel("Key:")
        row2.addWidget(self._key_label)
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setMaximumWidth(200)
        self._key_input.setPlaceholderText("not required")
        row2.addWidget(self._key_input)

        self._test_btn = QPushButton("Test")
        self._test_btn.setMaximumWidth(60)
        self._test_btn.clicked.connect(self._on_test)
        row2.addWidget(self._test_btn)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("font-size: 11px;")
        row2.addWidget(self._status_label)
        row2.addStretch()
        layout.addLayout(row2)

        self._on_provider_changed(self._provider_combo.currentText())

    def _on_provider_changed(self, name: str) -> None:
        caps = PROVIDER_CAPABILITIES.get(name)
        if caps is None:
            return
        self._url_input.setText(caps.default_base_url)

        self._model_combo.clear()
        for m in caps.default_models:
            self._model_combo.addItem(m)
        if caps.default_models:
            self._model_combo.setCurrentText(caps.default_models[0])
        else:
            self._model_combo.setCurrentText("")
        self._model_combo.lineEdit().setPlaceholderText(
            caps.default_models[0] if caps.default_models else "server default"
        )

        self._key_label.setVisible(caps.requires_api_key)
        self._key_input.setVisible(caps.requires_api_key)
        self._key_input.setPlaceholderText(
            "required" if caps.requires_api_key else "not required"
        )
        if not caps.requires_api_key:
            self._key_input.clear()
        self._status_label.setText("")

    def _load_defaults(self) -> None:
        name = self._provider_combo.currentText()
        caps = PROVIDER_CAPABILITIES.get(name)
        if caps is None:
            return
        self._url_input.setText(caps.default_base_url)
        if caps.default_models:
            self._model_combo.setCurrentText(caps.default_models[0])
        else:
            self._model_combo.setCurrentText("")
        self._status_label.setText("")

    def get_provider_config(self) -> ProviderConfig:
        name = self._provider_combo.currentText()
        caps = PROVIDER_CAPABILITIES.get(name)
        extra = dict(caps.extra_headers) if caps else {}
        return ProviderConfig(
            name=name,
            base_url=self._url_input.text().strip()
            or (caps.default_base_url if caps else ""),
            api_key=self._key_input.text().strip(),
            model=self._model_combo.currentText().strip(),
            extra_headers=extra,
        )

    def validate(self) -> str | None:
        return validate_provider(self.get_provider_config())

    def _on_test(self) -> None:
        if self._test_worker is not None:
            return
        error = self.validate()
        if error:
            self._status_label.setStyleSheet(
                f"font-size: 11px; color: {theme.STATUS_ERR};"
            )
            self._status_label.setText(error)
            return

        provider = self.get_provider_config()
        self._status_label.setStyleSheet(
            f"font-size: 11px; color: {theme.TEXT_SECONDARY};"
        )
        self._status_label.setText("Testing...")
        self._test_btn.setEnabled(False)

        self._test_worker = _TestWorker(provider)
        self._test_worker.finished.connect(self._on_test_done)
        self._test_worker.start()

    def _on_test_done(self, ok: bool, msg: str) -> None:
        if ok:
            self._status_label.setStyleSheet(
                f"font-size: 11px; color: {theme.STATUS_OK};"
            )
        else:
            self._status_label.setStyleSheet(
                f"font-size: 11px; color: {theme.STATUS_ERR};"
            )
        self._status_label.setText(msg[:80])
        self._test_btn.setEnabled(True)
        self._test_worker = None
