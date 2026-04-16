"""Timeline view — read-only ordered overview of all scenes."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
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
NO_CHAPTER = "(No Chapter)"
HEADER_BG = QColor(220, 220, 220)


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
        self._row_scene_ids: dict[int, int] = {}

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

        groups: list[tuple[str, list]] = []
        current_chapter: str | None = None
        for scene in scenes:
            chapter = scene.chapter or ""
            if chapter != current_chapter:
                current_chapter = chapter
                groups.append((chapter, []))
            groups[-1][1].append(scene)

        total_rows = len(scenes) + len(groups)
        self._table.setRowCount(total_rows)
        self._row_scene_ids.clear()

        table_row = 0
        scene_index = 0
        for chapter_label, chapter_scenes in groups:
            self._insert_chapter_header(
                table_row, chapter_label if chapter_label else NO_CHAPTER
            )
            table_row += 1

            for scene in chapter_scenes:
                scene_index += 1
                self._row_scene_ids[table_row] = scene.id
                self._insert_scene_row(table_row, scene_index, scene)
                table_row += 1

    def _insert_chapter_header(self, row: int, label: str) -> None:
        header_item = QTableWidgetItem(label)
        bold_font = QFont()
        bold_font.setBold(True)
        header_item.setFont(bold_font)
        header_item.setBackground(QBrush(HEADER_BG))
        header_item.setFlags(Qt.ItemFlag.NoItemFlags)
        self._table.setItem(row, 0, header_item)
        self._table.setSpan(row, 0, 1, 4)

    def _insert_scene_row(self, row: int, index: int, scene) -> None:
        align = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        values = [str(index), scene.chapter, scene.plotline, scene.title]
        for col, text in enumerate(values):
            item = QTableWidgetItem(text)
            item.setTextAlignment(align)
            self._table.setItem(row, col, item)

    # -- Navigation ----------------------------------------------------------

    def _on_double_click(self, row: int, _column: int) -> None:
        if self._on_scene_selected is None:
            return
        scene_id = self._row_scene_ids.get(row)
        if scene_id is not None:
            self._on_scene_selected(scene_id)
