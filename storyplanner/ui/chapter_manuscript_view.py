"""Novel Manuscript — a chapter-flow writing surface.

The primary writing unit in Novel mode is the Chapter, so the Manuscript section
in Novel writes ``Chapter.content`` (never an outline summary/description). A
clean vertical flow: act headers → chapter title → body editor. Non-Novel modes
keep the scene-based WritingCoreView untouched.

Deliberately lean (no per-scene energy/voice tooling yet) to avoid retrofitting
the large scene editor; chapter bodies persist directly via the Chapter store.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database
from storyplanner.ui import theme


class _ChapterEditor(QTextEdit):
    """A chapter body editor that autosaves to Chapter.content (debounced)."""

    def __init__(self, chapter, on_changed: Callable[[int, str], None]) -> None:
        super().__init__()
        self.chapter_id = chapter.id
        self._on_changed = on_changed
        self.setPlaceholderText("Start writing…")
        self.setAcceptRichText(False)
        self.setMarkdown(chapter.content or "")
        self.setMinimumHeight(160)
        self.setStyleSheet(
            f"QTextEdit {{ background: {theme.BG_PANEL}; color: {theme.TEXT_PRIMARY};"
            f" border: 1px solid {theme.BORDER}; border-radius: 6px; padding: 8px; }}")
        self.textChanged.connect(self._fire)

    def _fire(self) -> None:
        self._on_changed(self.chapter_id, self.toMarkdown().rstrip())


class ChapterManuscriptView(QWidget):
    """Novel manuscript: write chapters (body = Chapter.content)."""

    def __init__(
        self,
        db: Database,
        project_id: int,
        on_data_changed: Callable[[], None] | None = None,
        on_content_saved: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._on_data_changed = on_data_changed
        self._on_content_saved = on_content_saved
        self._editors: dict[int, _ChapterEditor] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        bar = QHBoxLayout()
        bar.setSpacing(6)
        title = QLabel("Manuscript")
        title.setStyleSheet(
            f"color: {theme.TEXT_PRIMARY}; font-size: 14px; font-weight: 700;")
        bar.addWidget(title)
        self._add_btn = QPushButton("+ Chapter")
        self._add_btn.setStyleSheet(theme.primary_btn())
        self._add_btn.clicked.connect(self._add_chapter)
        bar.addWidget(self._add_btn)
        bar.addStretch()
        outer.addLayout(bar)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._inner = QWidget()
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(12, 8, 12, 24)
        self._inner_layout.setSpacing(10)
        self._inner_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._inner)
        outer.addWidget(self._scroll, stretch=1)

        self.refresh()

    # -- build --------------------------------------------------------------

    def add_button_text(self) -> str:
        return self._add_btn.text()

    def refresh(self) -> None:
        while self._inner_layout.count():
            item = self._inner_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._editors.clear()

        chapters = self._db.get_chapters(self._project_id)
        if not chapters:
            empty = QLabel("No chapters yet. Click “+ Chapter” to start writing.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 12px;")
            self._inner_layout.addWidget(empty)
            return

        current_act = object()  # sentinel so the first act always prints
        for ch in chapters:
            act = (ch.act or "").strip()
            if act != current_act:
                current_act = act
                if act:
                    hdr = QLabel(act.upper())
                    hdr.setStyleSheet(
                        f"color: {theme.TEXT_SECONDARY}; font-size: 11px;"
                        f" font-weight: 700;")
                    self._inner_layout.addWidget(hdr)
            t = QLabel(ch.title or "Untitled chapter")
            t.setStyleSheet(
                f"color: {theme.TEXT_PRIMARY}; font-size: 13px; font-weight: 700;")
            self._inner_layout.addWidget(t)
            editor = _ChapterEditor(ch, self._save_body)
            self._inner_layout.addWidget(editor)
            self._editors[ch.id] = editor

    # -- actions ------------------------------------------------------------

    def _add_chapter(self) -> None:
        n = self._db.get_chapters(self._project_id)
        self._db.create_chapter(self._project_id, title=f"Chapter {len(n) + 1}")
        self.refresh()
        if self._on_data_changed:
            self._on_data_changed()

    def _save_body(self, chapter_id: int, content: str) -> None:
        # Persist the chapter body directly; lightweight notify (no rebuild — the
        # editor already reflects the text, preserving the undo stack/cursor).
        self._db.update_chapter(chapter_id, content=content)
        if self._on_content_saved:
            self._on_content_saved()
