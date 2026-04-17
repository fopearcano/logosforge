"""Narrative Structure view — scenes organized by beat in story order."""

from PySide6.QtWidgets import (
    QLabel,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database

BEAT_ORDER = [
    "Opening Image",
    "Setup",
    "Catalyst",
    "Debate",
    "Break into Two",
    "Midpoint",
    "Bad Guys Close In",
    "All Is Lost",
    "Break into Three",
    "Finale",
    "Final Image",
]


class StructureView(QWidget):
    def __init__(self, db: Database, project_id: int) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Narrative Structure"))

        self._browser = QTextBrowser()
        self._browser.setOpenLinks(False)
        layout.addWidget(self._browser)

        self._render()

    def _render(self) -> None:
        scenes = self._db.get_all_scenes(self._project_id)

        beat_scenes: dict[str, list[tuple[int, str, str]]] = {}
        for i, scene in enumerate(scenes):
            beat = scene.beat if scene.beat else ""
            if beat:
                beat_scenes.setdefault(beat, []).append(
                    (i + 1, scene.title, scene.summary)
                )

        self._browser.setHtml(self._build_html(beat_scenes, len(scenes)))

    def _build_html(
        self,
        beat_scenes: dict[str, list[tuple[int, str, str]]],
        total: int,
    ) -> str:
        parts: list[str] = []

        if not beat_scenes:
            parts.append("<p>No beats assigned to any scenes.</p>")
            return "".join(parts)

        ordered_beats = [b for b in BEAT_ORDER if b in beat_scenes]
        custom_beats = sorted(b for b in beat_scenes if b not in BEAT_ORDER)
        ordered_beats.extend(custom_beats)

        assigned = sum(len(v) for v in beat_scenes.values())
        unassigned = total - assigned

        parts.append("<h2>Narrative Structure</h2>")

        for beat in ordered_beats:
            entries = beat_scenes[beat]
            parts.append(
                f"<h3 style='margin-bottom: 2px;'>{_esc(beat)}</h3>"
            )
            for idx, title, summary in entries:
                parts.append(
                    f"<p style='margin: 2px 0 2px 16px;'>"
                    f"<b>[{idx}]</b> {_esc(title)}"
                )
                if summary:
                    parts.append(
                        f"<br><span style='color: #9aa0a6;'>"
                        f"{_esc(summary)}</span>"
                    )
                parts.append("</p>")

        if unassigned > 0:
            parts.append(
                f"<p style='color: #6b7280; margin-top: 12px;'>"
                f"{unassigned} scene(s) without a beat.</p>"
            )

        return "".join(parts)


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
