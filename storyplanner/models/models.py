"""Data models for StoryPlanner.

All models belong to a Project via project_id.
SQLModel gives us both SQLAlchemy tables and Pydantic validation in one class.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Project(SQLModel, table=True):
    """Top-level container. One project = one story."""

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: str = ""
    format_mode: str = "novel"
    narrative_engine: str = ""
    default_writing_format: str = ""
    settings_json: str = ""
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Character(SQLModel, table=True):
    """A character in the story."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    name: str
    description: str = ""
    color: str = "#3498db"
    created_at: datetime = Field(default_factory=_now)


class Place(SQLModel, table=True):
    """A location in the story world."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    name: str
    description: str = ""
    created_at: datetime = Field(default_factory=_now)


class Note(SQLModel, table=True):
    """A freeform note attached to a project."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    title: str
    content: str = ""
    tags: str = ""
    pinned: bool = False
    created_at: datetime = Field(default_factory=_now)


class NotePsykeLink(SQLModel, table=True):
    """Links a note to a PSYKE entry (many-to-many)."""

    note_id: int = Field(foreign_key="note.id", primary_key=True)
    psyke_entry_id: int = Field(foreign_key="psykeentry.id", primary_key=True)


class NoteSceneLink(SQLModel, table=True):
    """Links a note to a scene (many-to-many)."""

    note_id: int = Field(foreign_key="note.id", primary_key=True)
    scene_id: int = Field(foreign_key="scene.id", primary_key=True)


class Scene(SQLModel, table=True):
    """A scene/beat in the story. Will be placed on a timeline later."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    title: str
    summary: str = ""
    synopsis: str = ""
    goal: str = ""
    conflict: str = ""
    outcome: str = ""
    beat: str = ""
    tags: str = ""
    act: str = ""
    content: str = ""
    chapter: str = ""
    plotline: str = ""
    color_label: str = ""
    # -- Screenplay-engine fields (optional, default-safe) -----------------
    slugline: str = ""
    location: str = ""
    interior_exterior: str = ""        # "INT" | "EXT" | "INT/EXT" | ""
    time_of_day: str = ""              # "DAY" | "NIGHT" | "DUSK" | ...
    estimated_duration_minutes: int = 0
    visual_objective: str = ""
    dramatic_turn: str = ""
    blocking_notes: str = ""
    subtext_notes: str = ""
    setup_payoff_links: str = ""       # CSV of related scene IDs
    montage_group: str = ""
    cinematic_pacing: str = ""         # "fast" | "medium" | "slow" | ""
    continuity_notes: str = ""
    # -- Screenplay PSYKE extensions (cinematic + performative data) -------
    visible_conflict: str = ""         # what the audience sees
    hidden_conflict: str = ""          # subtext layer, who-wants-what
    emotional_turn: str = ""           # internal arc of the scene
    who_knows_what: str = ""           # knowledge state across characters
    physical_action: str = ""          # concrete physical action beat
    visual_symbolism: str = ""         # symbols / motifs in frame
    # -- Stage-script fields (optional, default-safe) ----------------------
    # time_of_day, dramatic_turn, blocking_notes and continuity_notes above
    # are reused; these add theatre-specific metadata.
    stage_location: str = ""
    set_description: str = ""
    scene_objective: str = ""
    entrance_exit_notes: str = ""
    prop_notes: str = ""
    cue_notes: str = ""
    offstage_events: str = ""
    audience_visibility_notes: str = ""
    performance_duration_minutes: int = 0
    sort_order: int = 0
    created_at: datetime = Field(default_factory=_now)


class SceneCharacterLink(SQLModel, table=True):
    """Links a scene to a character (many-to-many)."""

    scene_id: int = Field(foreign_key="scene.id", primary_key=True)
    character_id: int = Field(foreign_key="character.id", primary_key=True)


class ScenePlaceLink(SQLModel, table=True):
    """Links a scene to a place (many-to-many)."""

    scene_id: int = Field(foreign_key="scene.id", primary_key=True)
    place_id: int = Field(foreign_key="place.id", primary_key=True)


class SceneCharacterState(SQLModel, table=True):
    """Tracks a character's narrative state within a scene."""

    id: Optional[int] = Field(default=None, primary_key=True)
    scene_id: int = Field(foreign_key="scene.id")
    character_id: int = Field(foreign_key="character.id")
    state: str = ""


class PsykeEntry(SQLModel, table=True):
    """A Story Bible entry (PSYKE system)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    name: str
    entry_type: str = "other"
    aliases: str = ""
    notes: str = ""
    details_json: str = ""
    is_global: bool = False
    created_at: datetime = Field(default_factory=_now)


class PsykeRelation(SQLModel, table=True):
    """Links two PSYKE entries (bidirectional, stored both ways).

    relation_type is optional — "" means a generic association. Screenplay
    projects use typed relations: "supports_setup", "payoff",
    "thematic_echo", "visual_motif", "subtext_opposition".
    """

    entry_id: int = Field(foreign_key="psykeentry.id", primary_key=True)
    related_entry_id: int = Field(foreign_key="psykeentry.id", primary_key=True)
    relation_type: str = ""


class StoryLink(SQLModel, table=True):
    """A confirmed (or user-tracked) screenplay story link (Phase 10E).

    References to existing entities only — never a copy of scene/PSYKE content.
    Candidates are generated dynamically by the screenplay engines; only links a
    user explicitly confirms/dismisses/resolves are persisted here. The table is
    created idempotently by SQLModel ``create_all`` (old DBs gain it empty).
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    link_type: str = ""              # see SCREENPLAY_LINK_TYPES
    source_type: str = ""            # scene | psyke | setup | motif | object | ...
    source_id: str = ""              # reference id (string-encoded)
    source_scene_id: Optional[int] = None
    source_block_index: Optional[int] = None
    target_type: str = ""
    target_id: str = ""
    target_scene_id: Optional[int] = None
    target_block_index: Optional[int] = None
    label: str = ""
    evidence: str = ""
    status: str = "confirmed"        # candidate | confirmed | dismissed | resolved
    confidence: float = 0.0
    metadata_json: str = ""
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class ProductionDraft(SQLModel, table=True):
    """A screenplay production-draft container (Phase 10J).

    Optional, screenplay-only. Created idempotently by ``create_all`` (old DBs
    gain it empty). Page locking is awareness-only — ``page_locking_status`` is
    never "stable" because pagination is approximate.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    name: str = "Production Draft"
    draft_label: str = ""
    draft_date: str = ""
    status: str = "production"        # spec | production | locked | revised
    is_active: bool = True
    scene_numbering_enabled: bool = False
    page_locking_enabled: bool = False
    page_locking_status: str = "approximate"  # disabled|approximate|stable|unsupported
    notes: str = ""
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class ProductionSceneNumber(SQLModel, table=True):
    """A persistent production scene number for one scene within a draft."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    draft_id: int = Field(foreign_key="productiondraft.id", index=True)
    scene_id: Optional[int] = Field(default=None, foreign_key="scene.id")
    scene_number: str = ""
    original_scene_number: str = ""
    is_omitted: bool = False
    omitted_label: str = ""
    sort_index: int = 0
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class RevisionSet(SQLModel, table=True):
    """A dated/coloured revision set within a production draft."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    draft_id: int = Field(foreign_key="productiondraft.id", index=True)
    label: str = ""
    revision_date: str = ""
    color_name: str = "White"
    status: str = "draft"            # draft | issued | archived
    description: str = ""
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class RevisionChange(SQLModel, table=True):
    """A scene-level change recorded against a revision set (block-level deferred)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    draft_id: int = Field(foreign_key="productiondraft.id", index=True)
    revision_set_id: int = Field(foreign_key="revisionset.id", index=True)
    scene_id: Optional[int] = Field(default=None, foreign_key="scene.id")
    change_type: str = "modified"    # added | modified | deleted | omitted | renumbered
    summary: str = ""
    old_text_hash: str = ""
    new_text_hash: str = ""
    created_at: datetime = Field(default_factory=_now)


# Standard production revision colour sequence (metadata only).
REVISION_COLORS = (
    "White", "Blue", "Pink", "Yellow", "Green", "Goldenrod", "Buff", "Salmon",
    "Cherry", "Tan", "Ivory",
)
PRODUCTION_DRAFT_STATUSES = ("spec", "production", "locked", "revised")
REVISION_SET_STATUSES = ("draft", "issued", "archived")


SCREENPLAY_LINK_TYPES = (
    "setup_to_payoff", "motif_recurrence", "promise_to_consequence",
    "threat_to_consequence", "object_plant_to_use", "character_in_scene",
    "objective_to_turn", "subtext_to_character", "psyke_to_scene",
    "scene_to_sequence", "sequence_to_act", "diagnostic_to_scene",
)
STORY_LINK_STATUSES = ("candidate", "confirmed", "dismissed", "resolved")


PSYKE_RELATION_TYPES = (
    "",                       # generic association
    "supports_setup",         # this entry plants a setup that the other pays off
    "payoff",                 # this entry is a payoff of the other's setup
    "thematic_echo",          # entries that echo the same theme
    "visual_motif",           # shared visual / cinematic motif
    "subtext_opposition",     # entries that hold opposing subtextual stances
)


class PsykeProgression(SQLModel, table=True):
    """A progression note attached to a PSYKE entry."""

    id: Optional[int] = Field(default=None, primary_key=True)
    entry_id: int = Field(foreign_key="psykeentry.id")
    text: str
    scene_id: Optional[int] = Field(default=None, foreign_key="scene.id")
    sort_order: int = 0


class StoryMemoryEntry(SQLModel, table=True):
    """Extracted narrative memory — continuity-relevant facts."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    scene_id: int = Field(foreign_key="scene.id")
    memory_type: str = ""  # character_state, key_event, relationship, decision
    target: str = ""  # character name, or empty for events
    value: str = ""
    created_at: datetime = Field(default_factory=_now)


class OutlineNode(SQLModel, table=True):
    """A node in the hierarchical story outline."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    parent_id: Optional[int] = Field(default=None)
    title: str
    description: str = ""
    sort_order: int = 0
    created_at: datetime = Field(default_factory=_now)


class VoiceProfile(SQLModel, table=True):
    """How a character speaks — tone, rhythm, vocabulary, quirks."""

    id: Optional[int] = Field(default=None, primary_key=True)
    character_id: int = Field(foreign_key="character.id")
    tone: str = "neutral"
    sentence_length: str = "medium"
    vocabulary_level: str = "standard"
    quirks_json: str = "[]"
    punctuation_style_json: str = "{}"
    dialogue_markers_json: str = "[]"
    updated_at: datetime = Field(default_factory=_now)


VOICE_TONES = ("formal", "neutral", "casual", "abrasive", "polite")
VOICE_SENTENCE_LENGTHS = ("short", "medium", "long")
VOICE_VOCABULARY_LEVELS = ("simple", "standard", "elevated")


class QuantumStateRecord(SQLModel, table=True):
    """Persisted Quantum Outliner state — one row per project."""

    project_id: int = Field(foreign_key="project.id", primary_key=True)
    state_json: str = ""
    updated_at: datetime = Field(default_factory=_now)


class ChatMessage(SQLModel, table=True):
    """A single message in the project chat."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    role: str  # "user" | "assistant" | "system"
    content: str
    metadata_json: str = ""
    created_at: datetime = Field(default_factory=_now)


class ChatSummary(SQLModel, table=True):
    """Rolling summary of older chat messages — one row per project."""

    project_id: int = Field(foreign_key="project.id", primary_key=True)
    summary: str = ""
    last_summarized_message_id: int = 0
    updated_at: datetime = Field(default_factory=_now)


CHAT_PERSONALITIES = (
    "default",
    "mentor",
    "skeptic",
    "editor",
    "brutal",
    "whimsical",
    "minimalist",
    "philosopher",
)


# ---------------------------------------------------------------------------
# Stages — narrative versioning + branching
# ---------------------------------------------------------------------------

STAGE_SCOPE_TYPES = ("project", "act", "chapter", "scene", "psyke", "outline")
STAGE_STATUSES = ("active", "archived", "canonical", "alternate")


class Stage(SQLModel, table=True):
    """A named narrative version or branch."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    name: str
    description: str = ""
    parent_stage_id: Optional[int] = Field(default=None, foreign_key="stage.id")
    scope_type: str = "project"
    scope_id: Optional[int] = None
    status: str = "alternate"
    metadata_json: str = ""
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class StageSnapshot(SQLModel, table=True):
    """A captured copy of project data attached to a Stage."""

    id: Optional[int] = Field(default=None, primary_key=True)
    stage_id: int = Field(foreign_key="stage.id")
    label: str = ""
    reason: str = ""
    summary: str = ""
    data_json: str = ""
    created_at: datetime = Field(default_factory=_now)


class StageBranch(SQLModel, table=True):
    """An explicit branching edge between two stages."""

    id: Optional[int] = Field(default=None, primary_key=True)
    source_stage_id: int = Field(foreign_key="stage.id")
    target_stage_id: int = Field(foreign_key="stage.id")
    branch_reason: str = ""
    created_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Graphic Novel — page/panel narrative memory
#
# Hierarchy: Sequence → Pages → Panels. All rows are project-scoped and
# default-safe, so projects in other engines simply leave these tables
# empty. New tables are created by SQLModel.metadata.create_all() on open;
# existing project files gain the empty tables non-destructively.
# ---------------------------------------------------------------------------

GN_DENSITY_LEVELS = ("silent", "light", "medium", "dense", "explosive")
GN_TRANSITION_TYPES = (
    "moment_to_moment", "action_to_action", "subject_to_subject",
    "scene_to_scene", "aspect_to_aspect", "non_sequitur",
)
GN_CONTINUITY_ITEM_TYPES = (
    "prop", "costume", "wound", "object", "location_state",
    "character_design", "visual_state", "other",
)
GN_CONTINUITY_STATUSES = (
    "consistent", "changed", "unknown", "potential_conflict",
)
GN_ISSUE_STATUSES = (
    "planned", "outlined", "drafting", "complete", "published",
)


class GraphicNovelIssue(SQLModel, table=True):
    """A published installment (Issue) grouping a run of pages.

    Optional top-of-hierarchy unit: Issue → Page → Panel. Pages may stay
    unassigned (issue_id is None) — treated as the default / loose pages.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    issue_number: int = 0
    title: str = ""
    summary: str = ""
    status: str = ""              # GN_ISSUE_STATUSES (free-text; "" = unset)
    notes: str = ""
    sort_order: int = 0
    created_at: datetime = Field(default_factory=_now)


class GraphicNovelSequence(SQLModel, table=True):
    """A run of pages with one dramatic/visual purpose (Sequence level)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    title: str = ""
    summary: str = ""
    dramatic_purpose: str = ""
    visual_purpose: str = ""
    emotional_beat: str = ""
    issue: str = ""          # optional Issue label
    chapter: str = ""        # optional Chapter label
    sort_order: int = 0
    created_at: datetime = Field(default_factory=_now)


class GraphicNovelPage(SQLModel, table=True):
    """A single page of the graphic novel."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    sequence_id: Optional[int] = Field(
        default=None, foreign_key="graphicnovelsequence.id",
    )
    # Optional Issue grouping. None = unassigned / default issue. Added
    # after the page table shipped, so old DBs gain it via _migrate().
    issue_id: Optional[int] = Field(
        default=None, foreign_key="graphicnovelissue.id",
    )
    page_number: int = 0
    summary: str = ""
    emotional_beat: str = ""
    density_level: str = ""          # silent|light|medium|dense|explosive
    reveal_type: str = ""            # page-turn reveal / cliffhanger / none
    splash_page: bool = False
    notes: str = ""
    sort_order: int = 0
    created_at: datetime = Field(default_factory=_now)


class GraphicNovelPanel(SQLModel, table=True):
    """A single panel on a page. List-valued fields are CSV TEXT."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    page_id: int = Field(foreign_key="graphicnovelpage.id")
    panel_number: int = 0
    description: str = ""
    camera_angle: str = ""
    shot_type: str = ""
    emotional_tone: str = ""
    action: str = ""
    characters_present: str = ""     # CSV of character / PSYKE entry refs
    dialogue_refs: str = ""          # CSV of dialogue references
    visual_motifs: str = ""          # CSV of motif refs
    reading_priority: int = 0        # 0 = unset; lower reads first
    transition_type: str = ""        # GN_TRANSITION_TYPES
    sort_order: int = 0
    created_at: datetime = Field(default_factory=_now)


class GraphicNovelContinuityItem(SQLModel, table=True):
    """A tracked visual-continuity item (prop, costume, wound, object…)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    name: str
    item_type: str = "other"         # GN_CONTINUITY_ITEM_TYPES
    description: str = ""
    linked_psyke_entry_id: Optional[int] = Field(
        default=None, foreign_key="psykeentry.id",
    )
    notes: str = ""
    created_at: datetime = Field(default_factory=_now)


class GraphicNovelContinuityAppearance(SQLModel, table=True):
    """One appearance of a continuity item in a page/panel, with its state."""

    id: Optional[int] = Field(default=None, primary_key=True)
    continuity_item_id: int = Field(
        foreign_key="graphicnovelcontinuityitem.id",
    )
    page_id: Optional[int] = Field(
        default=None, foreign_key="graphicnovelpage.id",
    )
    panel_id: Optional[int] = Field(
        default=None, foreign_key="graphicnovelpanel.id",
    )
    state_description: str = ""
    continuity_status: str = "consistent"   # GN_CONTINUITY_STATUSES
    sort_order: int = 0
    created_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Stage Script — theatrical / performance metadata
#
# Lightweight, scene-scoped structures for the Stage Script engine. Props
# are NOT duplicated here: stage business references a PSYKE object entry.
# New tables are created by create_all() on open; existing project files
# gain them non-destructively.
# ---------------------------------------------------------------------------

STAGE_ENTRANCE_EXIT_TYPES = ("entrance", "exit")
STAGE_CUE_TYPES = ("light", "sound", "music", "prop", "movement", "other")

# Theatrical PSYKE relation types (PsykeRelation.relation_type). Directional
# except dominates/submits which form an antonym pair.
THEATRE_RELATION_TYPES = (
    "pressures", "confronts", "avoids", "dominates",
    "submits", "deceives", "overhears", "interrupts",
)


class StageEntranceExit(SQLModel, table=True):
    """A character entering or leaving the stage within a scene."""

    id: Optional[int] = Field(default=None, primary_key=True)
    scene_id: int = Field(foreign_key="scene.id")
    character_id: Optional[int] = Field(
        default=None, foreign_key="character.id",
    )
    type: str = "entrance"           # STAGE_ENTRANCE_EXIT_TYPES
    moment_order: int = 0
    cue_text: str = ""
    notes: str = ""
    created_at: datetime = Field(default_factory=_now)


class StageCue(SQLModel, table=True):
    """A technical cue (light / sound / music / prop / movement) in a scene."""

    id: Optional[int] = Field(default=None, primary_key=True)
    scene_id: int = Field(foreign_key="scene.id")
    cue_type: str = "other"          # STAGE_CUE_TYPES
    moment_order: int = 0
    cue_text: str = ""
    notes: str = ""
    created_at: datetime = Field(default_factory=_now)


class StageBusiness(SQLModel, table=True):
    """Stage business: a prop used by a character with a stage action.

    The prop is a PSYKE object entry (prop_psyke_entry_id) rather than a
    duplicated prop record.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    scene_id: int = Field(foreign_key="scene.id")
    prop_psyke_entry_id: Optional[int] = Field(
        default=None, foreign_key="psykeentry.id",
    )
    character_id: Optional[int] = Field(
        default=None, foreign_key="character.id",
    )
    stage_action: str = ""
    continuity_note: str = ""
    moment_order: int = 0
    created_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Series — season / episode / arc / plotline metadata
#
# Hierarchy: Project -> Season -> Episode -> EpisodePlotline; SeriesArc spans
# episodes. All rows are project-scoped and default-safe. New tables are
# created by create_all() on open; existing project files gain them
# non-destructively (no ALTER, no data migration).
# ---------------------------------------------------------------------------

SEASON_STATUSES = ("planned", "active", "complete", "")
EPISODE_STATUSES = ("planned", "outlined", "drafted", "final", "")
SERIES_ARC_SCOPES = (
    "series", "season", "episode", "character", "relationship", "mystery",
)
SERIES_ARC_STATUSES = ("active", "resolved", "abandoned", "delayed")
EPISODE_PLOTLINE_TYPES = ("A", "B", "C", "runner")


class Season(SQLModel, table=True):
    """A season of a series."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    season_number: int = 0
    title: str = ""
    summary: str = ""
    season_arc: str = ""
    central_question: str = ""
    finale_payoff: str = ""
    status: str = ""
    order_index: int = 0
    created_at: datetime = Field(default_factory=_now)


class Episode(SQLModel, table=True):
    """An episode within a season."""

    id: Optional[int] = Field(default=None, primary_key=True)
    season_id: int = Field(foreign_key="season.id")
    project_id: int = Field(foreign_key="project.id")
    episode_number: int = 0
    title: str = ""
    logline: str = ""
    summary: str = ""
    episode_engine: str = ""        # the episode's dramatic engine / function
    teaser: str = ""
    act_breaks: str = ""            # free-text act-break notes
    cliffhanger: str = ""
    status: str = ""
    estimated_runtime_minutes: int = 0
    order_index: int = 0
    created_at: datetime = Field(default_factory=_now)


class SeriesArc(SQLModel, table=True):
    """A long-running arc spanning episodes (series/season/character/...).

    linked_psyke_entries is a CSV of PSYKE entry ids — arcs reuse PSYKE
    rather than duplicating characters/themes.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    scope: str = "series"           # SERIES_ARC_SCOPES
    title: str = ""
    summary: str = ""
    setup_episode_id: Optional[int] = Field(
        default=None, foreign_key="episode.id",
    )
    payoff_episode_id: Optional[int] = Field(
        default=None, foreign_key="episode.id",
    )
    status: str = "active"          # SERIES_ARC_STATUSES
    linked_psyke_entries: str = ""  # CSV of PSYKE entry ids
    notes: str = ""
    created_at: datetime = Field(default_factory=_now)


class EpisodePlotline(SQLModel, table=True):
    """An A/B/C/runner plotline within an episode."""

    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: int = Field(foreign_key="episode.id")
    type: str = "A"                 # EPISODE_PLOTLINE_TYPES
    title: str = ""
    summary: str = ""
    characters: str = ""            # CSV of character / PSYKE refs
    resolution_state: str = ""
    order_index: int = 0
    created_at: datetime = Field(default_factory=_now)
