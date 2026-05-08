"""Autosave manager with debounced saves and status signals.

Replaces the synchronous _auto_save() in MainWindow with a debounced,
non-blocking save that coalesces rapid edits and reports status.
"""

import json
import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from storyplanner.db import Database
from storyplanner.export import _gather_project_data

log = logging.getLogger(__name__)

_DEBOUNCE_MS = 3000


class AutosaveManager(QObject):
    """Debounced autosave that writes project JSON after edits settle."""

    status_changed = Signal(str)  # "Saving…", "Saved", "Save failed"

    def __init__(
        self,
        db: Database,
        project_id: int,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._db = db
        self._project_id = project_id
        self._file_path: str | None = None
        self._dirty = False
        self._saving = False
        self._queued = False

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._do_save)

    @property
    def dirty(self) -> bool:
        return self._dirty

    @property
    def file_path(self) -> str | None:
        return self._file_path

    @file_path.setter
    def file_path(self, path: str | None) -> None:
        self._file_path = path

    def mark_dirty(self) -> None:
        self._dirty = True
        if self._file_path:
            self._debounce.start()

    def mark_clean(self) -> None:
        self._dirty = False
        self._debounce.stop()

    def save_now(self) -> bool:
        """Immediate save (Ctrl+S or close). Returns True on success."""
        self._debounce.stop()
        return self._do_save()

    def _do_save(self) -> bool:
        if not self._file_path:
            return False
        if self._saving:
            self._queued = True
            return False

        self._saving = True
        self.status_changed.emit("Saving…")

        try:
            data = _gather_project_data(self._db, self._project_id)
            content = json.dumps(data, indent=2, ensure_ascii=False)
            Path(self._file_path).write_text(content, encoding="utf-8")
            self._dirty = False
            self.status_changed.emit("Saved")
            log.debug("Autosaved to %s", self._file_path)
            ok = True
        except Exception:
            log.exception("Autosave failed")
            self.status_changed.emit("Save failed")
            ok = False
        finally:
            self._saving = False

        if self._queued:
            self._queued = False
            QTimer.singleShot(100, self._do_save)

        return ok

    def gather_data(self) -> dict:
        return _gather_project_data(self._db, self._project_id)
