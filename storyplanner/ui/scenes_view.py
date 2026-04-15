"""Scenes management view — list + create form."""

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


class ScenesView(QWidget):
    def __init__(self, db: Database, project_id: int) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id

        root = QHBoxLayout(self)

        # -- Left: scene list ------------------------------------------------
        left = QVBoxLayout()
        left.addWidget(QLabel("Scenes"))
        self._list = QListWidget()
        left.addWidget(self._list)
        root.addLayout(left)

        # -- Right: create form ----------------------------------------------
        right = QVBoxLayout()
        right.addWidget(QLabel("New Scene"))

        right.addWidget(QLabel("Title"))
        self._title_input = QLineEdit()
        right.addWidget(self._title_input)

        right.addWidget(QLabel("Summary"))
        self._summary_input = QPlainTextEdit()
        right.addWidget(self._summary_input)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._on_save)
        right.addWidget(save_btn)

        right.addStretch()
        root.addLayout(right)

        self._refresh_list()

    def _refresh_list(self) -> None:
        self._list.clear()
        for scene in self._db.get_all_scenes(self._project_id):
            self._list.addItem(scene.title)

    def _on_save(self) -> None:
        title = self._title_input.text().strip()
        if not title:
            return

        self._db.create_scene(
            project_id=self._project_id,
            title=title,
            summary=self._summary_input.toPlainText().strip(),
        )

        self._title_input.clear()
        self._summary_input.clear()
        self._refresh_list()
