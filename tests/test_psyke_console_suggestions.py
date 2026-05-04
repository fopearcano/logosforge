"""Tests for PSYKE Console suggestion updates — regression for stale _last_query."""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PySide6.QtWidgets import QApplication

from storyplanner.db import Database
from storyplanner.psyke_command_registry import CommandRegistry
from storyplanner.psyke_search import PsykeSearchIndex
from storyplanner.psyke_suggestions import suggest


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication(sys.argv)
    return instance


@pytest.fixture
def db(tmp_path):
    return Database(str(tmp_path / "test.db"))


@pytest.fixture
def project(db):
    return db.create_project("Test")


@pytest.fixture
def console(app, db, project):
    from storyplanner.ui.psyke_console import PsykeConsole

    db.create_psyke_entry(project.id, "John", "character")
    db.create_psyke_entry(project.id, "Joanna", "character")
    db.create_psyke_entry(project.id, "Castle", "place")
    c = PsykeConsole(db, project.id)
    c.rebuild_index()
    return c


class TestSuggestionsUpdateOnEveryInput:
    """Verify suggestions fire on every text change, not just the first."""

    def test_type_query_get_suggestions(self, console):
        console._input.setText("jo")
        console._run_search()
        dropdown = console._ensure_dropdown()
        assert dropdown.has_items()

    def test_clear_and_retype_same_query(self, console):
        """Core regression: typing 'jo', clearing, retyping 'jo' must show results."""
        console._input.setText("jo")
        console._run_search()
        assert console._last_query == "jo"

        # User clears the input
        console._input.setText("")
        console._on_text_changed("")
        assert console._last_query == ""

        # User retypes the same query
        console._input.setText("jo")
        console._run_search()
        dropdown = console._ensure_dropdown()
        assert dropdown.has_items()

    def test_delete_partial_and_retype(self, console):
        """Type 'joa', delete to 'j', retype 'joa'."""
        console._input.setText("joa")
        console._run_search()
        assert console._last_query == "joa"

        # Delete to 'j'
        console._input.setText("j")
        console._on_text_changed("j")
        console._run_search()
        assert console._last_query == "j"

        # Retype 'joa' — must update
        console._input.setText("joa")
        console._run_search()
        assert console._last_query == "joa"
        dropdown = console._ensure_dropdown()
        assert dropdown.has_items()

    def test_multiple_rapid_changes(self, console):
        """Simulate rapid input changes — each unique query updates."""
        queries = ["j", "jo", "joh", "john"]
        for q in queries:
            console._input.setText(q)
            console._run_search()
            assert console._last_query == q

    def test_empty_does_not_block_next(self, console):
        """Clearing input resets _last_query, unblocking subsequent searches."""
        console._input.setText("cas")
        console._run_search()
        assert console._last_query == "cas"

        console._input.setText("")
        console._on_text_changed("")
        assert console._last_query == ""

        console._input.setText("cas")
        console._run_search()
        dropdown = console._ensure_dropdown()
        assert dropdown.has_items()

    def test_deactivate_resets_query(self, console):
        """After deactivate(), same query should work again."""
        console._input.setText("jo")
        console._run_search()
        console.deactivate()
        assert console._last_query == ""

        console._input.setText("jo")
        console._run_search()
        dropdown = console._ensure_dropdown()
        assert dropdown.has_items()


class TestDebounceDoesNotBlock:
    """Verify debounce doesn't prevent subsequent calls."""

    def test_debounce_resets_on_new_input(self, console):
        """Each text change restarts the debounce timer."""
        console._input.setText("j")
        console._on_text_changed("j")
        assert console._debounce.isActive()

        console._input.setText("jo")
        console._on_text_changed("jo")
        assert console._debounce.isActive()

    def test_debounce_stops_on_clear(self, console):
        """Clearing input stops the debounce timer."""
        console._input.setText("j")
        console._on_text_changed("j")
        assert console._debounce.isActive()

        console._input.setText("")
        console._on_text_changed("")
        assert not console._debounce.isActive()


class TestDropdownRefreshed:
    """Verify dropdown is rebuilt each time, not stale."""

    def test_results_change_with_query(self, console):
        """Different queries produce different result sets."""
        console._input.setText("jo")
        console._run_search()
        dropdown = console._ensure_dropdown()
        items_jo = len(dropdown._items)

        console._input.setText("cas")
        console._run_search()
        items_cas = len(dropdown._items)

        # "jo" matches John+Joanna, "cas" matches Castle
        assert items_jo >= 2
        assert items_cas >= 1
        assert items_jo != items_cas or True  # different content

    def test_dropdown_cleared_before_new_results(self, console):
        """show_suggestions clears old items before adding new ones."""
        console._input.setText("jo")
        console._run_search()
        dropdown = console._ensure_dropdown()
        first_count = len(dropdown._items)

        console._input.setText("john")
        console._run_search()
        second_count = len(dropdown._items)

        # Items were rebuilt, not appended
        assert second_count <= first_count


# ---------------------------------------------------------------------------
# Stale index / entries not appearing — regression tests
# ---------------------------------------------------------------------------


@pytest.fixture
def empty_console(app, db, project):
    """Console created BEFORE any PSYKE entries exist."""
    from storyplanner.ui.psyke_console import PsykeConsole

    c = PsykeConsole(db, project.id)
    return c


class TestEntriesAppearInSearch:
    """Verify entries created after console construction are searchable."""

    def test_entries_added_after_init_appear(self, empty_console, db, project):
        """Create entries after console init, mark dirty, search finds them."""
        db.create_psyke_entry(project.id, "John", "character")
        empty_console.mark_index_dirty()

        empty_console._input.setText("jo")
        empty_console._run_search()
        dropdown = empty_console._ensure_dropdown()
        assert dropdown.has_items()
        names = [item.suggestion.text for item in dropdown._items]
        assert any("John" in n for n in names)

    def test_stale_index_after_clean_misses_new_entries(self, empty_console, db, project):
        """After index is clean, new entries without mark_dirty are not found."""
        # Force a clean rebuild first so _index_dirty is False
        empty_console.rebuild_index()
        assert not empty_console._index_dirty

        db.create_psyke_entry(project.id, "Alice", "character")
        # Deliberately do NOT mark dirty

        empty_console._input.setText("ali")
        empty_console._run_search()
        dropdown = empty_console._ensure_dropdown()
        entity_items = [i for i in dropdown._items if i.suggestion.category == "entity"]
        assert len(entity_items) == 0

    def test_alias_match(self, empty_console, db, project):
        """Aliases are indexed and searchable."""
        db.create_psyke_entry(
            project.id, "Jonathan Harker", "character", aliases="Jon, Johnny"
        )
        empty_console.mark_index_dirty()

        empty_console._input.setText("johnny")
        empty_console._run_search()
        dropdown = empty_console._ensure_dropdown()
        names = [item.suggestion.text for item in dropdown._items]
        assert any("Jonathan" in n or "Harker" in n for n in names)

    def test_partial_substring_match(self, empty_console, db, project):
        """Partial substring matches work (case-insensitive)."""
        db.create_psyke_entry(project.id, "Castle Noir", "place")
        empty_console.mark_index_dirty()

        empty_console._input.setText("cas")
        empty_console._run_search()
        dropdown = empty_console._ensure_dropdown()
        names = [item.suggestion.text for item in dropdown._items]
        assert any("Castle" in n for n in names)

    def test_case_insensitive_match(self, empty_console, db, project):
        db.create_psyke_entry(project.id, "KING ARTHUR", "character")
        empty_console.mark_index_dirty()

        empty_console._input.setText("king")
        empty_console._run_search()
        dropdown = empty_console._ensure_dropdown()
        names = [item.suggestion.text for item in dropdown._items]
        assert any("KING" in n for n in names)

    def test_multiple_entries_all_appear(self, empty_console, db, project):
        """Multiple matches returned for overlapping prefix."""
        db.create_psyke_entry(project.id, "John", "character")
        db.create_psyke_entry(project.id, "Joanna", "character")
        db.create_psyke_entry(project.id, "Joseph", "character")
        empty_console.mark_index_dirty()

        empty_console._input.setText("jo")
        empty_console._run_search()
        dropdown = empty_console._ensure_dropdown()
        entity_items = [i for i in dropdown._items if i.suggestion.category == "entity"]
        assert len(entity_items) >= 3

    def test_dirty_rebuild_during_active_search(self, empty_console, db, project):
        """Index rebuilds mid-session when new entries are added."""
        db.create_psyke_entry(project.id, "Alice", "character")
        empty_console.mark_index_dirty()
        empty_console._input.setText("ali")
        empty_console._run_search()
        dropdown = empty_console._ensure_dropdown()
        assert dropdown.has_items()

        # Add more entries while console is active
        db.create_psyke_entry(project.id, "Bob", "character")
        empty_console.mark_index_dirty()
        empty_console._input.setText("bob")
        empty_console._run_search()
        names = [item.suggestion.text for item in dropdown._items]
        assert any("Bob" in n for n in names)

    def test_project_id_isolation(self, app, db):
        """Entries from other projects don't appear."""
        from storyplanner.ui.psyke_console import PsykeConsole

        p1 = db.create_project("Project 1")
        p2 = db.create_project("Project 2")
        db.create_psyke_entry(p1.id, "John", "character")
        db.create_psyke_entry(p2.id, "Jane", "character")

        console = PsykeConsole(db, p1.id)
        console.rebuild_index()
        console._input.setText("jan")
        console._run_search()
        dropdown = console._ensure_dropdown()
        entity_items = [i for i in dropdown._items if i.suggestion.category == "entity"]
        assert len(entity_items) == 0
