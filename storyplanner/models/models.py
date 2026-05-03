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
    created_at: datetime = Field(default_factory=_now)


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
    """Links two PSYKE entries (bidirectional, stored both ways)."""

    entry_id: int = Field(foreign_key="psykeentry.id", primary_key=True)
    related_entry_id: int = Field(foreign_key="psykeentry.id", primary_key=True)


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


class QuantumStateRecord(SQLModel, table=True):
    """Persisted Quantum Outliner state — one row per project."""

    project_id: int = Field(foreign_key="project.id", primary_key=True)
    state_json: str = ""
    updated_at: datetime = Field(default_factory=_now)
