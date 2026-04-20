"""PSYKE syntax highlighter and Ctrl+Click jump handler for the scene editor."""

from __future__ import annotations

import re

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import (
    QMouseEvent,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)
from PySide6.QtWidgets import QPlainTextEdit

from storyplanner.ui import theme


class PsykeHighlighter(QSyntaxHighlighter):
    """Highlights PSYKE entry names and aliases in the scene editor."""

    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self._pattern: re.Pattern | None = None
        self._fmt = QTextCharFormat()
        self._update_format()

    def _update_format(self) -> None:
        from PySide6.QtGui import QColor
        color = QColor(theme.get("ACCENT"))
        self._fmt = QTextCharFormat()
        self._fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)
        self._fmt.setUnderlineColor(color)
        self._fmt.setForeground(color)

    def refresh_patterns(self, terms: list[str]) -> None:
        self._update_format()
        if not terms:
            self._pattern = None
            self.rehighlight()
            return
        escaped = sorted((re.escape(t) for t in terms if t.strip()), key=len, reverse=True)
        if not escaped:
            self._pattern = None
            self.rehighlight()
            return
        self._pattern = re.compile(
            r"\b(?:" + "|".join(escaped) + r")\b",
            re.IGNORECASE,
        )
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        if self._pattern is None:
            return
        for match in self._pattern.finditer(text):
            self.setFormat(match.start(), match.end() - match.start(), self._fmt)


class PsykeClickHandler(QObject):
    """Event filter: Ctrl+Click on a highlighted PSYKE term jumps to that entry."""

    def __init__(
        self,
        editor: QPlainTextEdit,
        highlighter: PsykeHighlighter,
        on_jump: callable,
    ) -> None:
        super().__init__(editor)
        self._editor = editor
        self._highlighter = highlighter
        self._on_jump = on_jump
        self._term_to_entry_id: dict[str, int] = {}
        editor.viewport().installEventFilter(self)

    def set_term_map(self, term_map: dict[str, int]) -> None:
        self._term_to_entry_id = term_map

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() != QEvent.Type.MouseButtonRelease:
            return False
        mouse: QMouseEvent = event
        if not (mouse.modifiers() & Qt.KeyboardModifier.ControlModifier):
            return False
        if mouse.button() != Qt.MouseButton.LeftButton:
            return False

        pattern = self._highlighter._pattern
        if pattern is None:
            return False

        cursor = self._editor.cursorForPosition(mouse.pos())
        block = cursor.block()
        col = cursor.positionInBlock()
        text = block.text()

        for match in pattern.finditer(text):
            if match.start() <= col <= match.end():
                matched_text = match.group()
                entry_id = self._term_to_entry_id.get(matched_text.lower())
                if entry_id is not None:
                    self._on_jump(entry_id)
                    return True
        return False
