"""Projects view — browse, open, and create project files."""

import os
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from storyplanner import recent_projects
from storyplanner.ui import theme

USER_ROLE = Qt.ItemDataRole.UserRole

_CARD_STYLE = (
    f"QFrame#projCard {{ background: {theme.CARD_BG};"
    f" border: 1px solid {theme.BORDER}; border-radius: 4px; }}"
)

_PRIMARY_BTN_STYLE = (
    f"QPushButton {{"
    f"  background-color: {theme.SELECTION_BG};"
    f"  color: {theme.TEXT_PRIMARY};"
    f"  border: 1px solid {theme.ACCENT_DIM};"
    f"  border-radius: 3px; padding: 6px 18px;"
    f"  font-weight: bold;"
    f"}}"
    f"QPushButton:hover {{"
    f"  background-color: {theme.BG_HOVER};"
    f"  border-color: {theme.ACCENT};"
    f"}}"
)

_EYEBROW_STYLE = (
    f"color: {theme.TEXT_SECONDARY}; font-size: 11px;"
    f" letter-spacing: 1px; text-transform: uppercase;"
)


class ProjectsView(QWidget):
    """Browse recent and local project files."""

    def __init__(
        self,
        on_open_file: Callable[[str], None],
        on_save_as: Callable[[], None],
    ) -> None:
        super().__init__()
        self._on_open_file = on_open_file
        self._on_save_as = on_save_as

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(28, 24, 28, 24)
        self._layout.setSpacing(16)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._container)

        self._build()

    def _build(self) -> None:
        self._clear_layout()

        heading = QLabel("Projects")
        heading_font = QFont()
        heading_font.setBold(True)
        heading_font.setPointSize(heading_font.pointSize() + 4)
        heading.setFont(heading_font)
        heading.setStyleSheet(f"color: {theme.TEXT_PRIMARY};")
        self._layout.addWidget(heading)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        open_btn = QPushButton("Open Project\u2026")
        open_btn.setStyleSheet(_PRIMARY_BTN_STYLE)
        open_btn.clicked.connect(self._on_browse)
        btn_row.addWidget(open_btn)

        new_btn = QPushButton("Create New Project")
        new_btn.clicked.connect(self._on_save_as)
        btn_row.addWidget(new_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._build)
        btn_row.addWidget(refresh_btn)

        btn_row.addStretch()
        self._layout.addLayout(btn_row)

        recent_paths = recent_projects.load()

        if not recent_paths:
            self._add_empty_state()
            self._layout.addStretch()
            return

        self._add_section("Recent projects", recent_paths)
        self._layout.addStretch()

    def _add_section(self, title: str, paths: list[str]) -> None:
        label = QLabel(title)
        label.setStyleSheet(_EYEBROW_STYLE)
        self._layout.addWidget(label)

        for path in paths:
            card = self._make_project_card(path)
            self._layout.addWidget(card)

    def _make_project_card(self, path: str) -> QFrame:
        card = QFrame()
        card.setObjectName("projCard")
        card.setStyleSheet(_CARD_STYLE)

        row = QHBoxLayout(card)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(12)

        info = QVBoxLayout()
        info.setSpacing(2)

        name = QLabel(Path(path).name)
        name_font = QFont()
        name_font.setBold(True)
        name.setFont(name_font)
        name.setStyleSheet(f"color: {theme.TEXT_PRIMARY};")
        info.addWidget(name)

        short = self._shorten_path(path)
        loc = QLabel(short)
        loc.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 11px;"
        )
        loc.setWordWrap(True)
        info.addWidget(loc)

        mtime = self._get_mtime(path)
        if mtime:
            time_label = QLabel(mtime)
            time_label.setStyleSheet(
                f"color: {theme.TEXT_MUTED}; font-size: 11px;"
            )
            info.addWidget(time_label)

        row.addLayout(info, stretch=1)

        open_btn = QPushButton("Open")
        open_btn.setStyleSheet(_PRIMARY_BTN_STYLE)
        open_btn.clicked.connect(lambda _, p=path: self._on_open_file(p))
        row.addWidget(open_btn)

        return card

    def _add_empty_state(self) -> None:
        card = QFrame()
        card.setObjectName("projCard")
        card.setStyleSheet(_CARD_STYLE)

        inner = QVBoxLayout(card)
        inner.setContentsMargins(24, 22, 24, 22)
        inner.setSpacing(10)

        msg = QLabel("No projects found.")
        msg_font = QFont()
        msg_font.setBold(True)
        msg.setFont(msg_font)
        inner.addWidget(msg)

        body = QLabel(
            "Open an existing project file or create a new one to get started."
        )
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {theme.TEXT_SECONDARY};")
        inner.addWidget(body)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        open_btn = QPushButton("Open Project\u2026")
        open_btn.setStyleSheet(_PRIMARY_BTN_STYLE)
        open_btn.clicked.connect(self._on_browse)
        btn_row.addWidget(open_btn)

        new_btn = QPushButton("Create New Project")
        new_btn.clicked.connect(self._on_save_as)
        btn_row.addWidget(new_btn)

        btn_row.addStretch()
        inner.addLayout(btn_row)

        self._layout.addWidget(card)

    def _on_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "JSON (*.json)",
        )
        if path:
            self._on_open_file(path)

    @staticmethod
    def _shorten_path(path: str) -> str:
        home = str(Path.home())
        if path.startswith(home):
            return "~" + path[len(home):]
        return path

    @staticmethod
    def _get_mtime(path: str) -> str | None:
        try:
            stat = os.stat(path)
            from datetime import datetime, timezone
            dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            return f"Modified {dt.strftime('%b %d, %Y %H:%M')}"
        except OSError:
            return None

    def _clear_layout(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            else:
                sub = item.layout()
                if sub is not None:
                    self._drop_layout(sub)

    def _drop_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout() is not None:
                self._drop_layout(item.layout())
