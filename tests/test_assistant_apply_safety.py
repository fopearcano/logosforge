"""Assistant apply-safety enforcement in the live panel.

Invalid output (planning leak / secret) is never shown as usable and Apply is
disabled — for cached responses too. Valid direct content enables Apply.
"""

import pytest

from storyplanner.assistant_contract import route
from storyplanner.db import Database
from storyplanner.ui.main_window import MainWindow

BAD = ("### Suggested Scene Structure\n- [INTRODUCING] x\n- y\n- z\n\n"
       "## Production Notes\nKey Questions to Explore:\nLet me craft this.")
SECRET = "Use api_key: sk-deadbeef12345678 then save clip.wav."
GOOD = "MILO VOSS\nIt was not open when I arrived.\n\nADA NORTH\nThen someone lied."


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


def _panel(engine="screenplay"):
    db = Database()
    pid = db.create_project("P", narrative_engine=engine).id
    db.create_scene(pid, "S1", content="INT. ARCHIVE - DAWN", act="Act I")
    win = MainWindow(db, pid)
    panel = win._assistant_panel
    panel._active_section = "Manuscript"
    panel._task_contract = route(
        section="Manuscript", writing_mode=engine, action="Dialogue")
    return win, panel


def test_invalid_output_blocks_apply():
    _win, panel = _panel()
    panel._on_response(BAD, False)
    assert panel._response_valid is False
    assert panel._get_response_text() is None          # central apply guard
    assert panel._replace_content_btn.isEnabled() is False
    assert panel._insert_cursor_btn.isEnabled() is False
    assert panel._append_btn.isEnabled() is False


def test_invalid_cached_output_also_blocked():
    _win, panel = _panel()
    panel._on_response(BAD, True)                       # from_cache=True
    assert panel._response_valid is False
    assert panel._get_response_text() is None


def test_secret_output_withheld():
    _win, panel = _panel("novel")
    panel._on_response(SECRET, False)
    shown = panel._response_output.toPlainText()
    assert "sk-deadbeef" not in shown                   # never displayed
    assert panel._response_valid is False
    assert panel._get_response_text() is None


def test_valid_direct_output_enables_apply():
    _win, panel = _panel()
    panel._on_response(GOOD, False)
    assert panel._response_valid is True
    assert panel._get_response_text() is not None
    assert panel._replace_content_btn.isEnabled() is True
    assert panel._copy_btn.isEnabled() is True


def test_apply_handler_guard_blocks_invalid(monkeypatch):
    _win, panel = _panel()
    panel._on_response(BAD, False)
    # Even if a handler is invoked directly, the central guard blocks it.
    calls = {"n": 0}
    monkeypatch.setattr(panel, "_notify_data_changed",
                        lambda: calls.__setitem__("n", calls["n"] + 1))
    panel._apply_replace()
    panel._apply_insert()
    panel._apply_append()
    assert calls["n"] == 0                              # nothing applied
