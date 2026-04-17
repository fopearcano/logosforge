"""Main window with a sidebar and content area."""

from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from storyplanner import recent_projects
from storyplanner.db import Database
from storyplanner.export import export_csv_scenes, export_json, export_markdown, export_screenplay
from storyplanner.import_data import import_json, validate_import_data
from storyplanner.ui.act_analysis_view import ActAnalysisView
from storyplanner.ui.beat_analysis_view import BeatAnalysisView
from storyplanner.ui.character_arc_view import CharacterArcView
from storyplanner.ui.characters_view import CharactersView
from storyplanner.ui.graph_view import GraphView
from storyplanner.ui.notes_view import NotesView
from storyplanner.ui.outline_view import OutlineView
from storyplanner.ui.places_view import PlacesView
from storyplanner.ui.scenes_view import ScenesView
from storyplanner.ui.search_view import SearchView
from storyplanner.ui.tag_analysis_view import TagAnalysisView
from storyplanner.ui.timeline_view import TimelineView


class MainWindow(QMainWindow):
    def __init__(self, db: Database, project_id: int) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._current_file: str | None = None
        self._dirty = False
        self._update_title()
        self.resize(900, 600)

        # -- Menu bar --------------------------------------------------------
        self._build_menu_bar()

        central = QWidget()
        root_layout = QHBoxLayout(central)

        # -- Left sidebar ----------------------------------------------------
        sidebar = QWidget()
        sidebar.setFixedWidth(160)
        sidebar.setStyleSheet(
            "QWidget { background-color: #0b0d10; }"
            "QPushButton { border: none; border-radius: 0; text-align: left;"
            "  padding: 7px 14px; background-color: transparent; color: #9aa0a6; }"
            "QPushButton:hover { background-color: #1c2128; color: #e6e6e6; }"
            "QPushButton:pressed { background-color: #1a3a2a; color: #00ff9c; }"
        )
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(1)

        self.sidebar_buttons: dict[str, QPushButton] = {}
        for label in ("Projects", "Characters", "Places", "Notes", "Scenes", "Timeline", "Outline", "Acts", "Beats", "Tags", "Graph", "Arcs", "Search"):
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
        self.sidebar_buttons["Outline"].clicked.connect(self._show_outline)
        self.sidebar_buttons["Acts"].clicked.connect(self._show_acts)
        self.sidebar_buttons["Beats"].clicked.connect(self._show_beats)
        self.sidebar_buttons["Tags"].clicked.connect(self._show_tags)
        self.sidebar_buttons["Graph"].clicked.connect(self._show_graph)
        self.sidebar_buttons["Arcs"].clicked.connect(self._show_arcs)
        self.sidebar_buttons["Search"].clicked.connect(self._show_search)

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
        self._set_content(
            CharactersView(
                self._db, self._project_id,
                on_data_changed=self._on_data_changed,
                on_link_clicked=self._on_link_navigated,
            )
        )

    def _show_places(self) -> None:
        self._set_content(
            PlacesView(
                self._db, self._project_id,
                on_data_changed=self._on_data_changed,
                on_link_clicked=self._on_link_navigated,
            )
        )

    def _show_notes(self) -> None:
        self._set_content(
            NotesView(
                self._db,
                self._project_id,
                on_data_changed=self._on_data_changed,
                on_link_clicked=self._on_link_navigated,
            )
        )

    def _show_scenes(self) -> None:
        self._set_content(
            ScenesView(
                self._db,
                self._project_id,
                on_data_changed=self._on_data_changed,
                on_link_clicked=self._on_link_navigated,
            )
        )

    def _show_timeline(self) -> None:
        self._set_content(
            TimelineView(
                self._db,
                self._project_id,
                on_scene_selected=self._open_scene_in_editor,
                on_data_changed=self._on_data_changed,
            )
        )

    def _show_outline(self) -> None:
        self._set_content(OutlineView(self._db, self._project_id))

    def _show_acts(self) -> None:
        self._set_content(ActAnalysisView(self._db, self._project_id))

    def _show_beats(self) -> None:
        self._set_content(BeatAnalysisView(self._db, self._project_id))

    def _show_tags(self) -> None:
        self._set_content(TagAnalysisView(self._db, self._project_id))

    def _show_graph(self) -> None:
        self._set_content(
            GraphView(
                self._db, self._project_id,
                on_node_clicked=self._on_link_navigated,
            )
        )

    def _show_arcs(self) -> None:
        self._set_content(
            CharacterArcView(
                self._db, self._project_id,
                on_scene_selected=self._open_scene_in_editor,
            )
        )

    def _show_search(self) -> None:
        self._set_content(
            SearchView(
                self._db,
                self._project_id,
                on_result_selected=self._on_search_result_selected,
            )
        )

    def _on_search_result_selected(self, entity_type: str, entity_id: int) -> None:
        self._on_link_navigated(entity_type, entity_id)

    def _on_link_navigated(self, entity_type: str, entity_id: int) -> None:
        if entity_type == "Character":
            view = CharactersView(
                self._db, self._project_id,
                on_data_changed=self._on_data_changed,
                on_link_clicked=self._on_link_navigated,
            )
            self._set_content(view)
            view.select_character(entity_id)
        elif entity_type == "Place":
            view = PlacesView(
                self._db, self._project_id,
                on_data_changed=self._on_data_changed,
                on_link_clicked=self._on_link_navigated,
            )
            self._set_content(view)
            view.select_place(entity_id)
        elif entity_type == "Note":
            view = NotesView(
                self._db, self._project_id,
                on_data_changed=self._on_data_changed,
                on_link_clicked=self._on_link_navigated,
            )
            self._set_content(view)
            view.select_note(entity_id)
        elif entity_type == "Scene":
            self._open_scene_in_editor(entity_id)

    def _open_scene_in_editor(self, scene_id: int) -> None:
        view = ScenesView(
            self._db, self._project_id,
            on_data_changed=self._on_data_changed,
            on_link_clicked=self._on_link_navigated,
        )
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
        self._current_file = None
        self._mark_clean()
        self._reset_content("Import complete. Select a section from the sidebar.")
        QMessageBox.information(
            self, "Import", f"Project imported successfully (ID {new_project_id})."
        )

    def _on_export(self) -> None:
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Project",
            "",
            "JSON (*.json);;Markdown (*.md);;Screenplay (*.txt);;CSV – Scenes (*.csv)",
        )
        if not path:
            return

        if path.endswith(".csv") or "CSV" in selected_filter:
            content = export_csv_scenes(self._db, self._project_id)
            if not path.endswith(".csv"):
                path += ".csv"
        elif "Screenplay" in selected_filter:
            content = export_screenplay(self._db, self._project_id)
            if not path.endswith(".txt"):
                path += ".txt"
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

    # -- Menu bar ------------------------------------------------------------

    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")

        open_action = QAction("Open Project...", self)
        open_action.triggered.connect(self._on_open_project)
        file_menu.addAction(open_action)

        save_as_action = QAction("Save As...", self)
        save_as_action.triggered.connect(self._on_save_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        self._recent_menu = QMenu("Recent Projects", self)
        file_menu.addMenu(self._recent_menu)
        self._refresh_recent_menu()

    def _refresh_recent_menu(self) -> None:
        self._recent_menu.clear()
        paths = recent_projects.load()
        if not paths:
            no_recent = QAction("(no recent projects)", self)
            no_recent.setEnabled(False)
            self._recent_menu.addAction(no_recent)
            return
        for path in paths:
            label = Path(path).name
            action = QAction(label, self)
            action.setToolTip(path)
            action.triggered.connect(lambda checked, p=path: self._open_file(p))
            self._recent_menu.addAction(action)

    def _update_title(self) -> None:
        dirty_mark = " *" if self._dirty else ""
        if self._current_file:
            name = Path(self._current_file).name
            self.setWindowTitle(f"StoryPlanner — {name}{dirty_mark}")
        else:
            self.setWindowTitle(f"StoryPlanner{dirty_mark}")

    def _on_open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            "",
            "JSON (*.json)",
        )
        if path:
            self._open_file(path)

    def _open_file(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
        except OSError as e:
            QMessageBox.warning(self, "Open Project", f"Could not read file:\n{e}")
            return

        data, error = validate_import_data(raw)
        if data is None:
            QMessageBox.warning(self, "Open Project", error)
            return

        new_project_id = import_json(self._db, data)
        self._project_id = new_project_id
        self._current_file = path
        self._mark_clean()
        recent_projects.add(path)
        self._refresh_recent_menu()

        self._reset_content("Project loaded. Select a section from the sidebar.")

    def _on_save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project As",
            "",
            "JSON (*.json)",
        )
        if not path:
            return
        if not path.endswith(".json"):
            path += ".json"

        content = export_json(self._db, self._project_id)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        self._current_file = path
        self._mark_clean()
        recent_projects.add(path)
        self._refresh_recent_menu()
        QMessageBox.information(self, "Save As", f"Project saved to {path}")

    def _reset_content(self, message: str) -> None:
        widget = QWidget()
        QVBoxLayout(widget).addWidget(QLabel(message))
        self._set_content(widget)

    # -- Dirty state and autosave --------------------------------------------

    def _on_data_changed(self) -> None:
        self._dirty = True
        self._update_title()
        self._auto_save()

    def _auto_save(self) -> None:
        if not self._current_file:
            return
        content = export_json(self._db, self._project_id)
        with open(self._current_file, "w", encoding="utf-8") as f:
            f.write(content)
        self._dirty = False
        self._update_title()

    def _mark_clean(self) -> None:
        self._dirty = False
        self._update_title()
