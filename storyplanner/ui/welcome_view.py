"""First-launch welcome view — one heading, one line, one action."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from storyplanner.ui import theme


_PRIMARY_BTN_STYLE = (
    f"QPushButton {{"
    f"  background-color: {theme.SELECTION_BG};"
    f"  color: {theme.TEXT_PRIMARY};"
    f"  border: 1px solid {theme.ACCENT_DIM};"
    f"  border-radius: 3px; padding: 8px 28px;"
    f"  font-weight: bold;"
    f"}}"
    f"QPushButton:hover {{"
    f"  background-color: {theme.BG_HOVER};"
    f"  border-color: {theme.ACCENT};"
    f"}}"
)


class WelcomeView(QWidget):
    """Shown on first launch when no scenes exist."""

    def __init__(self, on_create_scene: Callable[[], None]) -> None:
        super().__init__()
        self._on_create_scene = on_create_scene

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        heading = QLabel("Welcome to Logosforge")
        heading_font = QFont()
        heading_font.setBold(True)
        heading_font.setPointSize(heading_font.pointSize() + 8)
        heading.setFont(heading_font)
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet(f"color: {theme.TEXT_PRIMARY};")
        layout.addWidget(heading)

        body = QLabel("Start by creating your first scene.")
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 13px;"
        )
        layout.addWidget(body)

        btn = QPushButton("Create Scene")
        btn.setStyleSheet(_PRIMARY_BTN_STYLE)
        btn.clicked.connect(self._on_create_scene)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
