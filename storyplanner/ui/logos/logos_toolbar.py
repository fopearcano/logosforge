"""LogosToolbar — a compact, non-intrusive inline Logos entry point.

A slim bar that sits below the section content. It shows the Logos actions
available for the current section and renders the structured
:class:`LogosResult` in a small read-only area. It is hidden by default, never
pops up on its own, and never steals focus.

Phase 1: actions call the real (shared) Assistant backend off the UI thread so
the bar shows a visible loading state and stays responsive; the result can be
copied or dismissed; errors render in-place.

It is deliberately separate from AssistantPanel/AssistantDock: it does not touch
them, owns no provider settings, and only calls the shared LogosController.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from storyplanner.logos.controller import LogosController
from storyplanner.logos.result import LogosResult
from storyplanner.ui import theme


class _LogosWorker(QThread):
    """Runs a Logos action off the UI thread so the bar never freezes."""

    done = Signal(object)  # LogosResult

    def __init__(self, controller: LogosController, context, action_name: str) -> None:
        super().__init__()
        self._controller = controller
        self._context = context
        self._action_name = action_name

    def run(self) -> None:
        try:
            result = self._controller.run(self._context, self._action_name)
        except Exception as exc:  # pragma: no cover - defensive
            result = LogosResult.failure(self._action_name, f"Logos error: {exc}")
        self.done.emit(result)


class LogosToolbar(QWidget):
    """Inline Logos action bar + result preview for one section at a time."""

    action_completed = Signal(str, bool)  # (action_name, ok)

    def __init__(
        self,
        controller: LogosController,
        context_provider: Callable[[], object],
        parent: QWidget | None = None,
        on_request_apply: Callable[[object, object], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        # Pulls a fresh LogosContext on demand (so selection/section are live).
        self._context_provider = context_provider
        # Called when the user clicks "Apply…": (result, context) -> None.
        self._on_request_apply = on_request_apply
        self._section = ""
        self._worker: _LogosWorker | None = None
        self._last_result: LogosResult | None = None
        self._last_context: object | None = None

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

        self._copy_btn = self._tool_button("Copy", self._copy_result)
        self._dismiss_btn = self._tool_button("Dismiss", self.clear_result)
        self._apply_btn = self._tool_button("Apply…", self._request_apply)
        self._apply_btn.setEnabled(False)
        self._copy_btn.setEnabled(False)
        self._dismiss_btn.setEnabled(False)
        self._row.addWidget(self._apply_btn)
        self._row.addWidget(self._copy_btn)
        self._row.addWidget(self._dismiss_btn)
        outer.addLayout(self._row)

        self._result = QPlainTextEdit()
        self._result.setReadOnly(True)
        self._result.setMaximumHeight(120)
        self._result.setPlaceholderText(
            "Select text (Manuscript) or open an outline node, then run a Logos "
            "action.",
        )
        self._result.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        outer.addWidget(self._result)

        self._action_buttons: list[QPushButton] = []

    # -- Small helpers -------------------------------------------------------

    def _tool_button(self, label: str, slot: Callable[[], None]) -> QPushButton:
        btn = QPushButton(label)
        btn.setFlat(True)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setStyleSheet(
            f"QPushButton {{ color: {theme.TEXT_MUTED}; border: none; "
            f"font-size: 10px; padding: 1px 6px; }}"
            f"QPushButton:hover:enabled {{ color: {theme.TEXT_PRIMARY}; }}"
        )
        btn.clicked.connect(slot)
        return btn

    # -- Section wiring ------------------------------------------------------

    def set_section(self, section_name: str) -> None:
        if section_name == self._section:
            return
        self._section = section_name
        self.refresh_actions()

    def refresh_actions(self) -> None:
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
        """Pull a fresh context from the host, then run the action."""
        try:
            context = self._context_provider()
        except Exception as exc:  # never crash the host on context capture
            self._render(LogosResult.failure(action_name, f"Could not read context: {exc}"))
            self.action_completed.emit(action_name, False)
            return
        self.run_action_with_context(context, action_name)

    def run_action_with_context(self, context, action_name: str) -> None:
        """Run an action against an explicit context (e.g. an outline node)."""
        if self._worker is not None:
            return  # one at a time
        self._last_context = context
        self._set_busy(True)
        worker = _LogosWorker(self._controller, context, action_name)
        worker.done.connect(lambda res, n=action_name: self._on_done(n, res))
        self._worker = worker
        worker.start()

    def _on_done(self, action_name: str, result: LogosResult) -> None:
        self._worker = None
        self._set_busy(False)
        self._render(result)
        self.action_completed.emit(action_name, bool(result.ok))

    def _set_busy(self, busy: bool) -> None:
        self._status.setText("Logos thinking…" if busy else "")
        for btn in self._action_buttons:
            btn.setEnabled(not busy)

    # -- Result display ------------------------------------------------------

    def _render(self, result: LogosResult) -> None:
        self._last_result = result
        lines: list[str] = []
        if result.title:
            lines.append(f"▸ {result.title}")
        if not result.ok and result.error:
            lines.append(f"⚠ {result.error}")
        if result.message:
            lines.append(result.message)
        if result.suggestions:
            lines.append("")
            lines.extend(f"• {s}" for s in result.suggestions)
        text = "\n".join(lines).strip()
        self._result.setPlainText(text)
        has_text = bool(text)
        self._copy_btn.setEnabled(has_text)
        self._dismiss_btn.setEnabled(has_text)
        # "Apply…" only when the result carries confirmable operations and a
        # handler is wired.
        can_apply = bool(
            result.ok and result.proposed_operations and self._on_request_apply
        )
        self._apply_btn.setEnabled(can_apply)

    def _request_apply(self) -> None:
        if (
            self._on_request_apply is None
            or self._last_result is None
            or not self._last_result.proposed_operations
        ):
            return
        self._on_request_apply(self._last_result, self._last_context)

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def result_text(self) -> str:
        return self._result.toPlainText()

    def clear_result(self) -> None:
        self._result.clear()
        self._last_result = None
        self._copy_btn.setEnabled(False)
        self._dismiss_btn.setEnabled(False)
        self._apply_btn.setEnabled(False)

    def _copy_result(self) -> None:
        text = self._result.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self._status.setText("Copied")
