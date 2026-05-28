"""Per-project settings dialog — narrative engine and default writing format.

Owns the project's narrative identity. Manuscript and other sections read
these values via storyplanner.project_compat and adapt on change.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)

from storyplanner.db import Database
from storyplanner.project_compat import (
    ALL_ENGINES,
    ALL_FORMATS,
    ENGINE_LABELS,
    FORMAT_LABELS,
    default_format_for_engine,
    get_project_narrative_engine,
    get_project_writing_format,
)


class ProjectSettingsDialog(QDialog):
    """Dialog for editing a project's narrative engine + default format."""

    def __init__(
        self,
        db: Database,
        project_id: int,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._db = db
        self._project_id = project_id
        self._project = db.get_project_by_id(project_id)
        self._initial_engine = get_project_narrative_engine(self._project)
        self._initial_format = get_project_writing_format(self._project)
        self._format_manually_changed = False

        self.setWindowTitle("Project Settings")
        self.setMinimumWidth(420)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        title = QLabel(self._project.title if self._project else "Project")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        hint = QLabel(
            "Narrative engine defines how the assistant, PSYKE, graph,"
            " plot, and review tools reason about your story. The default"
            " writing format chooses the block grammar the manuscript"
            " editor uses for new scenes."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(hint)

        # -- Narrative engine ------------------------------------------------
        engine_row = QHBoxLayout()
        engine_row.addWidget(QLabel("Narrative Engine:"))
        self._engine_combo = QComboBox()
        for key in ALL_ENGINES:
            self._engine_combo.addItem(ENGINE_LABELS[key], key)
        idx = self._engine_combo.findData(self._initial_engine)
        if idx >= 0:
            self._engine_combo.setCurrentIndex(idx)
        self._engine_combo.currentIndexChanged.connect(self._on_engine_changed)
        engine_row.addWidget(self._engine_combo, stretch=1)
        layout.addLayout(engine_row)

        # -- Default writing format ------------------------------------------
        format_row = QHBoxLayout()
        format_row.addWidget(QLabel("Default Writing Format:"))
        self._format_combo = QComboBox()
        for key in ALL_FORMATS:
            self._format_combo.addItem(FORMAT_LABELS[key], key)
        idx = self._format_combo.findData(self._initial_format)
        if idx >= 0:
            self._format_combo.setCurrentIndex(idx)
        self._format_combo.currentIndexChanged.connect(self._on_format_user_changed)
        format_row.addWidget(self._format_combo, stretch=1)
        layout.addLayout(format_row)

        # -- Buttons ---------------------------------------------------------
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_engine_changed(self, _index: int) -> None:
        """When the engine changes, auto-sync the default format unless the
        user manually overrode it during this dialog session."""
        if self._format_manually_changed:
            return
        engine = self._engine_combo.currentData()
        suggested = default_format_for_engine(engine)
        idx = self._format_combo.findData(suggested)
        if idx >= 0:
            self._format_combo.blockSignals(True)
            self._format_combo.setCurrentIndex(idx)
            self._format_combo.blockSignals(False)

    def _on_format_user_changed(self, _index: int) -> None:
        self._format_manually_changed = True

    def _on_accept(self) -> None:
        new_engine = self._engine_combo.currentData()
        new_format = self._format_combo.currentData()

        engine_changed = new_engine != self._initial_engine
        if engine_changed:
            confirm = QMessageBox.question(
                self,
                "Change Narrative Engine?",
                "Changing the narrative engine affects how the assistant, "
                "PSYKE, graph, plot, and review tools interpret existing "
                "scenes and metadata.\n\nContinue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        if engine_changed:
            self._db.update_project_narrative_engine(self._project_id, new_engine)
        if new_format != self._initial_format:
            self._db.update_project_writing_format(self._project_id, new_format)
        self.accept()

    def get_selected_engine(self) -> str:
        return self._engine_combo.currentData()

    def get_selected_format(self) -> str:
        return self._format_combo.currentData()
