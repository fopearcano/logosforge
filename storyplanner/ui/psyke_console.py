"""PSYKE Console — omnibox with live search dropdown."""

from __future__ import annotations

import re

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database
from storyplanner.psyke_search import PsykeSearchIndex, SearchResult
from storyplanner.ui import theme

_OPACITY_IDLE = 0.4
_OPACITY_ACTIVE = 1.0
_DEBOUNCE_MS = 120
_MAX_VISIBLE = 8

_TYPE_ICONS = {
    "character": "\U0001F464",
    "place": "\U0001F3DB",
    "object": "\U0001F48E",
    "lore": "\U0001F4DC",
    "theme": "\U0001F3AD",
    "other": "\U0001F4CC",
}


class _ResultItem(QWidget):
    """Single row in the results dropdown."""

    def __init__(self, result: SearchResult, query: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("psykeResultItem")
        self.result = result

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)

        icon = _TYPE_ICONS.get(result.entry_type, "\U0001F4CC")
        icon_label = QLabel(icon)
        icon_label.setFixedWidth(20)
        layout.addWidget(icon_label)

        name_label = QLabel(_highlight(result.name, query))
        name_label.setObjectName("psykeResultName")
        layout.addWidget(name_label, stretch=1)

        type_label = QLabel(result.entry_type)
        type_label.setObjectName("psykeResultType")
        layout.addWidget(type_label)


def _highlight(name: str, query: str) -> str:
    """Wrap matched substring in bold tags."""
    if not query:
        return name
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    match = pattern.search(name)
    if match:
        s, e = match.start(), match.end()
        return (
            f"{_esc(name[:s])}"
            f"<b style='color: {theme.ACCENT};'>{_esc(name[s:e])}</b>"
            f"{_esc(name[e:])}"
        )
    return _esc(name)


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class _ResultsDropdown(QWidget):
    """Popup list that appears above the console."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("psykeResultsDropdown")
        self.setVisible(False)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 4, 0, 4)
        self._layout.setSpacing(0)

    def show_results(self, results: list[SearchResult], query: str) -> None:
        self._clear()

        if not results:
            empty = QLabel("No results")
            empty.setObjectName("psykeResultEmpty")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._layout.addWidget(empty)
            self.setVisible(True)
            self._apply_style()
            return

        for r in results[:_MAX_VISIBLE]:
            item = _ResultItem(r, query)
            self._layout.addWidget(item)

        self.setVisible(True)
        self._apply_style()

    def hide_results(self) -> None:
        self._clear()
        self.setVisible(False)

    def _clear(self) -> None:
        while self._layout.count():
            child = self._layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            f"#psykeResultsDropdown {{"
            f"  background-color: {theme.BG_PANEL};"
            f"  border: 1px solid {theme.BORDER};"
            f"  border-bottom: none;"
            f"  border-radius: 4px 4px 0 0;"
            f"}}"
            f"#psykeResultItem {{"
            f"  background-color: transparent;"
            f"  padding: 2px 0;"
            f"}}"
            f"#psykeResultItem:hover {{"
            f"  background-color: rgba(255,255,255,0.05);"
            f"}}"
            f"#psykeResultName {{"
            f"  color: {theme.TEXT_PRIMARY};"
            f"  font-size: 12px;"
            f"}}"
            f"#psykeResultType {{"
            f"  color: {theme.TEXT_MUTED};"
            f"  font-size: 10px;"
            f"  font-style: italic;"
            f"}}"
            f"#psykeResultEmpty {{"
            f"  color: {theme.TEXT_MUTED};"
            f"  font-size: 11px;"
            f"  padding: 8px;"
            f"}}"
        )


class PsykeConsole(QWidget):
    """Slim search bar with live results dropdown."""

    def __init__(
        self,
        db: Database,
        project_id: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setObjectName("psykeConsole")

        self._previous_focus: QWidget | None = None
        self._search_index = PsykeSearchIndex(db, project_id)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._run_search)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(0)

        self._input = QLineEdit()
        self._input.setPlaceholderText("\U0001F4D6  Search PSYKE…")
        self._input.setObjectName("psykeConsoleInput")
        self._input.setClearButtonEnabled(True)
        self._input.installEventFilter(self)
        self._input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._input)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(_OPACITY_IDLE)
        self.setGraphicsEffect(self._opacity)

        self._dropdown = _ResultsDropdown(self.window() if self.window() else self)

        self._apply_style()

    def activate(self) -> None:
        """Focus the console, remembering the previously focused widget."""
        from PySide6.QtWidgets import QApplication
        current = QApplication.focusWidget()
        if current is not None and current is not self._input:
            self._previous_focus = current
        self._search_index.rebuild()
        self._input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._input.selectAll()

    def deactivate(self) -> None:
        """Blur the console and restore focus to the previous widget."""
        self._input.clear()
        self._dropdown.hide_results()
        if self._previous_focus is not None:
            self._previous_focus.setFocus(Qt.FocusReason.OtherFocusReason)
            self._previous_focus = None
        else:
            self.clearFocus()

    def rebuild_index(self) -> None:
        self._search_index.rebuild()

    def _on_text_changed(self, text: str) -> None:
        if text.strip():
            self._debounce.start()
        else:
            self._debounce.stop()
            self._dropdown.hide_results()

    def _run_search(self) -> None:
        query = self._input.text().strip()
        if not query:
            self._dropdown.hide_results()
            return
        results = self._search_index.search(query, max_results=_MAX_VISIBLE)
        self._dropdown.show_results(results, query)
        self._position_dropdown()

    def _position_dropdown(self) -> None:
        if not self._dropdown.isVisible():
            return
        self._dropdown.setParent(self.window())
        self._dropdown.adjustSize()
        console_geo = self.geometry()
        mapped = self.mapTo(self.window(), self.rect().topLeft())
        dw = console_geo.width()
        dh = self._dropdown.sizeHint().height()
        self._dropdown.setGeometry(mapped.x(), mapped.y() - dh, dw, dh)
        self._dropdown.raise_()
        self._dropdown.show()

    def eventFilter(self, obj, event) -> bool:
        if obj is self._input:
            if event.type() == QEvent.Type.FocusIn:
                self._opacity.setOpacity(_OPACITY_ACTIVE)
            elif event.type() == QEvent.Type.FocusOut:
                self._opacity.setOpacity(_OPACITY_IDLE)
                QTimer.singleShot(150, self._maybe_hide_dropdown)
            elif event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Escape:
                    self.deactivate()
                    return True
        return super().eventFilter(obj, event)

    def _maybe_hide_dropdown(self) -> None:
        if not self._input.hasFocus():
            self._dropdown.hide_results()

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
