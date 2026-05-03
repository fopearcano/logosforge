"""PSYKE Console — omnibox with live search dropdown and keyboard navigation."""

from __future__ import annotations

import re

from PySide6.QtCore import (
    QEvent,
    QPropertyAnimation,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database
from storyplanner.psyke_commands import CommandType, parse as parse_command
from storyplanner.psyke_search import PsykeSearchIndex, SearchResult
from storyplanner.ui import theme

_OPACITY_IDLE = 0.4
_OPACITY_ACTIVE = 1.0
_FADE_MS = 150
_DEBOUNCE_MS = 100
_MAX_VISIBLE = 8

_TYPE_ICONS = {
    "character": "\U0001F464",
    "place": "\U0001F3DB",
    "object": "\U0001F48E",
    "lore": "\U0001F4DC",
    "theme": "\U0001F3AD",
    "other": "\U0001F4CC",
}

_SELECTED_BG = "rgba(255,255,255,0.08)"


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

    def set_selected(self, selected: bool) -> None:
        bg = _SELECTED_BG if selected else "transparent"
        self.setStyleSheet(f"#psykeResultItem {{ background-color: {bg}; }}")


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

    item_selected = Signal(SearchResult)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("psykeResultsDropdown")
        self.setVisible(False)
        self._items: list[_ResultItem] = []
        self._selected_index: int = -1

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 4, 0, 4)
        self._layout.setSpacing(0)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setDuration(_FADE_MS)

    def show_results(self, results: list[SearchResult], query: str) -> None:
        self._clear()
        self._selected_index = -1

        if not results:
            empty = QLabel("No results")
            empty.setObjectName("psykeResultEmpty")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._layout.addWidget(empty)
            self._reveal()
            return

        for r in results[:_MAX_VISIBLE]:
            item = _ResultItem(r, query)
            self._layout.addWidget(item)
            self._items.append(item)

        self._reveal()

    def hide_results(self) -> None:
        if not self.isVisible():
            return
        self._fade_anim.stop()
        self._fade_anim.setStartValue(self._opacity_effect.opacity())
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.finished.connect(self._on_fade_out_done)
        self._fade_anim.start()

    def move_selection(self, delta: int) -> None:
        if not self._items:
            return
        old = self._selected_index
        new = self._selected_index + delta
        new = max(-1, min(new, len(self._items) - 1))
        if new == old:
            return
        if 0 <= old < len(self._items):
            self._items[old].set_selected(False)
        self._selected_index = new
        if 0 <= new < len(self._items):
            self._items[new].set_selected(True)

    def confirm_selection(self) -> bool:
        if 0 <= self._selected_index < len(self._items):
            self.item_selected.emit(self._items[self._selected_index].result)
            return True
        return False

    def has_selection(self) -> bool:
        return 0 <= self._selected_index < len(self._items)

    def has_items(self) -> bool:
        return len(self._items) > 0

    def _reveal(self) -> None:
        self._apply_style()
        self.setVisible(True)
        self._fade_anim.stop()
        try:
            self._fade_anim.finished.disconnect(self._on_fade_out_done)
        except RuntimeError:
            pass
        self._fade_anim.setStartValue(self._opacity_effect.opacity())
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def _on_fade_out_done(self) -> None:
        try:
            self._fade_anim.finished.disconnect(self._on_fade_out_done)
        except RuntimeError:
            pass
        self._clear()
        self._selected_index = -1
        self.setVisible(False)

    def _clear(self) -> None:
        self._items.clear()
        while self._layout.count():
            child = self._layout.takeAt(0)
            w = child.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

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
    """Slim search bar with live results dropdown and keyboard navigation."""

    entry_selected = Signal(int, str)
    entry_open_requested = Signal(int)
    command_submitted = Signal(str, list)

    def __init__(
        self,
        db: Database,
        project_id: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setObjectName("psykeConsole")

        self._db = db
        self._project_id = project_id
        self._previous_focus: QWidget | None = None
        self._search_index = PsykeSearchIndex(db, project_id)
        self._last_query: str = ""
        self._selecting: bool = False

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

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(_OPACITY_IDLE)
        self.setGraphicsEffect(self._opacity_effect)

        self._opacity_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._opacity_anim.setDuration(_FADE_MS)

        self._dropdown: _ResultsDropdown | None = None

        self._apply_style()

    def _ensure_dropdown(self) -> _ResultsDropdown:
        if self._dropdown is None:
            self._dropdown = _ResultsDropdown(self.window() if self.window() else self)
            self._dropdown.item_selected.connect(self._on_item_selected)
        return self._dropdown

    def activate(self) -> None:
        """Focus the console, remembering the previously focused widget."""
        from PySide6.QtWidgets import QApplication

        current = QApplication.focusWidget()
        if current is not None and current is not self._input:
            self._previous_focus = current
        self._input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._input.selectAll()

    def deactivate(self) -> None:
        """Blur the console and restore focus to the previous widget."""
        self._selecting = True
        self._debounce.stop()
        self._input.clear()
        dropdown = self._ensure_dropdown()
        dropdown.hide_results()
        if self._previous_focus is not None:
            self._previous_focus.setFocus(Qt.FocusReason.OtherFocusReason)
            self._previous_focus = None
        else:
            self.clearFocus()
        self._selecting = False

    def rebuild_index(self) -> None:
        self._search_index.rebuild()

    def _on_text_changed(self, text: str) -> None:
        if self._selecting:
            return
        if text.strip():
            self._debounce.start()
        else:
            self._debounce.stop()
            self._ensure_dropdown().hide_results()

    def _run_search(self) -> None:
        query = self._input.text().strip()
        if not query:
            self._ensure_dropdown().hide_results()
            return
        if query == self._last_query:
            return
        self._last_query = query
        results = self._search_index.search(query, max_results=_MAX_VISIBLE)
        dropdown = self._ensure_dropdown()
        dropdown.show_results(results, query)
        self._position_dropdown()

    def _position_dropdown(self) -> None:
        dropdown = self._ensure_dropdown()
        if not dropdown.isVisible():
            return
        dropdown.setParent(self.window())
        dropdown.adjustSize()
        console_geo = self.geometry()
        mapped = self.mapTo(self.window(), self.rect().topLeft())
        dw = console_geo.width()
        dh = dropdown.sizeHint().height()
        dropdown.setGeometry(mapped.x(), mapped.y() - dh, dw, dh)
        dropdown.raise_()
        dropdown.show()

    def _on_item_selected(self, result: SearchResult) -> None:
        self.entry_selected.emit(result.entry_id, result.name)
        self.deactivate()

    def _animate_opacity(self, target: float) -> None:
        self._opacity_anim.stop()
        self._opacity_anim.setStartValue(self._opacity_effect.opacity())
        self._opacity_anim.setEndValue(target)
        self._opacity_anim.start()

    def eventFilter(self, obj, event) -> bool:
        if obj is self._input:
            if event.type() == QEvent.Type.FocusIn:
                self._animate_opacity(_OPACITY_ACTIVE)
                self._search_index.rebuild()
            elif event.type() == QEvent.Type.FocusOut:
                self._animate_opacity(_OPACITY_IDLE)
                self._last_query = ""
                QTimer.singleShot(200, self._maybe_hide_dropdown)
            elif event.type() == QEvent.Type.KeyPress:
                key = event.key()
                if key == Qt.Key.Key_Escape:
                    self.deactivate()
                    return True
                dropdown = self._ensure_dropdown()
                if key == Qt.Key.Key_Down and dropdown.has_items():
                    dropdown.move_selection(1)
                    return True
                if key == Qt.Key.Key_Up and dropdown.has_items():
                    dropdown.move_selection(-1)
                    return True
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    if dropdown.confirm_selection():
                        return True
                    if self._try_execute_input():
                        return True
        return super().eventFilter(obj, event)

    def _try_execute_input(self) -> bool:
        text = self._input.text().strip()
        if not text:
            return False

        parsed = parse_command(text)

        if parsed.kind == CommandType.SYSTEM:
            self.command_submitted.emit(parsed.command, parsed.args)
            self.deactivate()
            return True

        if parsed.kind == CommandType.ENTITY:
            resolved = self._search_index.resolve_entity(parsed.command)
            if resolved is None:
                return False
            action = parsed.first_arg.lower() if parsed.first_arg else "insert"
            if action == "open":
                self.entry_open_requested.emit(resolved.entry_id)
            else:
                self.entry_selected.emit(resolved.entry_id, resolved.name)
            self.deactivate()
            return True

        return False

    def _maybe_hide_dropdown(self) -> None:
        if not self._input.hasFocus():
            self._ensure_dropdown().hide_results()

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
