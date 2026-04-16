"""Timeline view — plotline-column overview of all scenes."""

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
UNASSIGNED = "Unassigned"


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
        self._cell_scene_ids: dict[tuple[int, int], int] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Timeline"))

        # -- Chapter filter --------------------------------------------------
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Chapter"))
        self._chapter_filter = QComboBox()
        self._chapter_filter.currentTextChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._chapter_filter)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # -- Table -----------------------------------------------------------
        self._table = QTableWidget()
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setWordWrap(True)
        self._table.verticalHeader().setVisible(False)
        self._table.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        self._refresh_filter()
        self._load()

    # -- Filter --------------------------------------------------------------

    def _refresh_filter(self) -> None:
        combo = self._chapter_filter
        combo.blockSignals(True)
        current = combo.currentText()
        combo.clear()
        combo.addItem(FILTER_ALL)
        for ch in self._db.get_scene_chapters(self._project_id):
            combo.addItem(ch)
        idx = combo.findText(current)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _get_chapter_filter(self) -> str | None:
        text = self._chapter_filter.currentText()
        return None if text == FILTER_ALL else text

    def _on_filter_changed(self) -> None:
        self._load()

    # -- Table ---------------------------------------------------------------

    def _load(self) -> None:
        scenes = self._db.get_all_scenes(
            self._project_id,
            chapter=self._get_chapter_filter(),
        )

        columns = self._build_plotline_columns(scenes)
        plotline_to_col: dict[str, int] = {}
        for i, name in enumerate(columns):
            plotline_to_col[name] = i

        self._table.clear()
        self._table.setColumnCount(len(columns) if columns else 1)
        self._table.setHorizontalHeaderLabels(columns if columns else [UNASSIGNED])
        self._table.setRowCount(len(scenes))
        self._cell_scene_ids.clear()

        for row, scene in enumerate(scenes):
            col_name = scene.plotline if scene.plotline else UNASSIGNED
            col = plotline_to_col[col_name]

            item = QTableWidgetItem(self._format_cell(row + 1, scene))
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
            )
            self._table.setItem(row, col, item)
            self._cell_scene_ids[(row, col)] = scene.id

        header = self._table.horizontalHeader()
        for i in range(self._table.columnCount()):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        self._table.resizeRowsToContents()

    def _build_plotline_columns(self, scenes: list) -> list[str]:
        plotlines: list[str] = []
        seen: set[str] = set()
        has_unassigned = False
        for scene in scenes:
            if not scene.plotline:
                has_unassigned = True
            elif scene.plotline not in seen:
                seen.add(scene.plotline)
                plotlines.append(scene.plotline)
        if has_unassigned:
            plotlines.append(UNASSIGNED)
        return plotlines

    def _format_cell(self, index: int, scene) -> str:
        parts = [f"#{index}  {scene.title}"]
        if scene.chapter:
            parts.append(scene.chapter)
        return "\n".join(parts)

    # -- Navigation ----------------------------------------------------------

    def _on_double_click(self, row: int, column: int) -> None:
        if self._on_scene_selected is None:
            return
        scene_id = self._cell_scene_ids.get((row, column))
        if scene_id is not None:
            self._on_scene_selected(scene_id)
