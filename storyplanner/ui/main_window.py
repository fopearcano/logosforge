"""Main window with a sidebar and content area."""

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database
from storyplanner.ui.characters_view import CharactersView
from storyplanner.ui.notes_view import NotesView
from storyplanner.ui.places_view import PlacesView


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
        for label in ("Projects", "Characters", "Places", "Notes", "Scenes"):
            btn = QPushButton(label)
            sidebar_layout.addWidget(btn)
            self.sidebar_buttons[label] = btn

        # Push buttons to the top
        sidebar_layout.addStretch()

        # Connect sidebar buttons
        self.sidebar_buttons["Characters"].clicked.connect(self._show_characters)
        self.sidebar_buttons["Places"].clicked.connect(self._show_places)
        self.sidebar_buttons["Notes"].clicked.connect(self._show_notes)

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
