"""Timeline view — plotline-column overview with minimal editing."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
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
        self._selected_scene_id: int | None = None

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
        self._table.cellClicked.connect(self._on_cell_clicked)
        self._table.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        # -- Actions ---------------------------------------------------------
        actions_row = QHBoxLayout()

        self._move_up_btn = QPushButton("Move Up")
        self._move_up_btn.setEnabled(False)
        self._move_up_btn.clicked.connect(self._on_move_up)
        actions_row.addWidget(self._move_up_btn)

        self._move_down_btn = QPushButton("Move Down")
        self._move_down_btn.setEnabled(False)
        self._move_down_btn.clicked.connect(self._on_move_down)
        actions_row.addWidget(self._move_down_btn)

        actions_row.addWidget(QLabel("Plotline:"))
        self._plotline_combo = QComboBox()
        self._plotline_combo.setEditable(True)
        self._plotline_combo.setEnabled(False)
        actions_row.addWidget(self._plotline_combo)

        self._set_plotline_btn = QPushButton("Set Plotline")
        self._set_plotline_btn.setEnabled(False)
        self._set_plotline_btn.clicked.connect(self._on_set_plotline)
        actions_row.addWidget(self._set_plotline_btn)

        actions_row.addStretch()
        layout.addLayout(actions_row)

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
        self._clear_selection()
        self._load()

    # -- Selection -----------------------------------------------------------

    def _on_cell_clicked(self, row: int, column: int) -> None:
        scene_id = self._cell_scene_ids.get((row, column))
        if scene_id is not None:
            self._selected_scene_id = scene_id
            self._set_actions_enabled(True)
            self._refresh_plotline_combo()
        else:
            self._clear_selection()

    def _clear_selection(self) -> None:
        self._selected_scene_id = None
        self._set_actions_enabled(False)
        self._table.clearSelection()

    def _set_actions_enabled(self, enabled: bool) -> None:
        self._move_up_btn.setEnabled(enabled)
        self._move_down_btn.setEnabled(enabled)
        self._plotline_combo.setEnabled(enabled)
        self._set_plotline_btn.setEnabled(enabled)

    def _refresh_plotline_combo(self) -> None:
        combo = self._plotline_combo
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("")
        for pl in self._db.get_scene_plotlines(self._project_id):
            combo.addItem(pl)
        if self._selected_scene_id is not None:
            scene = self._db.get_scene_by_id(self._selected_scene_id)
            if scene:
                idx = combo.findText(scene.plotline)
                combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    # -- Actions -------------------------------------------------------------

    def _on_move_up(self) -> None:
        if self._selected_scene_id is None:
            return
        self._db.move_scene_up(self._selected_scene_id)
        self._load()
        self._reselect()

    def _on_move_down(self) -> None:
        if self._selected_scene_id is None:
            return
        self._db.move_scene_down(self._selected_scene_id)
        self._load()
        self._reselect()

    def _on_set_plotline(self) -> None:
        if self._selected_scene_id is None:
            return
        plotline = self._plotline_combo.currentText().strip()
        self._db.update_scene_plotline(self._selected_scene_id, plotline)
        self._load()
        self._reselect()

    def _reselect(self) -> None:
        if self._selected_scene_id is None:
            return
        for (row, col), sid in self._cell_scene_ids.items():
            if sid == self._selected_scene_id:
                self._table.setCurrentCell(row, col)
                self._set_actions_enabled(True)
                return
        self._clear_selection()

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
