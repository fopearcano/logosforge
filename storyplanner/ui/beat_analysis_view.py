"""Beat Analysis view — summary and positioning of narrative beats."""

from PySide6.QtWidgets import (
    QLabel,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database


class BeatAnalysisView(QWidget):
    def __init__(self, db: Database, project_id: int) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Beat Analysis"))

        self._browser = QTextBrowser()
        self._browser.setOpenLinks(False)
        layout.addWidget(self._browser)

        self._render()

    def _render(self) -> None:
        scenes = self._db.get_all_scenes(self._project_id)

        beat_counts: dict[str, int] = {}
        beat_positions: list[tuple[int, str, str]] = []

        for i, scene in enumerate(scenes):
            if scene.beat:
                beat_counts[scene.beat] = beat_counts.get(scene.beat, 0) + 1
                beat_positions.append((i + 1, scene.title, scene.beat))

        html = self._build_html(beat_counts, beat_positions, len(scenes))
        self._browser.setHtml(html)

    def _build_html(
        self,
        beat_counts: dict[str, int],
        beat_positions: list[tuple[int, str, str]],
        total_scenes: int,
    ) -> str:
        parts: list[str] = []

        if not beat_positions:
            parts.append("<p>No beats assigned to any scenes.</p>")
            return "".join(parts)

        # -- Summary table --
        parts.append("<h2>Beat Summary</h2>")
        parts.append(
            "<table cellpadding='4' cellspacing='0' style='border-collapse: collapse;'>"
        )
        parts.append(
            "<tr style='border-bottom: 2px solid #2a2f36;'>"
            "<th align='left'>Beat</th>"
            "<th align='right'>Count</th>"
            "</tr>"
        )
        for beat, count in sorted(beat_counts.items()):
            parts.append(
                f"<tr style='border-bottom: 1px solid #1a1e24;'>"
                f"<td>{_esc(beat)}</td>"
                f"<td align='right'>{count}</td>"
                f"</tr>"
            )
        assigned = len(beat_positions)
        unassigned = total_scenes - assigned
        parts.append(
            f"<tr style='border-top: 2px solid #2a2f36;'>"
            f"<td><b>Total assigned</b></td>"
            f"<td align='right'><b>{assigned} / {total_scenes}</b></td>"
            f"</tr>"
        )
        parts.append("</table>")

        if unassigned > 0:
            parts.append(
                f"<p style='color: #6b7280;'>"
                f"{unassigned} scene(s) without a beat.</p>"
            )

        # -- Positions list --
        parts.append("<h2>Beat Positions</h2>")
        parts.append(
            "<table cellpadding='4' cellspacing='0' style='border-collapse: collapse;'>"
        )
        parts.append(
            "<tr style='border-bottom: 2px solid #2a2f36;'>"
            "<th align='left'>#</th>"
            "<th align='left'>Scene</th>"
            "<th align='left'>Beat</th>"
            "</tr>"
        )
        for index, title, beat in beat_positions:
            parts.append(
                f"<tr style='border-bottom: 1px solid #1a1e24;'>"
                f"<td>{index}</td>"
                f"<td>{_esc(title)}</td>"
                f"<td>{_esc(beat)}</td>"
                f"</tr>"
            )
        parts.append("</table>")

        return "".join(parts)


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
