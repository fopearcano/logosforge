"""Tests for the Narrative Dashboard — data computation, widgets, and view."""

from storyplanner.db import Database
from storyplanner.narrative_dashboard import (
    NarrativeDashboardData,
    SceneTension,
    TensionCurve,
    CharacterPresence,
    StructureDistribution,
    ThemePresence,
    compute_dashboard,
)
from storyplanner.ui.dashboard_widgets import (
    CharacterPresencePanel,
    StructurePanel,
    TensionCurvePanel,
    ThemeContinuityPanel,
)
from storyplanner.ui.narrative_dashboard_view import NarrativeDashboardView


# -- Helpers -------------------------------------------------------------------

def _small_project(db: Database):
    """Project with 3 scenes, 2 characters, 1 theme, 1 relation, 1 progression."""
    proj = db.create_project("Novel")
    s1 = db.create_scene(
        proj.id, "Opening",
        content="Alice screamed at Bob across the room. The danger was real.",
        act="Act One", chapter="Chapter 1",
    )
    s2 = db.create_scene(
        proj.id, "Rising",
        content="Bob fled from the house. Alice pursued him through the rain.",
        act="Act One", chapter="Chapter 1",
    )
    s3 = db.create_scene(
        proj.id, "Climax",
        content="Alice confronted Bob. The betrayal was revealed and death followed.",
        act="Act Two", chapter="Chapter 2",
    )
    e_alice = db.create_psyke_entry(proj.id, "Alice", entry_type="character")
    e_bob = db.create_psyke_entry(proj.id, "Bob", entry_type="character")
    e_theme = db.create_psyke_entry(proj.id, "Trust", entry_type="theme")
    db.add_psyke_relation(e_alice.id, e_bob.id)
    db.create_psyke_progression(e_alice.id, "Grew suspicious", scene_id=s2.id)
    return proj, s1, s2, s3, e_alice, e_bob, e_theme


def _large_project(db: Database):
    """Project with 8 scenes across 3 acts, 3 characters, 2 themes."""
    proj = db.create_project("Epic")
    scenes = []
    acts_chaps = [
        ("Act One", "Chapter 1"), ("Act One", "Chapter 1"),
        ("Act Two", "Chapter 2"), ("Act Two", "Chapter 2"),
        ("Act Two", "Chapter 3"), ("Act Two", "Chapter 3"),
        ("Act Three", "Chapter 4"), ("Act Three", "Chapter 4"),
    ]
    contents = [
        "Alice walked into the tavern. All eyes turned to her.",
        "Bob was waiting at the corner table. He nodded.",
        "Alice and Bob met Carol at the bridge. Danger approached.",
        "Carol screamed as the battle began. Alice fought bravely.",
        "Bob escaped through the forest. He realized the truth.",
        "The secret was revealed. Alice felt rage.",
        "Carol led them to the mountain. Bob mourned the loss.",
        "Alice sacrificed everything. The war ended in silence.",
    ]
    for i, ((act, chap), content) in enumerate(zip(acts_chaps, contents)):
        s = db.create_scene(
            proj.id, f"Scene {i+1}", content=content, act=act, chapter=chap,
        )
        scenes.append(s)
    a = db.create_psyke_entry(proj.id, "Alice", entry_type="character")
    b = db.create_psyke_entry(proj.id, "Bob", entry_type="character")
    c = db.create_psyke_entry(proj.id, "Carol", entry_type="character")
    t1 = db.create_psyke_entry(proj.id, "Trust", entry_type="theme")
    t2 = db.create_psyke_entry(proj.id, "Sacrifice", entry_type="theme")
    db.add_psyke_relation(a.id, b.id)
    db.add_psyke_relation(a.id, c.id)
    db.create_psyke_progression(a.id, "Grew determined", scene_id=scenes[3].id)
    db.create_psyke_progression(b.id, "Lost hope", scene_id=scenes[5].id)
    return proj, scenes, a, b, c, t1, t2


# ===========================================================================
# TENSION CURVE — data computation
# ===========================================================================

def test_tension_curve_has_one_point_per_scene():
    db = Database()
    proj, s1, s2, s3, *_ = _small_project(db)
    data = compute_dashboard(db, proj.id)
    assert len(data.tension.points) == 3


def test_tension_scores_are_non_negative():
    db = Database()
    proj, *_ = _small_project(db)
    data = compute_dashboard(db, proj.id)
    for p in data.tension.points:
        assert p.score >= 0


def test_tension_score_max_100():
    db = Database()
    proj, *_ = _small_project(db)
    data = compute_dashboard(db, proj.id)
    for p in data.tension.points:
        assert p.score <= 100


def test_tension_keywords_increase_score():
    db = Database()
    proj = db.create_project("K")
    db.create_scene(proj.id, "A", content="They sat quietly.")
    db.create_scene(proj.id, "B", content="Fight death betrayal scream rage!")
    data = compute_dashboard(db, proj.id)
    assert data.tension.points[1].score > data.tension.points[0].score


def test_tension_chars_increase_score():
    db = Database()
    proj = db.create_project("K")
    db.create_scene(proj.id, "A", content="The wind blew.")
    db.create_scene(proj.id, "B", content="Alice and Bob argued.")
    db.create_psyke_entry(proj.id, "Alice", entry_type="character")
    db.create_psyke_entry(proj.id, "Bob", entry_type="character")
    data = compute_dashboard(db, proj.id)
    assert data.tension.points[1].char_count == 2
    assert data.tension.points[0].char_count == 0


def test_tension_progression_increases_score():
    db = Database()
    proj = db.create_project("K")
    s1 = db.create_scene(proj.id, "A", content="Alice waited.")
    s2 = db.create_scene(proj.id, "B", content="Alice waited again.")
    e = db.create_psyke_entry(proj.id, "Alice", entry_type="character")
    db.create_psyke_progression(e.id, "Grew tired", scene_id=s2.id)
    data = compute_dashboard(db, proj.id)
    assert data.tension.points[1].progression_count == 1
    assert data.tension.points[0].progression_count == 0


def test_tension_flat_flag():
    db = Database()
    proj = db.create_project("K")
    for i in range(5):
        db.create_scene(proj.id, f"S{i}", content="Quiet day.")
    data = compute_dashboard(db, proj.id)
    flat_flags = [f for f in data.tension.flags if "Flat" in f]
    assert len(flat_flags) >= 1


def test_tension_weak_buildup_flag():
    db = Database()
    proj = db.create_project("K")
    for i in range(6):
        db.create_scene(proj.id, f"S{i}", content="Nothing happened.")
    data = compute_dashboard(db, proj.id)
    weak = [f for f in data.tension.flags if "Weak buildup" in f]
    assert len(weak) >= 1


# ===========================================================================
# CHARACTER PRESENCE
# ===========================================================================

def test_character_presence_entries():
    db = Database()
    proj, s1, s2, s3, alice, bob, _ = _small_project(db)
    data = compute_dashboard(db, proj.id)
    assert len(data.characters) == 2
    names = {c.name for c in data.characters}
    assert "Alice" in names
    assert "Bob" in names


def test_character_presence_scenes():
    db = Database()
    proj, *_ = _small_project(db)
    data = compute_dashboard(db, proj.id)
    alice = next(c for c in data.characters if c.name == "Alice")
    assert len(alice.present_scenes) >= 2


def test_character_over_dominant_flag():
    db = Database()
    proj = db.create_project("K")
    for i in range(5):
        db.create_scene(proj.id, f"S{i}", content="Alice talks. Alice walks.")
    db.create_psyke_entry(proj.id, "Alice", entry_type="character")
    data = compute_dashboard(db, proj.id)
    alice = data.characters[0]
    assert any("Over-dominant" in f for f in alice.flags)


def test_character_absence_flag():
    db = Database()
    proj = db.create_project("K")
    db.create_scene(proj.id, "S0", content="Alice walked.")
    for i in range(4):
        db.create_scene(proj.id, f"S{i+1}", content="Empty scene.")
    db.create_scene(proj.id, "S5", content="Alice returned.")
    db.create_psyke_entry(proj.id, "Alice", entry_type="character")
    data = compute_dashboard(db, proj.id)
    alice = data.characters[0]
    assert any("Absent" in f for f in alice.flags)


def test_character_total_scenes():
    db = Database()
    proj, *_ = _small_project(db)
    data = compute_dashboard(db, proj.id)
    for cp in data.characters:
        assert cp.total_scenes == 3


# ===========================================================================
# ACT / STRUCTURE DISTRIBUTION
# ===========================================================================

def test_structure_segments_from_acts():
    db = Database()
    proj, *_ = _small_project(db)
    data = compute_dashboard(db, proj.id)
    labels = [s.label for s in data.structure.segments]
    assert "Act One" in labels
    assert "Act Two" in labels


def test_structure_segment_word_counts_positive():
    db = Database()
    proj, *_ = _small_project(db)
    data = compute_dashboard(db, proj.id)
    for seg in data.structure.segments:
        assert seg.word_count > 0


def test_structure_total_scenes():
    db = Database()
    proj, *_ = _small_project(db)
    data = compute_dashboard(db, proj.id)
    assert data.structure.total_scenes == 3


def test_structure_infers_3_acts_without_labels():
    db = Database()
    proj = db.create_project("Plain")
    for i in range(8):
        db.create_scene(proj.id, f"S{i}", content="Some text goes here.")
    data = compute_dashboard(db, proj.id)
    labels = [s.label for s in data.structure.segments]
    assert any("Act 1" in l for l in labels)
    assert any("Act 2" in l for l in labels)
    assert any("Act 3" in l for l in labels)


def test_structure_empty_project():
    db = Database()
    proj = db.create_project("Empty")
    data = compute_dashboard(db, proj.id)
    assert data.structure.total_scenes == 0
    assert data.structure.segments == []


def test_structure_weak_middle_flag():
    db = Database()
    proj = db.create_project("Imbalanced")
    db.create_scene(
        proj.id, "S1", content="Long opening " * 50, act="Act 1",
    )
    db.create_scene(
        proj.id, "S2", content="Short.", act="Act 2",
    )
    db.create_scene(
        proj.id, "S3", content="Long ending " * 50, act="Act 3",
    )
    data = compute_dashboard(db, proj.id)
    assert any("Weak" in f for f in data.structure.flags)


# ===========================================================================
# THEME CONTINUITY
# ===========================================================================

def test_theme_presence_entries():
    db = Database()
    proj, *_ = _small_project(db)
    data = compute_dashboard(db, proj.id)
    assert len(data.themes) == 1
    assert data.themes[0].name == "Trust"


def test_theme_present_in_scenes():
    db = Database()
    proj = db.create_project("K")
    db.create_scene(proj.id, "A", content="Trust was everything.")
    db.create_scene(proj.id, "B", content="Nothing here.")
    db.create_scene(proj.id, "C", content="Trust returned.")
    db.create_psyke_entry(proj.id, "Trust", entry_type="theme")
    data = compute_dashboard(db, proj.id)
    trust = data.themes[0]
    assert len(trust.present_scenes) == 2


def test_theme_underused_flag():
    db = Database()
    proj = db.create_project("K")
    for i in range(10):
        content = "Trust matters." if i == 0 else "Nothing here."
        db.create_scene(proj.id, f"S{i}", content=content)
    db.create_psyke_entry(proj.id, "Trust", entry_type="theme")
    data = compute_dashboard(db, proj.id)
    trust = data.themes[0]
    assert any("Underused" in f for f in trust.flags)


def test_theme_disappears_flag():
    db = Database()
    proj = db.create_project("K")
    db.create_scene(proj.id, "S0", content="Trust was key.")
    for i in range(4):
        db.create_scene(proj.id, f"S{i+1}", content="Nothing.")
    db.create_scene(proj.id, "S5", content="Trust again.")
    db.create_psyke_entry(proj.id, "Trust", entry_type="theme")
    data = compute_dashboard(db, proj.id)
    trust = data.themes[0]
    assert any("Disappears" in f for f in trust.flags)


def test_no_theme_entries_yields_empty():
    db = Database()
    proj = db.create_project("K")
    db.create_scene(proj.id, "A", content="Hello world.")
    data = compute_dashboard(db, proj.id)
    assert data.themes == []


# ===========================================================================
# LARGE PROJECT
# ===========================================================================

def test_large_project_tension_curve_length():
    db = Database()
    proj, scenes, *_ = _large_project(db)
    data = compute_dashboard(db, proj.id)
    assert len(data.tension.points) == 8


def test_large_project_character_count():
    db = Database()
    proj, scenes, a, b, c, *_ = _large_project(db)
    data = compute_dashboard(db, proj.id)
    assert len(data.characters) == 3


def test_large_project_theme_count():
    db = Database()
    proj, scenes, *_, t1, t2 = _large_project(db)
    data = compute_dashboard(db, proj.id)
    assert len(data.themes) == 2


def test_large_project_structure_segments():
    db = Database()
    proj, *_ = _large_project(db)
    data = compute_dashboard(db, proj.id)
    labels = {s.label for s in data.structure.segments}
    assert "Act One" in labels
    assert "Act Two" in labels
    assert "Act Three" in labels


def test_large_project_tension_has_variety():
    db = Database()
    proj, *_ = _large_project(db)
    data = compute_dashboard(db, proj.id)
    scores = [p.score for p in data.tension.points]
    assert max(scores) > min(scores)


# ===========================================================================
# WIDGET PANELS
# ===========================================================================

def test_tension_panel_creates():
    panel = TensionCurvePanel()
    assert panel.minimumHeight() >= 100


def test_tension_panel_set_data():
    panel = TensionCurvePanel()
    curve = TensionCurve(
        points=[
            SceneTension(1, 0, "S1", 20, 1, 0, 1, 0),
            SceneTension(2, 1, "S2", 50, 2, 1, 3, 1),
        ],
        flags=["Flat section"],
    )
    panel.set_data(curve)
    assert panel._data is not None


def test_char_panel_creates():
    panel = CharacterPresencePanel()
    assert panel is not None


def test_char_panel_set_data():
    panel = CharacterPresencePanel()
    data = [
        CharacterPresence(1, "Alice", [0, 1, 2], 5, []),
        CharacterPresence(2, "Bob", [0, 2], 5, []),
    ]
    panel.set_data(data)
    assert len(panel._data) == 2


def test_char_panel_toggle():
    panel = CharacterPresencePanel()
    data = [
        CharacterPresence(1, "Alice", [0, 1], 3, []),
    ]
    panel.set_data(data)
    assert 1 in panel._visible_ids
    panel.toggle_character(1)
    assert 1 not in panel._visible_ids
    panel.toggle_character(1)
    assert 1 in panel._visible_ids


def test_structure_panel_creates():
    panel = StructurePanel()
    assert panel.minimumHeight() >= 50


def test_structure_panel_set_data():
    panel = StructurePanel()
    data = StructureDistribution(
        segments=[],
        total_scenes=0,
        total_words=0,
    )
    panel.set_data(data)
    assert panel._data is not None


def test_theme_panel_creates():
    panel = ThemeContinuityPanel()
    assert panel is not None


def test_theme_panel_set_data():
    panel = ThemeContinuityPanel()
    data = [
        ThemePresence(1, "Trust", [0, 2], 5, []),
    ]
    panel.set_data(data)
    assert len(panel._data) == 1


def test_theme_panel_toggle():
    panel = ThemeContinuityPanel()
    data = [ThemePresence(1, "Trust", [0], 3, [])]
    panel.set_data(data)
    assert 1 in panel._visible_ids
    panel.toggle_theme(1)
    assert 1 not in panel._visible_ids


# ===========================================================================
# VIEW INTEGRATION
# ===========================================================================

def test_view_creates_with_small_project():
    db = Database()
    proj, *_ = _small_project(db)
    view = NarrativeDashboardView(db, proj.id)
    assert view.data is not None
    assert len(view.data.tension.points) == 3


def test_view_creates_with_large_project():
    db = Database()
    proj, *_ = _large_project(db)
    view = NarrativeDashboardView(db, proj.id)
    assert view.data is not None
    assert len(view.data.tension.points) == 8


def test_view_creates_empty_project():
    db = Database()
    proj = db.create_project("Empty")
    view = NarrativeDashboardView(db, proj.id)
    assert view.data is not None
    assert view.data.tension.points == []
    assert view.data.characters == []
    assert view.data.themes == []
    assert view.data.structure.total_scenes == 0


def test_view_scene_click_callback():
    db = Database()
    proj, s1, *_ = _small_project(db)
    clicked = []
    view = NarrativeDashboardView(
        db, proj.id,
        on_scene_selected=lambda sid: clicked.append(sid),
    )
    view._on_scene_click(s1.id)
    assert clicked == [s1.id]


def test_view_refresh_recomputes():
    db = Database()
    proj, *_ = _small_project(db)
    view = NarrativeDashboardView(db, proj.id)
    old_count = len(view.data.tension.points)
    db.create_scene(proj.id, "Extra", content="New scene.")
    view.refresh()
    assert len(view.data.tension.points) == old_count + 1


def test_view_flags_shown_for_small_project():
    db = Database()
    proj, *_ = _small_project(db)
    view = NarrativeDashboardView(db, proj.id)
    # Small project may or may not have flags; just verify the container doesn't crash
    assert hasattr(view, "_flags_container")


def test_view_without_template_infers_acts():
    db = Database()
    proj = db.create_project("NoActs")
    for i in range(6):
        db.create_scene(proj.id, f"S{i}", content="Some content here.")
    view = NarrativeDashboardView(db, proj.id)
    labels = [s.label for s in view.data.structure.segments]
    assert any("Act" in l for l in labels)


def test_view_multiple_characters_and_themes():
    db = Database()
    proj, scenes, a, b, c, t1, t2 = _large_project(db)
    view = NarrativeDashboardView(db, proj.id)
    assert len(view.data.characters) == 3
    assert len(view.data.themes) == 2
