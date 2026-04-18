"""Tag Analysis view — summary and distribution of thematic tags across scenes."""

from PySide6.QtWidgets import (
    QLabel,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database
from storyplanner.ui import theme


class TagAnalysisView(QWidget):
    def __init__(self, db: Database, project_id: int) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Tag Analysis"))

        self._browser = QTextBrowser()
        self._browser.setOpenLinks(False)
        layout.addWidget(self._browser)

        self._render()

    def _render(self) -> None:
        scenes = self._db.get_all_scenes(self._project_id)

        tag_scenes: dict[str, list[tuple[int, str]]] = {}
        tagged_count = 0

        for i, scene in enumerate(scenes):
            if not scene.tags:
                continue
            tagged_count += 1
            for raw_tag in scene.tags.split(","):
                tag = raw_tag.strip()
                if tag:
                    tag_scenes.setdefault(tag, []).append((i + 1, scene.title))

        html = self._build_html(tag_scenes, len(scenes), tagged_count)
        self._browser.setHtml(html)

    def _build_html(
        self,
        tag_scenes: dict[str, list[tuple[int, str]]],
        total_scenes: int,
        tagged_count: int,
    ) -> str:
        parts: list[str] = []

        if not tag_scenes:
            parts.append("<p>No tags assigned to any scenes.</p>")
            return "".join(parts)

        sorted_tags = sorted(tag_scenes.keys())

        # -- Summary table --
        parts.append("<h2>Tag Summary</h2>")
        parts.append(
            "<table cellpadding='4' cellspacing='0' style='border-collapse: collapse;'>"
        )
        parts.append(
            "<tr style='border-bottom: 2px solid {theme.BORDER};'>"
            "<th align='left'>Tag</th>"
            "<th align='right'>Scenes</th>"
            "</tr>"
        )
        for tag in sorted_tags:
            count = len(tag_scenes[tag])
            parts.append(
                f"<tr style='border-bottom: 1px solid {theme.BORDER};'>"
                f"<td>{_esc(tag)}</td>"
                f"<td align='right'>{count}</td>"
                f"</tr>"
            )
        parts.append(
            f"<tr style='border-top: 2px solid {theme.BORDER};'>"
            f"<td><b>Unique tags</b></td>"
            f"<td align='right'><b>{len(sorted_tags)}</b></td>"
            f"</tr>"
        )
        parts.append("</table>")

        untagged = total_scenes - tagged_count
        if untagged > 0:
            parts.append(
                f"<p style='color: {theme.TEXT_MUTED};'>"
                f"{untagged} scene(s) without tags.</p>"
            )

        # -- Details per tag --
        parts.append("<h2>Tag Details</h2>")
        for tag in sorted_tags:
            scenes = tag_scenes[tag]
            parts.append(f"<h3>{_esc(tag)}</h3>")
            parts.append("<ul style='margin-top: 2px;'>")
            for index, title in scenes:
                parts.append(f"<li>#{index} — {_esc(title)}</li>")
            parts.append("</ul>")

        return "".join(parts)


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
