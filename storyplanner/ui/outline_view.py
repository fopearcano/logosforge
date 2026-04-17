"""Outline view — read-only narrative summary generated from project data."""

from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database
from storyplanner.export import export_outline_markdown


class OutlineView(QWidget):
    def __init__(self, db: Database, project_id: int) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Outline"))

        self._browser = QTextBrowser()
        self._browser.setOpenLinks(False)
        layout.addWidget(self._browser)

        self._export_btn = QPushButton("Export Outline")
        self._export_btn.clicked.connect(self._on_export)
        layout.addWidget(self._export_btn)

        self._render()

    def _on_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Outline",
            "",
            "Markdown (*.md)",
        )
        if not path:
            return
        if not path.endswith(".md"):
            path += ".md"

        content = export_outline_markdown(self._db, self._project_id)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        QMessageBox.information(self, "Export", f"Outline exported to {path}")

    def _render(self) -> None:
        project = self._db.get_project_by_id(self._project_id)
        characters = self._db.get_all_characters(self._project_id)
        places = self._db.get_all_places(self._project_id)
        scenes = self._db.get_all_scenes(self._project_id)

        char_name_by_id = {c.id: c.name for c in characters}
        place_name_by_id = {p.id: p.name for p in places}

        html_parts: list[str] = []

        # Project title
        title = project.title if project else "Untitled"
        html_parts.append(f"<h1>{_esc(title)}</h1>")

        if not scenes:
            html_parts.append("<p>No scenes to display.</p>")
            self._browser.setHtml("".join(html_parts))
            return

        # Group scenes by chapter, preserving order within each group
        chapter_groups: list[tuple[str, list]] = []
        current_chapter: str | None = None
        current_group: list = []

        for scene in scenes:
            chapter = scene.chapter if scene.chapter else ""
            if chapter != current_chapter:
                if current_group:
                    chapter_groups.append((current_chapter or "", current_group))
                current_chapter = chapter
                current_group = [scene]
            else:
                current_group.append(scene)
        if current_group:
            chapter_groups.append((current_chapter or "", current_group))

        scene_index = 0
        for chapter_name, group_scenes in chapter_groups:
            if chapter_name:
                html_parts.append(f"<h2>{_esc(chapter_name)}</h2>")
            else:
                html_parts.append("<h2>Uncategorized</h2>")

            for scene in group_scenes:
                scene_index += 1
                html_parts.append(
                    self._render_scene(
                        scene, scene_index, char_name_by_id, place_name_by_id
                    )
                )

        self._browser.setHtml("".join(html_parts))

    def _render_scene(
        self,
        scene,
        index: int,
        char_name_by_id: dict[int, str],
        place_name_by_id: dict[int, str],
    ) -> str:
        parts: list[str] = []
        parts.append(f"<h3>{index}. {_esc(scene.title)}</h3>")

        meta_lines: list[str] = []
        if scene.plotline:
            meta_lines.append(f"<b>Plotline:</b> {_esc(scene.plotline)}")

        char_ids = self._db.get_scene_character_ids(scene.id)
        char_names = [
            char_name_by_id[cid] for cid in char_ids if cid in char_name_by_id
        ]
        if char_names:
            meta_lines.append(
                f"<b>Characters:</b> {_esc(', '.join(char_names))}"
            )

        place_ids = self._db.get_scene_place_ids(scene.id)
        place_names = [
            place_name_by_id[pid] for pid in place_ids if pid in place_name_by_id
        ]
        if place_names:
            meta_lines.append(
                f"<b>Places:</b> {_esc(', '.join(place_names))}"
            )

        if meta_lines:
            parts.append("<p>" + "<br>".join(meta_lines) + "</p>")

        if scene.summary:
            parts.append(f"<p>{_esc(scene.summary)}</p>")

        if scene.synopsis:
            parts.append(f"<p><b>Synopsis:</b> {_esc(scene.synopsis)}</p>")

        gco: list[str] = []
        if scene.goal:
            gco.append(f"<b>Goal:</b> {_esc(scene.goal)}")
        if scene.conflict:
            gco.append(f"<b>Conflict:</b> {_esc(scene.conflict)}")
        if scene.outcome:
            gco.append(f"<b>Outcome:</b> {_esc(scene.outcome)}")
        if gco:
            parts.append("<p>" + "<br>".join(gco) + "</p>")

        return "".join(parts)


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
