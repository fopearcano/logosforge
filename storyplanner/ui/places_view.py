"""Places management view — list + create form."""

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database


class PlacesView(QWidget):
    def __init__(self, db: Database, project_id: int) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id

        root = QHBoxLayout(self)

        # -- Left: place list ------------------------------------------------
        left = QVBoxLayout()
        left.addWidget(QLabel("Places"))
        self._list = QListWidget()
        left.addWidget(self._list)
        root.addLayout(left)

        # -- Right: create form ----------------------------------------------
        right = QVBoxLayout()
        right.addWidget(QLabel("New Place"))

        right.addWidget(QLabel("Name"))
        self._name_input = QLineEdit()
        right.addWidget(self._name_input)

        right.addWidget(QLabel("Description"))
        self._desc_input = QPlainTextEdit()
        right.addWidget(self._desc_input)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._on_save)
        right.addWidget(save_btn)

        right.addStretch()
        root.addLayout(right)

        self._refresh_list()

    def _refresh_list(self) -> None:
        self._list.clear()
        for place in self._db.get_all_places(self._project_id):
            self._list.addItem(place.name)

    def _on_save(self) -> None:
        name = self._name_input.text().strip()
        if not name:
            return

        self._db.create_place(
            project_id=self._project_id,
            name=name,
            description=self._desc_input.toPlainText().strip(),
        )

        self._name_input.clear()
        self._desc_input.clear()
        self._refresh_list()
