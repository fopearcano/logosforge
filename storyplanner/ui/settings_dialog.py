"""Global settings dialog — appearance and AI provider configuration."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from storyplanner.ui import theme
from storyplanner.ui.provider_settings import ProviderSettingsWidget


class SettingsDialog(QDialog):
    def __init__(
        self,
        on_theme_changed: Callable[[str], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._on_theme_changed = on_theme_changed

        self.setWindowTitle("Preferences")
        self.setMinimumWidth(480)
        self.setMaximumWidth(600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # -- Appearance ---------------------------------------------------------
        layout.addWidget(self._section_label("Appearance"))

        theme_row = QHBoxLayout()
        theme_row.setSpacing(6)
        self._theme_btns: dict[str, QPushButton] = {}
        for name, label in (
            ("Dark", "Dark"),
            ("Light (Green)", "Light (Green)"),
            ("Light (Warm)", "Light (Warm)"),
        ):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(name == theme.current_palette())
            btn.clicked.connect(lambda _, n=name: self._select_theme(n))
            theme_row.addWidget(btn)
            self._theme_btns[name] = btn
        theme_row.addStretch()
        layout.addLayout(theme_row)

        layout.addWidget(self._separator())

        # -- AI Provider --------------------------------------------------------
        layout.addWidget(self._section_label("AI Provider"))

        self._provider_widget = ProviderSettingsWidget(compact=True)
        layout.addWidget(self._provider_widget)

        layout.addWidget(self._separator())

        # -- General (placeholder) ---------------------------------------------
        layout.addWidget(self._section_label("General"))
        placeholder = QLabel("No additional settings yet.")
        placeholder.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(placeholder)

        layout.addStretch()

        # -- Close button -------------------------------------------------------
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

    def _select_theme(self, name: str) -> None:
        for key, btn in self._theme_btns.items():
            btn.setChecked(key == name)
        self._on_theme_changed(name)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f"color: {theme.TEXT_PRIMARY}; font-weight: bold; font-size: 13px;"
            f" padding: 0; margin: 0;"
        )
        return label

    @staticmethod
    def _separator() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {theme.BORDER};")
        return sep
