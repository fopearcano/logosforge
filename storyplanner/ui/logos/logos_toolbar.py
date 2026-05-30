"""LogosToolbar — a compact, non-intrusive inline Logos entry point (Phase 0).

A slim horizontal bar that sits below the section content. It shows the Logos
actions available for the current section and renders the structured
:class:`LogosResult` in a small read-only area. It is hidden by default, never
pops up on its own, and never steals focus.

It is deliberately separate from AssistantPanel/AssistantDock: it does not touch
them, owns no provider settings, and only calls the shared LogosController.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from storyplanner.logos.controller import LogosController
from storyplanner.ui import theme


class LogosToolbar(QWidget):
    """Inline Logos action bar + result preview for one section at a time."""

    # Emitted after an action runs (mostly for tests / diagnostics).
    action_completed = Signal(str, bool)  # (action_name, ok)

    def __init__(
        self,
        controller: LogosController,
        context_provider: Callable[[], object],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        # Pulls a fresh LogosContext on demand (so selection/section are live).
        self._context_provider = context_provider
        self._section = ""
        self._busy = False

        self.setObjectName("logosToolbar")
        # Don't grab focus when shown — Logos must never steal the caret.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 6)
        outer.setSpacing(4)

        self._row = QHBoxLayout()
        self._row.setSpacing(6)
        self._title = QLabel("Logos")
        self._title.setStyleSheet(
            f"color: {theme.ACCENT}; font-weight: bold; font-size: 11px;"
        )
        self._row.addWidget(self._title)
        self._buttons_host = QHBoxLayout()
        self._buttons_host.setSpacing(4)
        self._row.addLayout(self._buttons_host)
        self._row.addStretch()
        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 10px;")
        self._row.addWidget(self._status)
        outer.addLayout(self._row)

        self._result = QPlainTextEdit()
        self._result.setReadOnly(True)
        self._result.setMaximumHeight(96)
        self._result.setPlaceholderText(
            "Select text (Manuscript) or open a scene, then run a Logos action.",
        )
        self._result.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        outer.addWidget(self._result)

        self._action_buttons: list[QPushButton] = []

    # -- Section wiring ------------------------------------------------------

    def set_section(self, section_name: str) -> None:
        if section_name == self._section:
            return
        self._section = section_name
        self.refresh_actions()

    def refresh_actions(self) -> None:
        # Clear existing buttons.
        for btn in self._action_buttons:
            self._buttons_host.removeWidget(btn)
            btn.deleteLater()
        self._action_buttons = []

        actions = self._controller.available_actions(self._section)
        for action in actions:
            btn = QPushButton(action.label)
            btn.setFlat(True)
            btn.setToolTip(action.description)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setStyleSheet(
                f"QPushButton {{ color: {theme.TEXT_SECONDARY}; border: 1px solid "
                f"{theme.BORDER}; border-radius: 4px; padding: 2px 8px; "
                f"font-size: 11px; }}"
                f"QPushButton:hover {{ color: {theme.TEXT_PRIMARY}; }}"
            )
            btn.clicked.connect(lambda _=False, n=action.name: self.run_action(n))
            self._buttons_host.addWidget(btn)
            self._action_buttons.append(btn)

        if not actions:
            self._status.setText("No Logos actions for this section yet.")
        else:
            self._status.setText("")

    # -- Run -----------------------------------------------------------------

    def run_action(self, action_name: str) -> None:
        if self._busy:
            return
        try:
            context = self._context_provider()
        except Exception as exc:  # never crash the host on context capture
            self._show_error(action_name, f"Could not read context: {exc}")
            return

        self._busy = True
        self._status.setText("Logos thinking…")
        try:
            result = self._controller.run(context, action_name)
        finally:
            self._busy = False
        self._status.setText("")
        self._render(result)
        self.action_completed.emit(action_name, result.ok)

    def _render(self, result) -> None:
        lines: list[str] = []
        if result.title:
            lines.append(f"▸ {result.title}")
        if not result.ok and result.error:
            lines.append(result.error)
        if result.message:
            lines.append(result.message)
        if result.suggestions:
            lines.append("")
            lines.extend(f"• {s}" for s in result.suggestions)
        self._result.setPlainText("\n".join(lines).strip())

    def _show_error(self, action_name: str, msg: str) -> None:
        self._result.setPlainText(msg)
        self.action_completed.emit(action_name, False)
