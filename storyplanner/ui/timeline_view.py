"""Timeline view — read-only ordered overview of all scenes."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database


class TimelineView(QWidget):
    def __init__(self, db: Database, project_id: int) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Timeline"))

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["#", "Chapter", "Plotline", "Title"])
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        self._load()

    def _load(self) -> None:
        scenes = self._db.get_all_scenes(self._project_id)
        self._table.setRowCount(len(scenes))
        for row, scene in enumerate(scenes):
            self._table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self._table.setItem(row, 1, QTableWidgetItem(scene.chapter))
            self._table.setItem(row, 2, QTableWidgetItem(scene.plotline))
            self._table.setItem(row, 3, QTableWidgetItem(scene.title))
            for col in range(4):
                item = self._table.item(row, col)
                if item:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
