"""Story Dashboard — project overview and entry points to current work."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from storyplanner import preferences
from storyplanner.analytics import compute_scene_stats
from storyplanner.db import Database
from storyplanner.ui import theme


_PRIMARY_BTN_STYLE = (
    f"QPushButton {{"
    f"  background-color: {theme.SELECTION_BG};"
    f"  color: {theme.TEXT_PRIMARY};"
    f"  border: 1px solid {theme.ACCENT_DIM};"
    f"  border-radius: 3px; padding: 6px 22px;"
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

_CARD_STYLE = (
    f"QFrame#dashCard {{ background: {theme.CARD_BG};"
    f" border: 1px solid {theme.BORDER}; border-radius: 4px; }}"
)


class DashboardView(QWidget):
    def __init__(
        self,
        db: Database,
        project_id: int,
        on_navigate: Callable[[str, int], None] | None = None,
        on_open_section: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._on_navigate = on_navigate
        self._on_open_section = on_open_section

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
        self._layout.setSpacing(20)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._container)

        self._build()

    def refresh(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            else:
                sublayout = item.layout()
                if sublayout is not None:
                    self._drop_layout(sublayout)
        self._build()

    def _drop_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout() is not None:
                self._drop_layout(item.layout())

    # -- Build ---------------------------------------------------------------

    def _build(self) -> None:
        project = self._db.get_project_by_id(self._project_id)
        scenes = self._db.get_all_scenes(self._project_id)

        self._add_header(project)

        if not scenes:
            self._add_empty_state()
            self._layout.addStretch()
            return

        self._add_progress(scenes)
        self._add_current_work(scenes)
        if (
            len(scenes) >= 3
            and not preferences.get_flag("has_seen_timeline_hint")
        ):
            self._add_timeline_hint()
        self._add_quick_actions()
        self._add_stats(scenes)
        self._layout.addStretch()

    def _add_timeline_hint(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(8)
        tip = QLabel("Tip: open the Timeline to see your story arc.")
        tip.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 12px;"
        )
        row.addWidget(tip)
        link = QPushButton("Open Timeline")
        link.setFlat(True)
        link.setStyleSheet(
            f"QPushButton {{ color: {theme.LINK_COLOR};"
            f" border: none; padding: 0 4px; font-size: 12px; }}"
            f"QPushButton:hover {{ color: {theme.TEXT_PRIMARY}; }}"
        )
        link.clicked.connect(lambda: self._open_section("timeline"))
        row.addWidget(link)
        row.addStretch()
        self._layout.addLayout(row)

    # -- Header --------------------------------------------------------------

    def _add_header(self, project) -> None:
        box = QVBoxLayout()
        box.setSpacing(2)

        title_text = project.title if project else "Untitled Project"
        title = QLabel(title_text)
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 6)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {theme.TEXT_PRIMARY};")
        box.addWidget(title)

        if project and project.updated_at:
            subtitle = QLabel(
                f"Last edited {project.updated_at.strftime('%b %d, %Y')}"
            )
            subtitle.setStyleSheet(
                f"color: {theme.TEXT_SECONDARY}; font-size: 12px;"
            )
            box.addWidget(subtitle)

        self._layout.addLayout(box)

    # -- Empty state ---------------------------------------------------------

    def _add_empty_state(self) -> None:
        card = self._make_card()
        inner = QVBoxLayout(card)
        inner.setContentsMargins(24, 22, 24, 22)
        inner.setSpacing(10)

        heading = QLabel("Your story starts here")
        heading_font = QFont()
        heading_font.setBold(True)
        heading_font.setPointSize(heading_font.pointSize() + 2)
        heading.setFont(heading_font)
        inner.addWidget(heading)

        body = QLabel(
            "No scenes yet. Create your first scene to begin outlining and writing."
        )
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {theme.TEXT_SECONDARY};")
        inner.addWidget(body)

        btn = QPushButton("Create Scene")
        btn.setStyleSheet(_PRIMARY_BTN_STYLE)
        btn.clicked.connect(lambda: self._open_section("scenes"))

        btn_row = QHBoxLayout()
        btn_row.addWidget(btn)
        btn_row.addStretch()
        inner.addLayout(btn_row)

        self._layout.addWidget(card)

    # -- Progress ------------------------------------------------------------

    def _add_progress(self, scenes) -> None:
        chapters = {s.chapter for s in scenes if s.chapter}
        latest = max(scenes, key=lambda s: s.created_at)
        position = next(
            (i for i, s in enumerate(scenes, 1) if s.id == latest.id), 0
        )

        row = QHBoxLayout()
        row.setSpacing(32)
        row.addLayout(self._stat_block("Scenes", str(len(scenes))))
        row.addLayout(self._stat_block("Chapters", str(len(chapters))))
        if position:
            row.addLayout(
                self._stat_block(
                    "Current position", f"#{position} of {len(scenes)}"
                )
            )
        row.addStretch()
        self._layout.addLayout(row)

    def _stat_block(self, label: str, value: str) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(1)

        value_label = QLabel(value)
        value_font = QFont()
        value_font.setBold(True)
        value_font.setPointSize(value_font.pointSize() + 4)
        value_label.setFont(value_font)
        value_label.setStyleSheet(f"color: {theme.TEXT_PRIMARY};")

        label_label = QLabel(label)
        label_label.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 11px;"
        )

        box.addWidget(value_label)
        box.addWidget(label_label)
        return box

    # -- Current work --------------------------------------------------------

    def _add_current_work(self, scenes) -> None:
        latest = max(scenes, key=lambda s: s.created_at)

        card = self._make_card()
        inner = QVBoxLayout(card)
        inner.setContentsMargins(20, 16, 20, 16)
        inner.setSpacing(8)

        eyebrow = QLabel("Continue writing")
        eyebrow.setStyleSheet(_EYEBROW_STYLE)
        inner.addWidget(eyebrow)

        title = QLabel(latest.title or "Untitled scene")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 3)
        title.setFont(title_font)
        title.setWordWrap(True)
        inner.addWidget(title)

        if latest.chapter:
            meta = QLabel(latest.chapter)
            meta.setStyleSheet(
                f"color: {theme.TEXT_SECONDARY}; font-size: 12px;"
            )
            inner.addWidget(meta)

        btn = QPushButton("Open Scene")
        btn.setStyleSheet(_PRIMARY_BTN_STYLE)
        btn.clicked.connect(lambda: self._navigate("Scene", latest.id))

        btn_row = QHBoxLayout()
        btn_row.addWidget(btn)
        btn_row.addStretch()
        inner.addLayout(btn_row)

        self._layout.addWidget(card)

    # -- Quick actions -------------------------------------------------------

    def _add_quick_actions(self) -> None:
        header = QLabel("Quick actions")
        header.setStyleSheet(_EYEBROW_STYLE)
        self._layout.addWidget(header)

        row = QHBoxLayout()
        row.setSpacing(8)
        for label, target in (
            ("New Scene", "scenes"),
            ("New Character", "characters"),
            ("Open Timeline", "timeline"),
        ):
            btn = QPushButton(label)
            btn.clicked.connect(
                lambda _=False, t=target: self._open_section(t)
            )
            row.addWidget(btn)
        row.addStretch()
        self._layout.addLayout(row)

    # -- Stats ---------------------------------------------------------------

    def _add_stats(self, scenes) -> None:
        header = QLabel("Stats")
        header.setStyleSheet(_EYEBROW_STYLE)
        self._layout.addWidget(header)

        total_words = sum(len((s.content or "").split()) for s in scenes)
        texts = [s.content for s in scenes if s.content and s.content.strip()]
        if texts:
            ratios = [compute_scene_stats(t)["dialogue_ratio"] for t in texts]
            dialogue_pct = round(100 * sum(ratios) / len(ratios))
        else:
            dialogue_pct = None

        rows = [
            ("Total words", f"{total_words:,}"),
            ("Scenes", str(len(scenes))),
        ]
        if dialogue_pct is not None:
            rows.append(("Dialogue", f"{dialogue_pct}%"))

        for label, value in rows:
            line = QHBoxLayout()
            line.setSpacing(12)
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {theme.TEXT_SECONDARY};")
            lbl.setMinimumWidth(120)
            val = QLabel(value)
            val.setStyleSheet(f"color: {theme.TEXT_PRIMARY};")
            line.addWidget(lbl)
            line.addWidget(val)
            line.addStretch()
            self._layout.addLayout(line)

    # -- Helpers -------------------------------------------------------------

    def _make_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("dashCard")
        card.setStyleSheet(_CARD_STYLE)
        return card

    def _navigate(self, entity_type: str, entity_id: int) -> None:
        if self._on_navigate:
            self._on_navigate(entity_type, entity_id)

    def _open_section(self, name: str) -> None:
        if self._on_open_section:
            self._on_open_section(name)
