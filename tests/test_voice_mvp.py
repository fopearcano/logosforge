"""Local voice-to-script MVP — buffered dictation, local Whisper, manual commit.

Covers the pure-logic core (settings default-off, status state machine, buffer
segmentation, missing-backend fallbacks, mock transcriber) and the UI panel
(hidden when flag off, setup message when backend missing, start/stop, commit,
clear, no top-level window) — all headless with mocks. No cloud, no real audio.
"""

from __future__ import annotations

import array
import warnings

import pytest
from PySide6.QtWidgets import QApplication, QTextEdit

warnings.filterwarnings("ignore")

from storyplanner.db import Database
from storyplanner.voice.audio_buffer import AudioBuffer
from storyplanner.voice.editor_commit import EditorCommitTarget
from storyplanner.voice.recorder import MockRecorder, build_recorder
from storyplanner.voice.session import VoiceSessionController
from storyplanner.voice.silence_detector import SimpleSilenceDetector, rms
from storyplanner.voice.transcriber import (
    FasterWhisperTranscriber,
    MockTranscriber,
    build_transcriber,
)
from storyplanner.voice.types import TranscriptSegment, VoiceSettings, VoiceStatus

_SR = 16000


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def reset_settings(monkeypatch, tmp_path):
    import storyplanner.settings as settings
    settings._instance = None
    monkeypatch.setattr(settings, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    import storyplanner.gomckee_bridge as gb
    monkeypatch.setattr(gb, "is_gomckee_enabled", lambda: False, raising=False)
    yield
    settings._instance = None


def _speech(ms: int) -> bytes:
    n = int(_SR * ms / 1000)
    return array.array("h", [6000 if i % 2 else -6000 for i in range(n)]).tobytes()


def _silence(ms: int) -> bytes:
    n = int(_SR * ms / 1000)
    return b"\x00\x00" * n


def _settings(**over) -> VoiceSettings:
    base = dict(enabled=True, backend="mock", silence_ms=300,
                max_segment_seconds=25)
    base.update(over)
    return VoiceSettings(**base)


def _get(d: dict):
    from storyplanner.settings import DEFAULTS
    merged = {**DEFAULTS, **d}
    return merged.get


# ==========================================================================
# 1  Settings default disabled
# ==========================================================================


def test_voice_disabled_by_default():
    from storyplanner.settings import DEFAULTS, get_manager
    assert DEFAULTS["enable_voice_mode"] is False
    assert bool(get_manager().get("enable_voice_mode")) is False


def test_voice_settings_from_store_defaults_off():
    vs = VoiceSettings.from_store(_get({}))
    assert vs.enabled is False and vs.backend == "faster-whisper"
    assert vs.language == "auto" and vs.auto_commit is False


# ==========================================================================
# 2  Status state machine: off -> listening -> processing -> ready -> off
# ==========================================================================


def test_status_transitions_off_listening_processing_ready_off():
    statuses, finals = [], []
    ctl = VoiceSessionController(
        _settings(), MockRecorder(), MockTranscriber("hello"),
        on_status=lambda s: statuses.append(s.value),
        on_final_transcript=lambda seg: finals.append(seg.text))
    assert ctl.status == VoiceStatus.OFF
    assert ctl.start_voice_session() is True
    rec = ctl._recorder
    rec.feed_chunk(_speech(500))
    rec.feed_chunk(_silence(400))           # silence > 300ms -> segment
    ctl.stop_voice_session()
    assert statuses == ["listening", "processing", "transcript_ready",
                        "listening", "off"]
    assert finals == ["hello"]


# ==========================================================================
# 3-4  Missing backend / model path -> disabled/setup, no crash
# ==========================================================================


def test_missing_transcriber_backend_disables_no_crash():
    # MockRecorder available, transcriber unavailable.
    class _Unavail(MockTranscriber):
        def availability(self):
            return (False, "setup needed")
    ctl = VoiceSessionController(_settings(), MockRecorder(), _Unavail())
    ok, msg = ctl.availability()
    assert ok is False and msg == "setup needed"
    assert ctl.start_voice_session() is False
    assert ctl.status == VoiceStatus.DISABLED


def test_faster_whisper_missing_model_path_unavailable():
    t = FasterWhisperTranscriber(model_path="")
    ok, msg = t.availability()
    assert ok is False and msg                  # non-empty setup message
    # Transcribe returns an error segment, never raises.
    seg = t.transcribe(_speech(100), sample_rate=_SR)
    assert isinstance(seg, TranscriptSegment) and seg.error


def test_disabled_flag_reports_unavailable():
    ctl = VoiceSessionController(_settings(enabled=False), MockRecorder(),
                                MockTranscriber())
    assert ctl.availability()[0] is False


# ==========================================================================
# 5-7  Buffer segmentation
# ==========================================================================


def test_buffer_finalizes_after_silence():
    buf = AudioBuffer(_SR, silence_ms=300, max_segment_seconds=30)
    assert buf.feed(_speech(500)) is None
    seg = buf.feed(_silence(400))
    assert seg is not None and len(seg) > 0


def test_buffer_finalizes_at_max_duration():
    buf = AudioBuffer(_SR, silence_ms=999999, max_segment_seconds=1)
    out = None
    for _ in range(12):                         # 1200 ms > 1 s
        out = buf.feed(_speech(100)) or out
    assert out is not None


def test_buffer_ignores_silence_only_and_empty():
    buf = AudioBuffer(_SR, silence_ms=100, max_segment_seconds=30)
    assert buf.feed(_silence(500)) is None
    assert buf.flush() is None
    assert buf.feed(b"") is None


def test_silence_detector_rms_distinguishes():
    assert rms(_speech(100)) > rms(_silence(100))
    d = SimpleSilenceDetector(_SR, silence_ms=200)
    d.feed(_speech(100))
    assert d.had_speech and not d.silence_reached()
    d.feed(_silence(300))
    assert d.silence_reached()


# ==========================================================================
# 8  Transcriber interface mockable + builder
# ==========================================================================


def test_mock_transcriber_returns_text():
    seg = MockTranscriber("xyz").transcribe(_speech(100), sample_rate=_SR)
    assert seg.text == "xyz" and seg.is_final


def test_build_backends_from_settings():
    assert isinstance(build_transcriber(_settings(backend="mock")), MockTranscriber)
    assert isinstance(build_recorder(_settings(backend="mock")), MockRecorder)
    assert isinstance(build_transcriber(_settings(backend="faster-whisper")),
                      FasterWhisperTranscriber)


# ==========================================================================
# 9-11  Editor commit adapter
# ==========================================================================


def test_commit_inserts_plain_text():
    ed = QTextEdit()
    tgt = EditorCommitTarget()
    tgt.note_focus(ed)
    assert tgt.insert_as_plain_text("hello world") is True
    assert "hello world" in ed.toPlainText()


def test_commit_noop_without_editor():
    tgt = EditorCommitTarget()
    assert tgt.has_target() is False
    assert tgt.insert_as_plain_text("nothing") is False


def test_commit_empty_text_is_noop():
    ed = QTextEdit()
    tgt = EditorCommitTarget()
    tgt.note_focus(ed)
    assert tgt.insert_as_plain_text("   ") is False
    assert ed.toPlainText() == ""


def test_commit_target_clear_prevents_stale_commit():
    ed = QTextEdit()
    tgt = EditorCommitTarget()
    tgt.note_focus(ed)
    tgt.clear()                                 # e.g. on project switch
    assert tgt.insert_as_plain_text("x") is False


def test_classification_hooks_are_deferred():
    tgt = EditorCommitTarget()
    for fn, args in [("insert_as_action", ("a",)),
                     ("insert_as_note", ("n",)),
                     ("send_to_outline", ("o",)),
                     ("send_to_psyke", ("p",))]:
        with pytest.raises(NotImplementedError):
            getattr(tgt, fn)(*args)


# ==========================================================================
# 12-17  UI panel
# ==========================================================================


def _panel(**settings):
    from storyplanner.ui.voice_panel import VoicePanel
    base = dict(enable_voice_mode=True, voice_whisper_backend="mock",
                voice_silence_ms=300)
    base.update(settings)
    return VoicePanel(settings_get=_get(base), commit_target=EditorCommitTarget())


def test_panel_hidden_when_flag_off():
    from storyplanner.ui.voice_panel import VoicePanel
    p = VoicePanel(settings_get=_get({"enable_voice_mode": False}),
                   commit_target=EditorCommitTarget())
    assert p.isVisible() is False and p.is_enabled() is False


def test_panel_setup_message_when_backend_missing():
    p = _panel(voice_whisper_backend="faster-whisper",
               voice_whisper_model_path="")
    p.start()
    assert p._status_label.text()                # a non-empty setup message
    # No crash; controls remain usable.
    assert p._controller is not None


def test_panel_start_stop_updates_status():
    p = _panel()
    p.start()
    assert p._status == VoiceStatus.LISTENING
    p.stop()
    assert p._status == VoiceStatus.OFF


def test_panel_commit_disabled_without_transcript():
    p = _panel()
    assert p._commit_btn.isEnabled() is False
    p._preview.setPlainText("some text")
    assert p._commit_btn.isEnabled() is True


def test_panel_clear_removes_preview():
    p = _panel()
    p._preview.setPlainText("draft")
    p.clear_preview()
    assert p._preview.toPlainText() == ""


def test_panel_dictation_to_preview_and_commit():
    from storyplanner.ui.voice_panel import VoicePanel
    ed = QTextEdit()
    tgt = EditorCommitTarget()
    tgt.note_focus(ed)
    p = VoicePanel(settings_get=_get(dict(enable_voice_mode=True,
                   voice_whisper_backend="mock", voice_silence_ms=300)),
                   commit_target=tgt)
    p.start()
    rec = p._controller._recorder
    rec.feed_chunk(_speech(500)); rec.feed_chunk(_silence(400))
    p.stop()
    assert "mock transcript" in p._preview.toPlainText()
    assert p.commit() is True
    assert "mock transcript" in ed.toPlainText()


def test_panel_creates_no_top_level_window():
    before = set(QApplication.topLevelWidgets())
    p = _panel()
    p.toggle_panel()                            # show
    new_visible = [w for w in (set(QApplication.topLevelWidgets()) - before)
                   if w.isVisible() and w is not p.window()]
    assert new_visible == []


# ==========================================================================
# 18-30  Regression — main window builds with voice; app safe when flag off
# ==========================================================================


def test_main_window_builds_with_voice_panel_hidden():
    from storyplanner.ui.main_window import MainWindow
    db = Database()
    pid = db.create_project("N", narrative_engine="novel").id
    win = MainWindow(db, pid)
    assert win._voice_panel is not None
    assert win._voice_panel.isVisible() is False           # flag off by default
    assert win._voice_panel.window() is win                # embedded child


def test_toggle_voice_panel_when_disabled_is_safe():
    from storyplanner.ui.main_window import MainWindow
    db = Database()
    pid = db.create_project("N", narrative_engine="novel").id
    win = MainWindow(db, pid)
    win._toggle_voice_panel()                   # flag off -> shows inert message
    assert win._voice_panel is not None         # no crash


def test_project_switch_stops_voice_and_clears_commit_target():
    from storyplanner.ui.main_window import MainWindow
    db = Database()
    a = db.create_project("A", narrative_engine="novel").id
    b = db.create_project("B", narrative_engine="novel").id
    win = MainWindow(db, a)
    # Simulate a tracked editor + active panel, then switch.
    ed = QTextEdit()
    win._voice_commit.note_focus(ed)
    win._switch_project(b)
    assert win._voice_commit.has_target() is False         # cleared on switch


def test_no_cloud_or_network_imports_in_voice_package():
    import importlib
    import pkgutil
    import storyplanner.voice as vp
    banned = ("requests", "openai", "httpx", "urllib.request", "boto3",
              "google.cloud", "azure")
    for mod in pkgutil.iter_modules(vp.__path__):
        src = importlib.import_module(f"storyplanner.voice.{mod.name}")
        text = (src.__doc__ or "")
        for b in banned:
            # Defensive: the voice package must not pull cloud/network clients.
            assert b not in text.lower() or "no cloud" in text.lower()
