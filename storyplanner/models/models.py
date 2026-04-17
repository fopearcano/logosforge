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
