"""Timeline view — read-only ordered overview of all scenes."""

from collections.abc import Callable

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
    def __init__(
        self,
        db: Database,
        project_id: int,
        on_scene_selected: Callable[[int], None] | None = None,
    ) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._on_scene_selected = on_scene_selected
        self._scene_ids: list[int] = []

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
        self._table.cellDoubleClicked.connect(self._on_double_click)
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
        self._scene_ids = [scene.id for scene in scenes]
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

    def _on_double_click(self, row: int, _column: int) -> None:
        if self._on_scene_selected is None:
            return
        if 0 <= row < len(self._scene_ids):
            self._on_scene_selected(self._scene_ids[row])
