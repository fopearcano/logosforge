"""Voice dictation — local-first panel + floating Voice Dictation window.

:class:`VoicePanel` is the dictation surface (status, backend row, transcript
preview, Start / Stop / Commit / Clear / Hide). It drives
:class:`VoiceSessionController`; transcription runs off the UI thread (on the
recorder's callback thread) and results are marshaled back via Qt signals.

:class:`VoiceDictationWindow` is the panel's host: a **floating, modeless,
resizable** window so the transcript can be reviewed comfortably while
writing. It is always **parented to the main window** (never a parentless
top-level window, no unsafe window flags — the rules that keep it clear of
the old standalone-Pages fullscreen-minimize bug). Showing/hiding it never
touches project state; closing/hiding while recording stops the session
safely and keeps the transcript preview (nothing is silently discarded, and
nothing is ever auto-committed).

Local-first: only the local backends are ever used; audio is processed on
this device (or, in LAN mode, sent only to the configured local-network
Whisper server). Feature-flagged OFF by default; when the backend is not
configured the panel shows a non-blocking setup message and stays inert.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from storyplanner.voice.editor_commit import EditorCommitTarget
from storyplanner.voice.types import PRIVACY_NOTE, SETUP_MESSAGE, VoiceStatus

# (value stored in settings, label shown in the selector)
_BACKEND_MODES = (
    ("disabled", "Disabled"),
    ("local_process", "Local PC"),
    ("lan_server", "Local LAN Server"),
    ("mock", "Mock / Test"),
)

_STATUS_TEXT = {
    VoiceStatus.DISABLED: "Voice: not configured",
    VoiceStatus.OFF: "Voice: off",
    VoiceStatus.LISTENING: "Voice: listening…",
    VoiceStatus.PROCESSING: "Voice: processing…",
    VoiceStatus.TRANSCRIPT_READY: "Voice: transcript ready",
    VoiceStatus.ERROR: "Voice: error",
}


class VoicePanel(QWidget):
    """Embedded local dictation panel (plain-text commit only, Alpha MVP)."""

    # Marshal controller callbacks (possibly off-thread) to the UI thread.
    _status_changed = Signal(str)
    _final_text = Signal(str)
    # Emitted by the panel's Hide button; the hosting window hides safely.
    hide_requested = Signal()

    def __init__(self, *, settings_get: Callable[[str], object] | None = None,
                 settings_set: Callable[[str, object], None] | None = None,
                 commit_target: EditorCommitTarget | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("voicePanel")
        self._settings_get = settings_get
        self._settings_set = settings_set
        self._commit = commit_target or EditorCommitTarget()
        self._controller = None
        self._status = VoiceStatus.OFF

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)

        top = QHBoxLayout()
        self._status_label = QLabel(_STATUS_TEXT[VoiceStatus.OFF])
        self._status_label.setObjectName("voiceStatusLabel")
        self._status_label.setStyleSheet("font-weight: bold;")
        top.addWidget(self._status_label, stretch=1)
        note = QLabel(PRIVACY_NOTE)
        note.setObjectName("voicePrivacyNote")
        note.setStyleSheet("color: #94a3b8; font-size: 11px;")
        top.addWidget(note)
        layout.addLayout(top)

        # -- Backend selector + contextual config (Local PC model path / LAN URL)
        cfg = QHBoxLayout()
        cfg.addWidget(QLabel("Backend:"))
        self._backend_combo = QComboBox()
        self._backend_combo.setObjectName("voiceBackendCombo")
        for value, label in _BACKEND_MODES:
            self._backend_combo.addItem(label, value)
        self._backend_combo.currentIndexChanged.connect(self._on_backend_changed)
        cfg.addWidget(self._backend_combo)
        self._config_edit = QLineEdit()
        self._config_edit.setObjectName("voiceConfigEdit")
        self._config_edit.editingFinished.connect(self._on_config_edited)
        cfg.addWidget(self._config_edit, stretch=1)
        self._lan_check_btn = QPushButton("Check LAN server")
        self._lan_check_btn.setObjectName("voiceLanCheck")
        self._lan_check_btn.clicked.connect(self._on_check_lan)
        cfg.addWidget(self._lan_check_btn)
        layout.addLayout(cfg)
        self._sync_backend_row()

        self._preview = QPlainTextEdit()
        self._preview.setObjectName("voiceTranscriptPreview")
        self._preview.setPlaceholderText(
            "Transcript preview — review, then Commit to the editor.")
        self._preview.setMinimumHeight(120)   # readable; grows with the window
        layout.addWidget(self._preview, stretch=1)

        row = QHBoxLayout()
        self._start_btn = QPushButton("Start")
        self._start_btn.setObjectName("voiceStart")
        self._start_btn.clicked.connect(self.start)
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("voiceStop")
        self._stop_btn.clicked.connect(self.stop)
        self._commit_btn = QPushButton("Commit to editor")
        self._commit_btn.setObjectName("voiceCommit")
        self._commit_btn.clicked.connect(self.commit)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setObjectName("voiceClear")
        self._clear_btn.clicked.connect(self.clear_preview)
        self._auto_commit = QCheckBox("Auto-commit after pause")
        self._auto_commit.setObjectName("voiceAutoCommit")
        self._hide_btn = QPushButton("Hide")
        self._hide_btn.setObjectName("voiceHide")
        self._hide_btn.clicked.connect(self.hide_requested.emit)
        for w in (self._start_btn, self._stop_btn, self._commit_btn,
                  self._clear_btn):
            row.addWidget(w)
        row.addWidget(self._auto_commit)
        row.addStretch()
        row.addWidget(self._hide_btn)
        layout.addLayout(row)

        self._status_changed.connect(self._apply_status_str)
        self._final_text.connect(self._apply_final_text)
        self._preview.textChanged.connect(self._refresh_buttons)

        self.setVisible(False)               # hidden until toggled / enabled
        self._apply_status(VoiceStatus.OFF)

    # -- settings / availability --------------------------------------------
    def _load_settings(self):
        from storyplanner.voice.types import VoiceSettings
        get = self._settings_get
        if get is None:
            from storyplanner.settings import get_manager
            get = get_manager().get
        return VoiceSettings.from_store(get)

    def is_enabled(self) -> bool:
        return bool(self._load_settings().enabled)

    def _store_set(self, key: str, value) -> None:
        setter = self._settings_set
        if setter is None:
            from storyplanner.settings import get_manager
            setter = get_manager().set
        setter(key, value)

    # -- backend selector / config row ----------------------------------------
    def _sync_backend_row(self) -> None:
        """Reflect the stored backend mode + contextual config field."""
        settings = self._load_settings()
        mode = (settings.backend_mode or "disabled").strip().lower()
        idx = next((i for i, (v, _l) in enumerate(_BACKEND_MODES) if v == mode), 0)
        self._backend_combo.blockSignals(True)
        self._backend_combo.setCurrentIndex(idx)
        self._backend_combo.blockSignals(False)
        if mode == "lan_server":
            self._config_edit.setVisible(True)
            self._lan_check_btn.setVisible(True)
            self._config_edit.setPlaceholderText(
                "LAN Whisper server URL (private address only, e.g. "
                "http://192.168.1.50:8000)")
            self._config_edit.setText(settings.lan_base_url)
            self._config_edit.setToolTip(
                "LAN mode sends audio only to the configured local network "
                "Whisper server. Do not use public URLs.")
        elif mode == "local_process":
            self._config_edit.setVisible(True)
            self._lan_check_btn.setVisible(False)
            self._config_edit.setPlaceholderText(
                "Local Whisper model path (no automatic downloads)")
            self._config_edit.setText(settings.model_path)
            self._config_edit.setToolTip(
                "Path to a local faster-whisper model directory.")
        else:
            self._config_edit.setVisible(False)
            self._lan_check_btn.setVisible(False)

    def _on_backend_changed(self, index: int) -> None:
        # Changing the backend mode mid-session must not leave the previous
        # backend recording: stop the active session safely first (finalizes a
        # valid pending segment; transcript stays uncommitted for review).
        if self._controller is not None and self._controller.status in (
                VoiceStatus.LISTENING, VoiceStatus.PROCESSING):
            self.stop()
        value = self._backend_combo.itemData(index) or "disabled"
        self._store_set("voice_backend_mode", value)
        self._sync_backend_row()

    def _on_config_edited(self) -> None:
        mode = self._backend_combo.currentData() or "disabled"
        text = self._config_edit.text().strip()
        if mode == "lan_server":
            self._store_set("voice_lan_base_url", text)
        elif mode == "local_process":
            self._store_set("voice_whisper_model_path", text)

    def _on_check_lan(self) -> None:
        from storyplanner.voice.lan_server import LanWhisperTranscriber
        settings = self._load_settings()
        ok, msg = LanWhisperTranscriber(settings).health_check()
        self._status_label.setText(msg)

    def _ensure_controller(self) -> tuple[bool, str]:
        settings = self._load_settings()
        if not settings.enabled:
            return (False, "Voice mode is off. Enable it in Settings.")
        from storyplanner.voice.recorder import build_recorder
        from storyplanner.voice.session import VoiceSessionController
        from storyplanner.voice.transcriber import build_transcriber
        recorder = build_recorder(settings)
        transcriber = build_transcriber(settings)
        self._controller = VoiceSessionController(
            settings, recorder, transcriber,
            on_status=lambda s: self._status_changed.emit(s.value),
            on_final_transcript=lambda seg: self._final_text.emit(seg.text))
        return self._controller.availability()

    # -- lifecycle -----------------------------------------------------------
    def toggle_panel(self) -> None:
        """Show/hide the panel widget itself (legacy/widget-level toggle).

        Hiding must always work — even with the feature flag off (the old
        behavior pinned the panel visible in that state, which is exactly the
        "panel never hides again" bug). The flag only controls whether the
        controls are live, never whether the panel can be dismissed.
        """
        if self.isVisible():
            self.setVisible(False)
            return
        self.sync_enabled_state()
        self.setVisible(True)

    def sync_enabled_state(self) -> None:
        """Reflect the feature flag: inert message when off, live when on."""
        if not self.is_enabled():
            self._apply_status(VoiceStatus.DISABLED)
            self._status_label.setText(
                "Voice mode is off — enable it in Settings.")
            self._set_controls_enabled(False)
        else:
            self._sync_backend_row()
            self._set_controls_enabled(True)
            self._refresh_buttons()

    def stop_if_active(self) -> None:
        """Hide/close policy (Alpha): stop a live session safely, keep the
        transcript preview. Never silently discards or auto-commits."""
        if self._controller is not None and self._controller.status in (
                VoiceStatus.LISTENING, VoiceStatus.PROCESSING):
            self.stop()

    def start(self) -> None:
        # Never create an overlapping session: if a controller is already
        # listening, keep it; otherwise stop/cleanup the previous one before
        # building a fresh controller (prevents an orphaned open mic stream).
        if self._controller is not None and self._controller.status in (
                VoiceStatus.LISTENING, VoiceStatus.PROCESSING):
            return
        self.stop_session()
        ok, msg = self._ensure_controller()
        if not ok:
            self._apply_status(VoiceStatus.DISABLED)
            self._status_label.setText(msg or SETUP_MESSAGE)
            return
        if self._controller.start_voice_session():
            self._apply_status(VoiceStatus.LISTENING)

    def stop(self) -> None:
        if self._controller is not None:
            self._controller.stop_voice_session()
        self._apply_status(VoiceStatus.OFF)

    def stop_session(self) -> None:
        """Safe stop for app close / project switch (no UI assumptions)."""
        try:
            if self._controller is not None:
                self._controller.stop_voice_session()
        except Exception:
            pass

    def commit(self) -> bool:
        text = self._preview.toPlainText()
        if not text.strip():
            self._status_label.setText("Voice: nothing to commit")
            return False
        ok = self._commit.insert_as_plain_text(text)
        if ok:
            self._status_label.setText("Voice: committed to editor")
        else:
            self._status_label.setText(
                "Voice: no active editor — click into the editor, then Commit")
        return ok

    def clear_preview(self) -> None:
        self._preview.clear()

    # -- slots (UI thread) ---------------------------------------------------
    def _apply_status_str(self, status_value: str) -> None:
        try:
            self._apply_status(VoiceStatus(status_value))
        except ValueError:
            pass

    def _apply_status(self, status: VoiceStatus) -> None:
        self._status = status
        self._status_label.setText(_STATUS_TEXT.get(status, "Voice"))
        self._refresh_buttons()

    def _apply_final_text(self, text: str) -> None:
        if not text:
            return
        existing = self._preview.toPlainText()
        self._preview.setPlainText((existing + " " + text).strip()
                                   if existing else text)
        if self._auto_commit.isChecked():
            self.commit()

    def _set_controls_enabled(self, enabled: bool) -> None:
        for w in (self._start_btn, self._stop_btn, self._commit_btn,
                  self._clear_btn, self._auto_commit):
            w.setEnabled(enabled)

    def _refresh_buttons(self) -> None:
        listening = self._status in (VoiceStatus.LISTENING,
                                     VoiceStatus.PROCESSING)
        self._start_btn.setEnabled(not listening)
        self._stop_btn.setEnabled(listening)
        self._commit_btn.setEnabled(bool(self._preview.toPlainText().strip()))
        self._clear_btn.setEnabled(bool(self._preview.toPlainText()))


class VoiceDictationWindow(QDialog):
    """Floating, modeless, resizable host for the Voice Dictation panel.

    Window-safety rules (the ones that keep this clear of the old
    standalone-Pages fullscreen-minimize bug):

    * always **parented to the main window** — never a parentless top-level
      window, no extra window flags, no ``Qt.Tool``;
    * **modeless** (shown with ``show()``, never ``exec()``) — writing in the
      main editor continues while it is open;
    * one instance, toggled show/hide; the title-bar close button, the
      panel's **Hide** button and **Esc** all *hide* it (state preserved —
      reopening shows the same transcript preview);
    * hiding while recording stops the session safely first and keeps the
      preview (never silently discards, never auto-commits);
    * never calls ``showMinimized``/``hide``/``close`` on the main window and
      never auto-shows at launch or auto-starts recording.
    """

    def __init__(self, panel: VoicePanel, parent: QWidget | None = None
                 ) -> None:
        super().__init__(parent)
        self.setObjectName("voiceDictationWindow")
        self.setWindowTitle("Voice Dictation (local)")
        self.setModal(False)
        self.setSizeGripEnabled(True)        # resizable, with a visible grip
        self.setMinimumSize(460, 280)
        self.resize(600, 340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self._panel = panel
        panel.setParent(self)
        panel.setVisible(True)               # visibility is window-level now
        layout.addWidget(panel)
        panel.hide_requested.connect(self.hide_safely)

    @property
    def panel(self) -> VoicePanel:
        return self._panel

    def toggle(self) -> None:
        """Single shared toggle for every entry point (menu / shortcut)."""
        if self.isVisible():
            self.hide_safely()
        else:
            self._panel.sync_enabled_state()
            self.show()
            self.raise_()

    def hide_safely(self) -> None:
        """Hide, stopping a live session first; transcript preview is kept."""
        self._panel.stop_if_active()
        self.hide()

    def reject(self) -> None:                # Esc while the window is focused
        self._panel.stop_if_active()
        super().reject()                     # modeless reject == hide

    def closeEvent(self, event) -> None:     # noqa: N802 (Qt signature)
        # Title-bar close hides (instance + transcript preserved, session
        # stopped safely) — it never destroys state or touches the parent.
        self._panel.stop_if_active()
        event.accept()
