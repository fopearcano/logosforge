"""Story Health View — compact visual panel for narrative status."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database
from storyplanner.story_health import HealthSignal, StoryHealth, compute_health, level_color


class _HealthBar(QFrame):
    """A single health indicator: label + bar + status text."""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("healthBar")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(2)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self._title = QLabel(title)
        self._title.setObjectName("healthBarTitle")
        header.addWidget(self._title)

        self._status = QLabel("")
        self._status.setObjectName("healthBarStatus")
        self._status.setAlignment(Qt.AlignmentFlag.AlignRight)
        header.addWidget(self._status)
        layout.addLayout(header)

        self._bar = QProgressBar()
        self._bar.setObjectName("healthProgressBar")
        self._bar.setMaximum(100)
        self._bar.setTextVisible(False)
        self._bar.setMaximumHeight(6)
        layout.addWidget(self._bar)

    def set_signal(self, signal: HealthSignal) -> None:
        self._status.setText(signal.label)
        self._bar.setValue(int(signal.score * 100))
        color = level_color(signal.level)
        self._bar.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {color}; border-radius: 3px; }}"
        )
        self._status.setStyleSheet(f"color: {color};")


class StoryHealthView(QWidget):
    """Compact story health panel with four indicator bars."""

    def __init__(self, db: Database, project_id: int, parent=None) -> None:
        super().__init__(parent)
        self._db = db
        self._project_id = project_id

        self.setObjectName("storyHealthView")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)

        title = QLabel("Story Health")
        title.setObjectName("healthTitle")
        layout.addWidget(title)

        self._structure_bar = _HealthBar("Structure")
        layout.addWidget(self._structure_bar)

        self._chars_bar = _HealthBar("Characters")
        layout.addWidget(self._chars_bar)

        self._arcs_bar = _HealthBar("Arc Coverage")
        layout.addWidget(self._arcs_bar)

        self._density_bar = _HealthBar("Scene Density")
        layout.addWidget(self._density_bar)

        layout.addStretch()
        self.refresh()

    def refresh(self) -> None:
        health = compute_health(self._db, self._project_id)
        self._structure_bar.set_signal(health.structure)
        self._chars_bar.set_signal(health.characters)
        self._arcs_bar.set_signal(health.arcs)
        self._density_bar.set_signal(health.density)
        self._health = health

    def get_health(self) -> StoryHealth:
        return self._health
