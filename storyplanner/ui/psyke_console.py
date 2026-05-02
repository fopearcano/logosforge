"""PSYKE Console — minimal omnibox fixed at the bottom of the main window."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLineEdit,
    QWidget,
)

from storyplanner.ui import theme

_OPACITY_IDLE = 0.4
_OPACITY_ACTIVE = 1.0


class PsykeConsole(QWidget):
    """Slim search bar pinned to the bottom of the app."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setObjectName("psykeConsole")

        self._previous_focus: QWidget | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(0)

        self._input = QLineEdit()
        self._input.setPlaceholderText("\U0001F4D6  Search PSYKE…")
        self._input.setObjectName("psykeConsoleInput")
        self._input.setClearButtonEnabled(True)
        self._input.installEventFilter(self)
        layout.addWidget(self._input)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(_OPACITY_IDLE)
        self.setGraphicsEffect(self._opacity)

        self._apply_style()

    def activate(self) -> None:
        """Focus the console, remembering the previously focused widget."""
        current = QWidget.keyboardGrabber()
        if current is None:
            from PySide6.QtWidgets import QApplication
            current = QApplication.focusWidget()
        if current is not None and current is not self._input:
            self._previous_focus = current
        self._input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._input.selectAll()

    def deactivate(self) -> None:
        """Blur the console and restore focus to the previous widget."""
        self._input.clear()
        if self._previous_focus is not None:
            self._previous_focus.setFocus(Qt.FocusReason.OtherFocusReason)
            self._previous_focus = None
        else:
            self.clearFocus()

    def eventFilter(self, obj, event) -> bool:
        if obj is self._input:
            if event.type() == QEvent.Type.FocusIn:
                self._opacity.setOpacity(_OPACITY_ACTIVE)
            elif event.type() == QEvent.Type.FocusOut:
                self._opacity.setOpacity(_OPACITY_IDLE)
            elif event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Escape:
                    self.deactivate()
                    return True
        return super().eventFilter(obj, event)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            f"#psykeConsole {{"
            f"  background-color: {theme.BG_DARK};"
            f"  border-top: 1px solid {theme.BORDER};"
            f"}}"
            f"#psykeConsoleInput {{"
            f"  background-color: transparent;"
            f"  border: none;"
            f"  color: {theme.TEXT_MUTED};"
            f"  font-size: 12px;"
            f"  padding: 4px 6px;"
            f"}}"
            f"#psykeConsoleInput:focus {{"
            f"  color: {theme.TEXT_PRIMARY};"
            f"}}"
        )

    def refresh_style(self) -> None:
        self._apply_style()
