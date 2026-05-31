"""Central Logos section view (navigation fix).

A lightweight read-only landing page for Logos that **reuses** the existing
``LogosController`` and the already-built inline engines (proactive suggestions,
diagnostics, health). It creates no new analysis engine, no second Logos system,
and no provider settings — it only surfaces what already exists in one place so a
left-panel "Logos" item has somewhere to open.

Everything here is deterministic and read-only:
- shows current Logos status (project, section, action count),
- lists the Logos actions available for the current section (catalogue),
- shows current proactive suggestions if a scanner is provided,
- offers buttons that delegate to the existing diagnostics / health drawers,
- shows a concise empty state when no project is loaded.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class LogosView(QWidget):
    def __init__(self, db, project_id, controller=None, *,
                 get_context=None, get_writing_mode=None,
                 get_section=None, scan_suggestions=None,
                 on_open_diagnostics=None, on_open_health=None,
                 on_refresh_suggestions=None, parent=None):
        super().__init__(parent)
        self._db = db
        self._project_id = project_id
        self._controller = controller
        self._get_context = get_context
        self._get_writing_mode = get_writing_mode
        self._get_section = get_section
        self._scan_suggestions = scan_suggestions
        self._on_open_diagnostics = on_open_diagnostics
        self._on_open_health = on_open_health
        self._on_refresh_suggestions = on_refresh_suggestions

        self.setObjectName("logosView")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)

        title = QLabel("Logos")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        root.addWidget(title)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet("font-size: 12px; opacity: 0.85;")
        root.addWidget(self._status)

        # Action row — delegate to the existing drawers / scanners.
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self._diag_btn = QPushButton("Diagnostics")
        self._health_btn = QPushButton("Narrative Health")
        self._refresh_btn = QPushButton("Refresh Suggestions")
        for b in (self._diag_btn, self._health_btn, self._refresh_btn):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_row.addWidget(b)
        btn_row.addStretch()
        self._diag_btn.clicked.connect(self._open_diagnostics)
        self._health_btn.clicked.connect(self._open_health)
        self._refresh_btn.clicked.connect(self.refresh)
        root.addLayout(btn_row)

        # Scrollable body (compact / 13-inch friendly).
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._body = QWidget()
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 4, 0, 0)
        self._body_layout.setSpacing(6)
        self._body_layout.addStretch()
        scroll.setWidget(self._body)
        root.addWidget(scroll, stretch=1)

        self.refresh()

    # -- helpers ------------------------------------------------------------

    def _clear_body(self) -> None:
        while self._body_layout.count():
            item = self._body_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _section_header(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 13px; font-weight: 600; margin-top: 6px;")
        return lbl

    def _row(self, primary: str, secondary: str = "") -> QWidget:
        w = QFrame()
        w.setObjectName("logosRow")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(1)
        p = QLabel(primary)
        p.setWordWrap(True)
        p.setStyleSheet("font-size: 12px; font-weight: 500;")
        lay.addWidget(p)
        if secondary:
            s = QLabel(secondary)
            s.setWordWrap(True)
            s.setStyleSheet("font-size: 11px; opacity: 0.75;")
            lay.addWidget(s)
        return w

    def _current_section(self) -> str:
        try:
            if callable(self._get_section):
                return self._get_section() or "Manuscript"
        except Exception:
            pass
        return "Manuscript"

    def _writing_mode(self) -> str:
        try:
            if callable(self._get_writing_mode):
                return self._get_writing_mode() or ""
        except Exception:
            pass
        return ""

    # -- delegated actions --------------------------------------------------

    def _open_diagnostics(self) -> None:
        if callable(self._on_open_diagnostics):
            self._on_open_diagnostics()

    def _open_health(self) -> None:
        if callable(self._on_open_health):
            self._on_open_health()

    # -- refresh ------------------------------------------------------------

    def refresh(self) -> None:
        self._clear_body()

        if not self._project_id:
            self._status.setText("No project loaded. Open or create a project to "
                                 "use Logos.")
            for b in (self._diag_btn, self._health_btn, self._refresh_btn):
                b.setEnabled(False)
            self._body_layout.addStretch()
            return
        for b in (self._diag_btn, self._health_btn, self._refresh_btn):
            b.setEnabled(True)

        section = self._current_section()
        mode = self._writing_mode()

        actions = []
        if self._controller is not None:
            try:
                actions = self._controller.available_actions(
                    section, writing_mode=mode)
            except Exception:
                actions = []

        self._status.setText(
            f"Section: {section}"
            + (f" · mode: {mode}" if mode else "")
            + f" · {len(actions)} action(s) available. "
            "Logos is advisory — it previews/confirms; it never auto-applies.")

        # Suggestions (deterministic; provided by the existing proactive engine).
        suggestions = []
        if callable(self._on_refresh_suggestions):
            try:
                self._on_refresh_suggestions()
            except Exception:
                pass
        if callable(self._scan_suggestions):
            try:
                suggestions = list(self._scan_suggestions() or [])
            except Exception:
                suggestions = []
        if suggestions:
            self._body_layout.addWidget(
                self._section_header(f"Suggestions ({len(suggestions)})"))
            for s in suggestions[:12]:
                title = getattr(s, "title", "") or getattr(s, "type", "Suggestion")
                msg = getattr(s, "message", "") or getattr(s, "evidence", "")
                self._body_layout.addWidget(self._row(title, msg))

        # Available actions catalogue.
        self._body_layout.addWidget(
            self._section_header(f"Available actions for {section}"))
        if not actions:
            self._body_layout.addWidget(
                self._row("No Logos actions for this section.",
                          "Open a section like Manuscript or PSYKE for more."))
        else:
            for act in actions[:30]:
                label = getattr(act, "label", "") or getattr(act, "name", "")
                desc = getattr(act, "description", "")
                kind = "deterministic" if getattr(act, "deterministic", False) \
                    else "AI"
                self._body_layout.addWidget(
                    self._row(f"{label}  ·  {kind}", desc))

        self._body_layout.addStretch()

    # Allow MainWindow to re-point this view at a new project without rebuild.
    def set_project(self, project_id: int) -> None:
        self._project_id = project_id
        self.refresh()
