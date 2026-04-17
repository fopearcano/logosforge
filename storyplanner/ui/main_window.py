"""Main window with a sidebar and content area."""

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database
from storyplanner.export import export_csv_scenes, export_json, export_markdown
from storyplanner.import_data import import_json, validate_import_data
from storyplanner.ui.characters_view import CharactersView
from storyplanner.ui.notes_view import NotesView
from storyplanner.ui.places_view import PlacesView
from storyplanner.ui.scenes_view import ScenesView
from storyplanner.ui.timeline_view import TimelineView


class MainWindow(QMainWindow):
    def __init__(self, db: Database, project_id: int) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self.setWindowTitle("StoryPlanner")
        self.resize(900, 600)

        central = QWidget()
        root_layout = QHBoxLayout(central)

        # -- Left sidebar ----------------------------------------------------
        sidebar = QWidget()
        sidebar.setFixedWidth(160)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)

        self.sidebar_buttons: dict[str, QPushButton] = {}
        for label in ("Projects", "Characters", "Places", "Notes", "Scenes", "Timeline"):
            btn = QPushButton(label)
            sidebar_layout.addWidget(btn)
            self.sidebar_buttons[label] = btn

        # Push buttons to the top
        sidebar_layout.addStretch()

        # Import / Export buttons at bottom of sidebar
        self._import_btn = QPushButton("Import")
        sidebar_layout.addWidget(self._import_btn)
        self._import_btn.clicked.connect(self._on_import)

        self._export_btn = QPushButton("Export")
        sidebar_layout.addWidget(self._export_btn)
        self._export_btn.clicked.connect(self._on_export)

        # Connect sidebar buttons
        self.sidebar_buttons["Characters"].clicked.connect(self._show_characters)
        self.sidebar_buttons["Places"].clicked.connect(self._show_places)
        self.sidebar_buttons["Notes"].clicked.connect(self._show_notes)
        self.sidebar_buttons["Scenes"].clicked.connect(self._show_scenes)
        self.sidebar_buttons["Timeline"].clicked.connect(self._show_timeline)

        # -- Right content area ----------------------------------------------
        self.content_area = QWidget()
        QVBoxLayout(self.content_area).addWidget(
            QLabel("Select a section from the sidebar")
        )

        # -- Assemble --------------------------------------------------------
        root_layout.addWidget(sidebar)
        root_layout.addWidget(self.content_area, stretch=1)

        self.setCentralWidget(central)

    def _set_content(self, widget: QWidget) -> None:
        """Replace the content area with a new widget."""
        layout = self.centralWidget().layout()
        layout.replaceWidget(self.content_area, widget)
        self.content_area.deleteLater()
        self.content_area = widget

    def _show_characters(self) -> None:
        self._set_content(CharactersView(self._db, self._project_id))

    def _show_places(self) -> None:
        self._set_content(PlacesView(self._db, self._project_id))

    def _show_notes(self) -> None:
        self._set_content(NotesView(self._db, self._project_id))

    def _show_scenes(self) -> None:
        self._set_content(ScenesView(self._db, self._project_id))

    def _show_timeline(self) -> None:
        self._set_content(
            TimelineView(
                self._db,
                self._project_id,
                on_scene_selected=self._open_scene_in_editor,
            )
        )

    def _open_scene_in_editor(self, scene_id: int) -> None:
        view = ScenesView(self._db, self._project_id)
        self._set_content(view)
        view.select_scene(scene_id)

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Project",
            "",
            "JSON (*.json)",
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
        except OSError as e:
            QMessageBox.warning(self, "Import", f"Could not read file:\n{e}")
            return

        data, error = validate_import_data(raw)
        if data is None:
            QMessageBox.warning(self, "Import", error)
            return

        new_project_id = import_json(self._db, data)
        self._project_id = new_project_id

        self._set_content(QWidget())
        QVBoxLayout(self.content_area).addWidget(
            QLabel("Import complete. Select a section from the sidebar.")
        )
        QMessageBox.information(
            self, "Import", f"Project imported successfully (ID {new_project_id})."
        )

    def _on_export(self) -> None:
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Project",
            "",
            "JSON (*.json);;Markdown (*.md);;CSV – Scenes (*.csv)",
        )
        if not path:
            return

        if path.endswith(".csv") or "CSV" in selected_filter:
            content = export_csv_scenes(self._db, self._project_id)
            if not path.endswith(".csv"):
                path += ".csv"
        elif path.endswith(".md") or "Markdown" in selected_filter:
            content = export_markdown(self._db, self._project_id)
            if not path.endswith(".md"):
                path += ".md"
        else:
            content = export_json(self._db, self._project_id)
            if not path.endswith(".json"):
                path += ".json"

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        QMessageBox.information(self, "Export", f"Exported to {path}")
