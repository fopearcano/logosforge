"""Timeline view — read-only ordered overview of all scenes."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database

FILTER_ALL = "All"


class TimelineView(QWidget):
    def __init__(self, db: Database, project_id: int) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Timeline"))

        # -- Filters ---------------------------------------------------------
        filter_row = QHBoxLayout()

        filter_row.addWidget(QLabel("Chapter"))
        self._chapter_filter = QComboBox()
        self._chapter_filter.currentTextChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._chapter_filter)

        filter_row.addWidget(QLabel("Plotline"))
        self._plotline_filter = QComboBox()
        self._plotline_filter.currentTextChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._plotline_filter)

        filter_row.addStretch()
        layout.addLayout(filter_row)

        # -- Table -----------------------------------------------------------
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["#", "Chapter", "Plotline", "Title"])
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        self._refresh_filters()
        self._load()

    # -- Filters -------------------------------------------------------------

    def _refresh_filters(self) -> None:
        self._refresh_combo(
            self._chapter_filter,
            self._db.get_scene_chapters(self._project_id),
        )
        self._refresh_combo(
            self._plotline_filter,
            self._db.get_scene_plotlines(self._project_id),
        )

    def _refresh_combo(self, combo: QComboBox, values: list[str]) -> None:
        combo.blockSignals(True)
        current = combo.currentText()
        combo.clear()
        combo.addItem(FILTER_ALL)
        for val in values:
            combo.addItem(val)
        idx = combo.findText(current)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _get_filter_value(self, combo: QComboBox) -> str | None:
        text = combo.currentText()
        return None if text == FILTER_ALL else text

    def _on_filter_changed(self) -> None:
        self._load()

    # -- Table ---------------------------------------------------------------

    def _load(self) -> None:
        scenes = self._db.get_all_scenes(
            self._project_id,
            chapter=self._get_filter_value(self._chapter_filter),
            plotline=self._get_filter_value(self._plotline_filter),
        )
        self._table.setRowCount(len(scenes))
        for row, scene in enumerate(scenes):
            self._table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self._table.setItem(row, 1, QTableWidgetItem(scene.chapter))
            self._table.setItem(row, 2, QTableWidgetItem(scene.plotline))
            self._table.setItem(row, 3, QTableWidgetItem(scene.title))
            for col in range(4):
                item = self._table.item(row, col)
                if item:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                    )
