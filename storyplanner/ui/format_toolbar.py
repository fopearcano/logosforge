"""Floating format toolbar — appears on text selection in the manuscript editor.

Provides quick-access formatting (bold, italic, heading, blockquote) and
emits signals for AI assistant actions (rewrite, expand, dialogue).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QWidget,
)

from storyplanner.ui import theme


class FormatToolbar(QWidget):
    """Compact floating toolbar for text formatting and AI action hooks."""

    ai_action = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("formatToolbar")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._active_editor: QTextEdit | None = None
        self._tracked: list[QTextEdit] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        bold_btn = self._make_btn("B", weight=QFont.Weight.Bold)
        bold_btn.setToolTip("Bold  (Ctrl+B)")
        bold_btn.clicked.connect(self._toggle_bold)
        layout.addWidget(bold_btn)

        italic_btn = self._make_btn("I", italic=True)
        italic_btn.setToolTip("Italic  (Ctrl+I)")
        italic_btn.clicked.connect(self._toggle_italic)
        layout.addWidget(italic_btn)

        heading_btn = self._make_btn("H")
        heading_btn.setToolTip("Cycle heading level")
        heading_btn.clicked.connect(self._cycle_heading)
        layout.addWidget(heading_btn)

        quote_btn = self._make_btn("❝")
        quote_btn.setToolTip("Toggle blockquote")
        quote_btn.clicked.connect(self._toggle_quote)
        layout.addWidget(quote_btn)

        sep = QWidget()
        sep.setFixedWidth(1)
        sep.setFixedHeight(16)
        sep.setObjectName("formatToolbarSep")
        layout.addWidget(sep)

        for label, key in (
            ("Rewrite", "rewrite"),
            ("Expand", "expand"),
            ("Dialogue", "dialogue"),
        ):
            btn = self._make_btn(label)
            btn.clicked.connect(lambda _, k=key: self.ai_action.emit(k))
            layout.addWidget(btn)

        self.hide()

    @staticmethod
    def _make_btn(
        text: str,
        weight: QFont.Weight = QFont.Weight.Normal,
        italic: bool = False,
    ) -> QPushButton:
        btn = QPushButton(text)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        font = btn.font()
        font.setWeight(weight)
        font.setItalic(italic)
        btn.setFont(font)
        return btn

    # -- Editor tracking ------------------------------------------------------

    def track_editor(self, editor: QTextEdit) -> None:
        if editor in self._tracked:
            return
        self._tracked.append(editor)
        editor.selectionChanged.connect(
            lambda e=editor: self._on_selection_changed(e),
        )

    def untrack_all(self) -> None:
        self._tracked.clear()
        self._active_editor = None
        self.hide()

    @property
    def active_editor(self) -> QTextEdit | None:
        return self._active_editor

    @property
    def selected_text(self) -> str:
        if not self._active_editor:
            return ""
        return (
            self._active_editor.textCursor()
            .selectedText()
            .replace(" ", "\n")
        )

    # -- Selection handling ---------------------------------------------------

    def _on_selection_changed(self, editor: QTextEdit) -> None:
        cursor = editor.textCursor()
        if cursor.hasSelection():
            self._active_editor = editor
            self._reposition(editor)
            self.show()
            self.raise_()
        elif editor is self._active_editor:
            self.hide()
            self._active_editor = None

    def _reposition(self, editor: QTextEdit) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        cursor = editor.textCursor()
        rect = editor.cursorRect(cursor)
        pos = editor.mapTo(parent, rect.topLeft())
        w = self.sizeHint().width()
        h = self.sizeHint().height()
        x = max(4, min(pos.x() - w // 2, parent.width() - w - 4))
        y = pos.y() - h - 6
        if y < 4:
            y = pos.y() + rect.height() + 6
        self.move(x, y)
        self.adjustSize()

    # -- Public format helpers (for keyboard shortcuts) -----------------------

    def toggle_bold_on(self, editor: QTextEdit | None = None) -> None:
        if editor is not None:
            self._active_editor = editor
        self._toggle_bold()

    def toggle_italic_on(self, editor: QTextEdit | None = None) -> None:
        if editor is not None:
            self._active_editor = editor
        self._toggle_italic()

    # -- Formatting actions ---------------------------------------------------

    def _toggle_bold(self) -> None:
        self._wrap_toggle("**")

    def _toggle_italic(self) -> None:
        self._wrap_toggle("*")

    def _wrap_toggle(self, marker: str) -> None:
        editor = self._active_editor
        if not editor:
            return
        cursor = editor.textCursor()
        text = cursor.selectedText().replace(" ", "\n")
        if not text:
            return

        ml = len(marker)
        doc = editor.toPlainText()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        before = doc[max(0, start - ml) : start]
        after = doc[end : end + ml]
        if before == marker and after == marker:
            cursor.setPosition(start - ml)
            cursor.setPosition(end + ml, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(text)
            cursor.setPosition(start - ml)
            cursor.setPosition(
                start - ml + len(text), QTextCursor.MoveMode.KeepAnchor,
            )
            editor.setTextCursor(cursor)
            return

        if (
            text.startswith(marker)
            and text.endswith(marker)
            and len(text) > 2 * ml
        ):
            inner = text[ml:-ml]
            cursor.insertText(inner)
            cursor.setPosition(start)
            cursor.setPosition(
                start + len(inner), QTextCursor.MoveMode.KeepAnchor,
            )
            editor.setTextCursor(cursor)
            return

        wrapped = f"{marker}{text}{marker}"
        cursor.insertText(wrapped)
        cursor.setPosition(start + ml)
        cursor.setPosition(
            start + ml + len(text), QTextCursor.MoveMode.KeepAnchor,
        )
        editor.setTextCursor(cursor)

    def _cycle_heading(self) -> None:
        editor = self._active_editor
        if not editor:
            return
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(
            QTextCursor.MoveOperation.EndOfBlock,
            QTextCursor.MoveMode.KeepAnchor,
        )
        line = cursor.selectedText()

        if line.startswith("### "):
            cursor.insertText(line[4:])
        elif line.startswith("## "):
            cursor.insertText("### " + line[3:])
        elif line.startswith("# "):
            cursor.insertText("## " + line[2:])
        else:
            cursor.insertText("# " + line)

    def _toggle_quote(self) -> None:
        editor = self._active_editor
        if not editor:
            return
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(
            QTextCursor.MoveOperation.EndOfBlock,
            QTextCursor.MoveMode.KeepAnchor,
        )
        line = cursor.selectedText()

        if line.startswith("> "):
            cursor.insertText(line[2:])
        else:
            cursor.insertText("> " + line)
