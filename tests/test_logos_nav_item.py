"""Tests for the left-panel 'Logos' navigation item (navigation wiring fix)."""

import pytest

from storyplanner.db import Database
from storyplanner.ui.main_window import MainWindow
from storyplanner.ui.logos.logos_view import LogosView


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


def _win(mode="novel"):
    db = Database()
    pid = db.create_project("Test", narrative_engine=mode).id
    db.create_scene(pid, "S1", content="Alice stood in the Kitchen.",
                    location="Kitchen")
    return db, pid, MainWindow(db, pid)


# ==========================================================================
# Presence / registration
# ==========================================================================


def test_logos_item_present_in_sidebar():
    db, pid, win = _win()
    assert "Logos" in win.sidebar_buttons


def test_logos_item_near_assistant_in_ai_cluster():
    # Logos sits in the trailing AI cluster, directly after Assistant.
    db, pid, win = _win()
    assert "Assistant" in win.sidebar_buttons
    assert "Chat" in win.sidebar_buttons
    assert "Logos" in win.sidebar_buttons


def test_logos_registered_as_nav_section():
    db, pid, win = _win()
    assert "Logos" in win._nav_labels
    assert "Logos" in win._nav_section_handlers
    assert win.sidebar_buttons["Logos"].isCheckable()


def test_logos_item_not_duplicated():
    db, pid, win = _win()
    # exactly one nav-label entry and one handler entry
    assert win._nav_labels.count("Logos") == 1
    assert list(win._nav_section_handlers).count("Logos") == 1


def test_assistant_remains_a_toggle_not_a_section():
    db, pid, win = _win()
    # Adding Logos must not turn Assistant into a checkable section.
    assert "Assistant" in win.sidebar_buttons
    assert "Assistant" not in win._nav_labels


# ==========================================================================
# Click opens the Logos view + highlight
# ==========================================================================


def test_clicking_logos_opens_logos_view():
    db, pid, win = _win()
    win.sidebar_buttons["Logos"].click()
    assert win._current_section == "Logos"
    assert isinstance(win.content_area, LogosView)


def test_logos_highlight_works():
    db, pid, win = _win()
    win.sidebar_buttons["Logos"].click()
    assert win.sidebar_buttons["Logos"].isChecked() is True


def test_logos_highlight_is_exclusive():
    db, pid, win = _win()
    win.sidebar_buttons["Logos"].click()
    win.sidebar_buttons["Chat"].click()
    assert win.sidebar_buttons["Logos"].isChecked() is False
    assert win.sidebar_buttons["Chat"].isChecked() is True


# ==========================================================================
# Existing navigation still works
# ==========================================================================


def test_chat_navigation_still_works():
    db, pid, win = _win()
    from storyplanner.ui.chat_view import ChatView
    win.sidebar_buttons["Chat"].click()
    assert win._current_section == "Chat"
    assert isinstance(win.content_area, ChatView)


def test_assistant_toggle_still_works():
    db, pid, win = _win()
    # Clicking Assistant toggles the panel; it must not raise and must not
    # become the active section.
    win.sidebar_buttons["Assistant"].click()
    assert win._current_section != "Assistant"


def test_psyke_navigation_still_works():
    db, pid, win = _win()
    win.sidebar_buttons["PSYKE"].click()
    assert win._current_section == "PSYKE"


# ==========================================================================
# View content + reuse (no second Logos system)
# ==========================================================================


def test_logos_view_reuses_existing_controller():
    db, pid, win = _win()
    win.sidebar_buttons["Logos"].click()
    # The view uses the MainWindow's single LogosController instance.
    assert win.content_area._controller is win._logos_controller


def test_logos_view_lists_actions_for_a_section():
    db, pid, win = _win()
    win.sidebar_buttons["Logos"].click()
    # status text mentions the section + action count
    assert "action(s) available" in win.content_area._status.text()


def test_logos_view_empty_state_without_project():
    db = Database()
    view = LogosView(db, None, controller=None)
    assert "No project loaded" in view._status.text()


# ==========================================================================
# Project switch / data change clears stale state
# ==========================================================================


def test_project_switch_rebuilds_logos_view():
    db, pid, win = _win()
    win.sidebar_buttons["Logos"].click()
    first_view = win.content_area
    pid2 = db.create_project("Second", narrative_engine="novel").id
    win._switch_project(pid2)
    # The active Logos section is rebuilt for the new project.
    assert win._current_section == "Logos"
    assert isinstance(win.content_area, LogosView)
    assert win.content_area is not first_view
    assert win.content_area._project_id == pid2


def test_logos_view_refresh_after_data_change():
    db, pid, win = _win()
    win.sidebar_buttons["Logos"].click()
    # _on_data_changed refreshes the active view; must not raise.
    win._on_data_changed()
    assert isinstance(win.content_area, LogosView)


def test_logos_set_project_clears_stale():
    db, pid, win = _win()
    win.sidebar_buttons["Logos"].click()
    view = win.content_area
    pid2 = db.create_project("Other", narrative_engine="novel").id
    view.set_project(pid2)
    assert view._project_id == pid2


# ==========================================================================
# Collapsed sidebar alignment
# ==========================================================================


def test_collapsed_sidebar_logos_icon_text():
    db, pid, win = _win()
    btn = win.sidebar_buttons["Logos"]
    btn.set_collapsed(True)
    # Collapsed: icon-only text, label in tooltip — same contract as other
    # standalone items (no indent centering glitch).
    assert btn.text() == btn._icon_text
    assert btn.toolTip() == "Logos"
    btn.set_collapsed(False)
    assert "Logos" in btn.text()


def test_collapsed_logos_matches_other_standalone_items():
    db, pid, win = _win()
    logos, psyke = win.sidebar_buttons["Logos"], win.sidebar_buttons["PSYKE"]
    logos.set_collapsed(True)
    psyke.set_collapsed(True)
    # Both standalone items render icon-only with no leading indent spaces.
    assert logos.text() == logos._icon_text
    assert psyke.text() == psyke._icon_text
    assert not logos.text().startswith(" ")
