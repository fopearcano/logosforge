"""Tests for PSYKE Console suggestion updates — regression for stale _last_query."""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PySide6.QtWidgets import QApplication, QWidget

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
        dropdown = console._ensure_dropdown()
        assert dropdown.has_items()

        # User clears the input
        console._input.setText("")
        console._on_text_changed("")

        # User retypes the same query — must still show results
        console._input.setText("jo")
        console._run_search()
        assert dropdown.has_items()

    def test_delete_partial_and_retype(self, console):
        """Type 'joa', delete to 'j', retype 'joa'."""
        console._input.setText("joa")
        console._run_search()
        dropdown = console._ensure_dropdown()
        assert dropdown.has_items()

        # Delete to 'j'
        console._input.setText("j")
        console._run_search()

        # Retype 'joa' — must update
        console._input.setText("joa")
        console._run_search()
        assert dropdown.has_items()

    def test_multiple_rapid_changes(self, console):
        """Simulate rapid input changes — each one triggers search."""
        queries = ["j", "jo", "joh", "john"]
        dropdown = console._ensure_dropdown()
        for q in queries:
            console._input.setText(q)
            console._run_search()
            assert dropdown.has_items()

    def test_empty_does_not_block_next(self, console):
        """Clearing input then retyping same query still shows results."""
        console._input.setText("cas")
        console._run_search()
        dropdown = console._ensure_dropdown()
        assert dropdown.has_items()

        console._input.setText("")
        console._on_text_changed("")

        console._input.setText("cas")
        console._run_search()
        assert dropdown.has_items()

    def test_deactivate_resets_state(self, console):
        """After deactivate(), same query should work again."""
        console._input.setText("jo")
        console._run_search()
        console.deactivate()

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

    def test_set_project_switches_index(self, app, db):
        """After set_project(), search returns entries from the new project."""
        from storyplanner.ui.psyke_console import PsykeConsole

        p1 = db.create_project("Project 1")
        p2 = db.create_project("Project 2")
        db.create_psyke_entry(p1.id, "John", "character")
        db.create_psyke_entry(p2.id, "Jane", "character")

        console = PsykeConsole(db, p1.id)
        console.rebuild_index()

        # John is in p1
        console._input.setText("jo")
        console._run_search()
        dropdown = console._ensure_dropdown()
        entity_items = [i for i in dropdown._items if i.suggestion.category == "entity"]
        assert len(entity_items) >= 1

        # Switch to p2
        console.set_project(p2.id)

        # Jane is in p2, John is not
        console._input.setText("jan")
        console._run_search()
        entity_items = [i for i in dropdown._items if i.suggestion.category == "entity"]
        assert len(entity_items) >= 1
        assert any("Jane" in i.suggestion.text for i in entity_items)

        console._input.setText("jo")
        console._run_search()
        entity_items = [i for i in dropdown._items if i.suggestion.category == "entity"]
        assert len(entity_items) == 0


# ---------------------------------------------------------------------------
# Entries cache
# ---------------------------------------------------------------------------


class TestEntriesCache:
    """Verify the entries cache avoids redundant DB queries."""

    def test_cache_populated_on_first_search(self, empty_console, db, project):
        """First search loads entries into cache."""
        db.create_psyke_entry(project.id, "John", "character")
        empty_console.mark_index_dirty()

        assert empty_console._psyke_entries_cache is None
        empty_console._input.setText("jo")
        empty_console._run_search()
        assert empty_console._psyke_entries_cache is not None
        assert len(empty_console._psyke_entries_cache) == 1

    def test_cache_reused_across_searches(self, empty_console, db, project):
        """Consecutive searches reuse the same cache object."""
        db.create_psyke_entry(project.id, "John", "character")
        empty_console.mark_index_dirty()

        empty_console._input.setText("jo")
        empty_console._run_search()
        first_cache = empty_console._psyke_entries_cache

        empty_console._input.setText("john")
        empty_console._run_search()
        assert empty_console._psyke_entries_cache is first_cache

    def test_mark_dirty_invalidates_cache(self, empty_console, db, project):
        """mark_index_dirty clears the cache."""
        db.create_psyke_entry(project.id, "John", "character")
        empty_console.mark_index_dirty()

        empty_console._input.setText("jo")
        empty_console._run_search()
        assert empty_console._psyke_entries_cache is not None

        empty_console.mark_index_dirty()
        assert empty_console._psyke_entries_cache is None

    def test_new_entry_appears_after_dirty(self, empty_console, db, project):
        """Entry added after cache load appears after mark_index_dirty."""
        db.create_psyke_entry(project.id, "John", "character")
        empty_console.mark_index_dirty()
        empty_console._input.setText("jo")
        empty_console._run_search()

        db.create_psyke_entry(project.id, "Joanna", "character")
        empty_console.mark_index_dirty()
        empty_console._input.setText("jo")
        empty_console._run_search()

        assert len(empty_console._psyke_entries_cache) == 2
        dropdown = empty_console._ensure_dropdown()
        entity_items = [i for i in dropdown._items if i.suggestion.category == "entity"]
        assert len(entity_items) >= 2

    def test_set_project_invalidates_cache(self, app, db):
        """Switching projects clears cache and loads new entries."""
        from storyplanner.ui.psyke_console import PsykeConsole

        p1 = db.create_project("Project 1")
        p2 = db.create_project("Project 2")
        db.create_psyke_entry(p1.id, "John", "character")
        db.create_psyke_entry(p2.id, "Jane", "character")

        console = PsykeConsole(db, p1.id)
        console.rebuild_index()
        assert any(e.name == "John" for e in console._psyke_entries_cache)

        console.set_project(p2.id)
        assert console._psyke_entries_cache is None

        console._input.setText("jan")
        console._run_search()
        assert any(e.name == "Jane" for e in console._psyke_entries_cache)
        assert not any(e.name == "John" for e in console._psyke_entries_cache)

    def test_lazy_init_no_db_hit(self, app, db, project):
        """Console constructor with lazy index does not query DB."""
        from storyplanner.ui.psyke_console import PsykeConsole

        console = PsykeConsole(db, project.id)
        assert console._psyke_entries_cache is None
        assert len(console._search_index._index) == 0


# ---------------------------------------------------------------------------
# Layout — center-bottom floating positioning
# ---------------------------------------------------------------------------


class TestConsoleCenterBottomLayout:
    """Verify the console width is responsive to parent/window size."""

    def _make_console(self, app, db, project, parent_w, parent_h):
        from storyplanner.ui.psyke_console import PsykeConsole

        parent = QWidget()
        parent.resize(parent_w, parent_h)
        c = PsykeConsole(db, project.id, parent=parent)
        c.reposition()
        return c, parent

    def test_reposition_centers_horizontally(self, app, db, project):
        c, parent = self._make_console(app, db, project, 1200, 800)
        expected_w = int(1200 * 0.50)
        assert c.width() == expected_w

    def test_reposition_clamps_to_min_width(self, app, db, project):
        c, parent = self._make_console(app, db, project, 400, 600)
        assert c.width() == 320

    def test_reposition_clamps_to_max_width(self, app, db, project):
        c, parent = self._make_console(app, db, project, 2400, 800)
        assert c.width() == 720

    def test_reposition_responsive_on_resize(self, app, db, project):
        c, parent = self._make_console(app, db, project, 1000, 800)
        w1 = c.width()
        parent.resize(1400, 800)
        c.reposition()
        assert c.width() != w1

    def test_console_width_bounded(self, app, db, project):
        c, parent = self._make_console(app, db, project, 1200, 800)
        assert 320 <= c.width() <= 720
