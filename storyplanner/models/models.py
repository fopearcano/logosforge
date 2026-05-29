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
