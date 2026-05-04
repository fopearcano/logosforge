"""PSYKE Console — omnibox with live search dropdown and keyboard navigation."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

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
from storyplanner.psyke_intents import detect_intent, intent_to_command
from storyplanner.psyke_search import PsykeSearchIndex
from storyplanner.psyke_suggestions import Suggestion, suggest
from storyplanner.ui import theme

if TYPE_CHECKING:
    from storyplanner.psyke_command_registry import CommandRegistry

_OPACITY_IDLE = 0.4
_OPACITY_ACTIVE = 1.0
_FADE_MS = 150
_DEBOUNCE_MS = 100
_MAX_VISIBLE = 8

class _SuggestionItem(QWidget):
    """Single row in the results dropdown."""

    def __init__(self, suggestion: Suggestion, query: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("psykeResultItem")
        self.suggestion = suggestion
        self.setFixedHeight(32)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 10, 0)
        row.setSpacing(0)

        self._accent_bar = QWidget()
        self._accent_bar.setFixedWidth(3)
        self._accent_bar.setObjectName("psykeAccentBar")
        row.addWidget(self._accent_bar)

        icon_label = QLabel(suggestion.icon)
        icon_label.setObjectName("psykeResultIcon")
        icon_label.setFixedWidth(28)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(icon_label)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 2, 0, 2)
        text_col.setSpacing(0)

        name_label = QLabel(_highlight(suggestion.text, query))
        name_label.setObjectName("psykeResultName")
        text_col.addWidget(name_label)

        if suggestion.description:
            desc_label = QLabel(_esc(suggestion.description))
            desc_label.setObjectName("psykeResultDesc")
            text_col.addWidget(desc_label)

        row.addLayout(text_col, stretch=1)

        if suggestion.category in ("command", "entity_action"):
            badge = QLabel(suggestion.category.replace("_", " "))
            badge.setObjectName("psykeResultBadge")
            row.addWidget(badge)

        self._apply_idle_style()

    def set_selected(self, selected: bool) -> None:
        if selected:
            self.setStyleSheet(
                f"#psykeResultItem {{ background-color: {theme.SELECTION_BG}; }}"
                f"#psykeAccentBar {{ background-color: {theme.ACCENT}; }}"
            )
        else:
            self._apply_idle_style()

    def _apply_idle_style(self) -> None:
        self.setStyleSheet(
            "#psykeResultItem { background-color: transparent; }"
            "#psykeAccentBar { background-color: transparent; }"
        )


def _highlight(name: str, query: str) -> str:
    if not query:
        return name
    clean = query.lstrip("/")
    if not clean:
        return _esc(name)
    pattern = re.compile(re.escape(clean), re.IGNORECASE)
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

    item_activated = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("psykeResultsDropdown")
        self.setVisible(False)
        self._items: list[_SuggestionItem] = []
        self._selected_index: int = -1
        self._fade_out_connected: bool = False

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 4, 0, 4)
        self._layout.setSpacing(0)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setDuration(_FADE_MS)

        self._apply_style()

    def show_suggestions(self, suggestions: list[Suggestion], query: str) -> None:
        self._clear()
        self._selected_index = -1

        if not suggestions:
            empty = QLabel("No results")
            empty.setObjectName("psykeResultEmpty")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._layout.addWidget(empty)
            self._reveal()
            return

        for s in suggestions[:_MAX_VISIBLE]:
            item = _SuggestionItem(s, query)
            self._layout.addWidget(item)
            self._items.append(item)

        self._reveal()

    def hide_results(self) -> None:
        if not self.isVisible():
            return
        self._fade_anim.stop()
        self._fade_anim.setStartValue(self._opacity_effect.opacity())
        self._fade_anim.setEndValue(0.0)
        if not self._fade_out_connected:
            self._fade_anim.finished.connect(self._on_fade_out_done)
            self._fade_out_connected = True
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
            self.item_activated.emit(self._items[self._selected_index].suggestion)
            return True
        return False

    def has_selection(self) -> bool:
        return 0 <= self._selected_index < len(self._items)

    def has_items(self) -> bool:
        return len(self._items) > 0

    def _reveal(self) -> None:
        self.setVisible(True)
        self._fade_anim.stop()
        if self._fade_out_connected:
            self._fade_anim.finished.disconnect(self._on_fade_out_done)
            self._fade_out_connected = False
        self._fade_anim.setStartValue(self._opacity_effect.opacity())
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def _on_fade_out_done(self) -> None:
        self._fade_out_connected = False
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
            f"#psykeResultIcon {{"
            f"  font-size: 13px;"
            f"}}"
            f"#psykeResultName {{"
            f"  color: {theme.TEXT_PRIMARY};"
            f"  font-size: 12px;"
            f"  font-weight: 500;"
            f"}}"
            f"#psykeResultDesc {{"
            f"  color: {theme.TEXT_MUTED};"
            f"  font-size: 10px;"
            f"}}"
            f"#psykeResultBadge {{"
            f"  color: {theme.TEXT_MUTED};"
            f"  font-size: 9px;"
            f"  padding: 1px 6px;"
            f"  border: 1px solid {theme.BORDER};"
            f"  border-radius: 3px;"
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
        self._registry: CommandRegistry | None = None
        self._get_scene_entry_ids: Any = None
        self._index_dirty: bool = True

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

    def set_registry(self, registry: CommandRegistry) -> None:
        self._registry = registry

    def set_scene_context(self, getter: Any) -> None:
        self._get_scene_entry_ids = getter

    def _ensure_dropdown(self) -> _ResultsDropdown:
        if self._dropdown is None:
            win = self.window() or self
            self._dropdown = _ResultsDropdown(win)
            self._dropdown.item_activated.connect(self._on_suggestion_activated)
            self._dropdown_parent = win
        return self._dropdown

    def activate(self) -> None:
        from PySide6.QtWidgets import QApplication

        current = QApplication.focusWidget()
        if current is not None and current is not self._input:
            self._previous_focus = current
        self._input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._input.selectAll()

    def deactivate(self) -> None:
        self._selecting = True
        self._debounce.stop()
        self._last_query = ""
        self._input.clear()
        if self._dropdown is not None:
            self._dropdown.hide_results()
        if self._previous_focus is not None:
            self._previous_focus.setFocus(Qt.FocusReason.OtherFocusReason)
            self._previous_focus = None
        else:
            self.clearFocus()
        self._selecting = False

    def rebuild_index(self) -> None:
        self._search_index.rebuild()
        self._index_dirty = False

    def mark_index_dirty(self) -> None:
        self._index_dirty = True

    def _on_text_changed(self, text: str) -> None:
        if self._selecting:
            return
        if text.strip():
            self._debounce.start()
        else:
            self._debounce.stop()
            self._last_query = ""
            if self._dropdown is not None:
                self._dropdown.hide_results()

    def _run_search(self) -> None:
        if self._index_dirty:
            self._search_index.rebuild()
            self._index_dirty = False
            self._last_query = ""

        query = self._input.text().strip()
        if not query:
            self._ensure_dropdown().hide_results()
            return
        if query == self._last_query:
            return
        self._last_query = query

        scene_ids: set[int] | None = None
        if self._get_scene_entry_ids:
            scene_ids = self._get_scene_entry_ids()

        suggestions = suggest(
            query,
            self._search_index,
            registry=self._registry,
            scene_entry_ids=scene_ids,
            max_results=_MAX_VISIBLE,
        )
        dropdown = self._ensure_dropdown()
        dropdown.show_suggestions(suggestions, query)
        self._position_dropdown()

    def _position_dropdown(self) -> None:
        dropdown = self._ensure_dropdown()
        if not dropdown.isVisible():
            return
        win = self.window()
        if hasattr(self, "_dropdown_parent") and self._dropdown_parent is not win:
            dropdown.setParent(win)
            self._dropdown_parent = win
        dropdown.adjustSize()
        console_geo = self.geometry()
        mapped = self.mapTo(win, self.rect().topLeft())
        dw = console_geo.width()
        dh = dropdown.sizeHint().height()
        dropdown.setGeometry(mapped.x(), mapped.y() - dh, dw, dh)
        dropdown.raise_()
        dropdown.show()

    def _on_suggestion_activated(self, suggestion: Suggestion) -> None:
        if suggestion.category == "intent":
            parsed = parse_command(suggestion.text)
            if parsed.kind == CommandType.SYSTEM:
                self.command_submitted.emit(parsed.command, parsed.args)
                self.deactivate()
                return
            if parsed.kind == CommandType.ENTITY:
                resolved = self._search_index.resolve_entity(parsed.command)
                if resolved:
                    self.entry_selected.emit(resolved.entry_id, resolved.name)
                    self.deactivate()
                    return
            self.deactivate()
            return

        if suggestion.category in ("command", "nl_command"):
            text = suggestion.text.lstrip("/")
            parsed = parse_command("/" + text)
            if parsed.kind == CommandType.SYSTEM:
                self.command_submitted.emit(parsed.command, parsed.args)
                self.deactivate()
                return
            self._input.setText(suggestion.text)
            self._input.setCursorPosition(len(suggestion.text))
            self._last_query = ""
            self._debounce.start()
            return

        if suggestion.category in ("entity_action", "nl_action"):
            text = suggestion.text.lstrip("/")
            parts = text.split(None, 1)
            if len(parts) == 2:
                word_a, word_b = parts[0].lower(), parts[1]
                if word_a in ("insert", "mention", "use"):
                    resolved = self._search_index.resolve_entity(word_b)
                    if resolved:
                        self.entry_selected.emit(resolved.entry_id, resolved.name)
                        self.deactivate()
                        return
                if word_a in ("open", "show", "view"):
                    resolved = self._search_index.resolve_entity(word_b)
                    if resolved:
                        self.entry_open_requested.emit(resolved.entry_id)
                        self.deactivate()
                        return
                resolved = self._search_index.resolve_entity(word_a)
                if resolved:
                    action = word_b.lower()
                    if action == "open":
                        self.entry_open_requested.emit(resolved.entry_id)
                    else:
                        self.entry_selected.emit(resolved.entry_id, resolved.name)
                    self.deactivate()
                    return

        if suggestion.entry_id:
            entry = self._db.get_psyke_entry_by_id(suggestion.entry_id)
            if entry:
                self.entry_selected.emit(entry.id, entry.name)
                self.deactivate()
                return

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
                if self._index_dirty:
                    self._search_index.rebuild()
                    self._index_dirty = False
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

        return self._try_intent(text)

    def _try_intent(self, text: str) -> bool:
        intent = detect_intent(text, use_llm=True)
        if intent is None:
            return False
        cmd_str = intent_to_command(intent)
        if cmd_str is None:
            return False
        parsed = parse_command(cmd_str)
        if parsed.kind == CommandType.SYSTEM:
            self.command_submitted.emit(parsed.command, parsed.args)
            self.deactivate()
            return True
        if parsed.kind == CommandType.ENTITY:
            resolved = self._search_index.resolve_entity(parsed.command)
            if resolved:
                self.entry_selected.emit(resolved.entry_id, resolved.name)
                self.deactivate()
                return True
        return False

    def _maybe_hide_dropdown(self) -> None:
        if not self._input.hasFocus() and self._dropdown is not None:
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
