"""Story Dashboard — high-level narrative overview in one place."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from storyplanner.analytics import compute_project_stats
from storyplanner.context_builder import _count_scene_tags, gather_story_memory
from storyplanner.db import Database


class DashboardView(QWidget):
    def __init__(
        self,
        db: Database,
        project_id: int,
        on_navigate: Callable[[str, int], None] | None = None,
    ) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._on_navigate = on_navigate

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Story Dashboard")
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 8px;")
        outer.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._container)

        self._build()

    def refresh(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._build()

    def _build(self) -> None:
        self._add_writing_stats()
        self._add_act_distribution()
        self._add_beat_distribution()
        self._add_tag_summary()
        self._add_character_overview()
        self._add_story_memory()
        self._layout.addStretch()

    # -- Sections ------------------------------------------------------------

    def _add_section_header(self, text: str) -> None:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #9aa0a6; "
            "margin-top: 12px; margin-bottom: 4px; padding-left: 4px;"
        )
        self._layout.addWidget(lbl)

    def _add_section_body(self, text: str) -> None:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("padding-left: 8px; line-height: 1.4;")
        self._layout.addWidget(lbl)

    # -- Writing Stats -------------------------------------------------------

    def _add_writing_stats(self) -> None:
        self._add_section_header("Writing Stats")
        scenes = self._db.get_all_scenes(self._project_id)
        texts = [s.content for s in scenes if s.content]
        stats = compute_project_stats(texts)
        if stats["scene_count"] == 0:
            self._add_section_body("No scenes yet.")
            return
        lines = [
            f"  Scenes: {stats['scene_count']}",
            f"  Avg words/scene: {stats['avg_words']}",
            f"  Longest scene: {stats['longest']} words",
            f"  Shortest scene: {stats['shortest']} words",
        ]
        self._add_section_body("\n".join(lines))

    # -- Act Distribution ----------------------------------------------------

    def _add_act_distribution(self) -> None:
        self._add_section_header("Act Distribution")
        scenes = self._db.get_all_scenes(self._project_id)
        if not scenes:
            self._add_section_body("No scenes yet.")
            return

        acts: dict[str, list[int]] = {}
        for i, s in enumerate(scenes, 1):
            act = s.act or "(unassigned)"
            acts.setdefault(act, []).append(i)

        lines: list[str] = []
        for act, positions in acts.items():
            first, last = positions[0], positions[-1]
            rng = f"{first}" if first == last else f"{first}–{last}"
            lines.append(f"  {act}: {len(positions)} scenes (#{rng})")
        self._add_section_body("\n".join(lines))

    # -- Beat Distribution ---------------------------------------------------

    def _add_beat_distribution(self) -> None:
        self._add_section_header("Beat Distribution")
        scenes = self._db.get_all_scenes(self._project_id)

        beats: dict[str, int] = {}
        for s in scenes:
            if s.beat:
                beats[s.beat] = beats.get(s.beat, 0) + 1

        if not beats:
            self._add_section_body("No beats assigned.")
            return

        lines = [
            f"  {beat}: {count}" for beat, count in
            sorted(beats.items(), key=lambda kv: (-kv[1], kv[0]))
        ]
        self._add_section_body("\n".join(lines))

    # -- Tag / Theme Summary -------------------------------------------------

    def _add_tag_summary(self) -> None:
        self._add_section_header("Tag / Theme Summary")
        counts = _count_scene_tags(self._db, self._project_id)
        if not counts:
            self._add_section_body("No tags used.")
            return

        lines = [f"  {tag}: {n}" for tag, n in counts[:10]]
        self._add_section_body("\n".join(lines))

    # -- Character Overview --------------------------------------------------

    def _add_character_overview(self) -> None:
        self._add_section_header("Character Overview")
        characters = self._db.get_all_characters(self._project_id)
        if not characters:
            self._add_section_body("No characters yet.")
            return

        for char in characters:
            arc = self._db.get_character_arc(self._project_id, char.id)
            scene_count = len(arc)
            last_state = arc[-1][3] if arc else None

            row = QHBoxLayout()
            btn = QPushButton(char.name)
            btn.setFlat(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "text-align: left; color: #58a6ff; padding: 2px 4px;"
            )
            btn.clicked.connect(
                lambda checked, cid=char.id: self._navigate("Character", cid)
            )
            row.addWidget(btn)

            detail = f"{scene_count} scene{'s' if scene_count != 1 else ''}"
            if last_state:
                detail += f"  ·  last state: {last_state}"
            detail_lbl = QLabel(detail)
            detail_lbl.setStyleSheet("color: #8b949e; padding-left: 4px;")
            row.addWidget(detail_lbl)
            row.addStretch()
            self._layout.addLayout(row)

    # -- Story Memory --------------------------------------------------------

    def _add_story_memory(self) -> None:
        self._add_section_header("Global Story Memory")
        memory = gather_story_memory(self._db, self._project_id)
        if not memory:
            self._add_section_body("Not enough data to build story memory.")
            return

        display = QPlainTextEdit()
        display.setReadOnly(True)
        display.setPlainText(memory)
        display.setMaximumHeight(180)
        display.setStyleSheet(
            "QPlainTextEdit {"
            "  background-color: #12151a;"
            "  color: #d4d4d4;"
            "  border: 1px solid #2a2f36;"
            "  border-radius: 4px;"
            "  padding: 8px;"
            "}"
        )
        self._layout.addWidget(display)

    # -- Navigation ----------------------------------------------------------

    def _navigate(self, entity_type: str, entity_id: int) -> None:
        if self._on_navigate:
            self._on_navigate(entity_type, entity_id)
