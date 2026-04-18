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
from storyplanner.providers import PROVIDER_DEFAULTS, PROVIDER_NAMES, ProviderConfig


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

        layout = QVBoxLayout(self) if not compact else QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Row 1: provider + model
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Provider:"))
        self._provider_combo = QComboBox()
        for name in PROVIDER_NAMES:
            self._provider_combo.addItem(name)
        self._provider_combo.currentTextChanged.connect(self._on_provider_changed)
        row1.addWidget(self._provider_combo)

        row1.addWidget(QLabel("Model:"))
        self._model_input = QLineEdit()
        self._model_input.setPlaceholderText("default")
        self._model_input.setMaximumWidth(200)
        row1.addWidget(self._model_input)
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
        defaults = PROVIDER_DEFAULTS.get(name)
        if defaults is None:
            return
        self._url_input.setText(defaults.base_url)
        self._model_input.setText(defaults.model)
        self._model_input.setPlaceholderText(
            defaults.model or "default"
        )
        needs_key = name in ("OpenAI", "OpenRouter")
        self._key_label.setVisible(needs_key)
        self._key_input.setVisible(needs_key)
        self._key_input.setPlaceholderText(
            "required" if needs_key else "not required"
        )
        if not needs_key:
            self._key_input.clear()
        self._status_label.setText("")

    def get_provider_config(self) -> ProviderConfig:
        name = self._provider_combo.currentText()
        defaults = PROVIDER_DEFAULTS.get(name)
        extra = dict(defaults.extra_headers) if defaults else {}
        return ProviderConfig(
            name=name,
            base_url=self._url_input.text().strip()
            or (defaults.base_url if defaults else ""),
            api_key=self._key_input.text().strip(),
            model=self._model_input.text().strip(),
            extra_headers=extra,
        )

    def _on_test(self) -> None:
        if self._test_worker is not None:
            return
        provider = self.get_provider_config()
        self._status_label.setStyleSheet(
            "font-size: 11px; color: #8b949e;"
        )
        self._status_label.setText("Testing...")
        self._test_btn.setEnabled(False)

        self._test_worker = _TestWorker(provider)
        self._test_worker.finished.connect(self._on_test_done)
        self._test_worker.start()

    def _on_test_done(self, ok: bool, msg: str) -> None:
        if ok:
            self._status_label.setStyleSheet(
                "font-size: 11px; color: #3fb950;"
            )
        else:
            self._status_label.setStyleSheet(
                "font-size: 11px; color: #f85149;"
            )
        self._status_label.setText(msg[:80])
        self._test_btn.setEnabled(True)
        self._test_worker = None
