"""Data models for StoryPlanner.

All models belong to a Project. SQLModel gives us both SQLAlchemy tables
and Pydantic validation in one class.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Project(SQLModel, table=True):
    """Top-level container. One project = one story."""

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: str = ""
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    # Relationships (back-populated from children)
    characters: list["Character"] = Relationship(back_populates="project")
    places: list["Place"] = Relationship(back_populates="project")
    notes: list["Note"] = Relationship(back_populates="project")
    scenes: list["Scene"] = Relationship(back_populates="project")


class Character(SQLModel, table=True):
    """A character in the story."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    name: str
    description: str = ""
    color: str = "#3498db"  # Hex color for future timeline display
    created_at: datetime = Field(default_factory=_now)

    project: Optional[Project] = Relationship(back_populates="characters")


class Place(SQLModel, table=True):
    """A location in the story world."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    name: str
    description: str = ""
    created_at: datetime = Field(default_factory=_now)

    project: Optional[Project] = Relationship(back_populates="places")


class Note(SQLModel, table=True):
    """A freeform note attached to a project."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    title: str = ""
    content: str = ""
    created_at: datetime = Field(default_factory=_now)

    project: Optional[Project] = Relationship(back_populates="notes")


class Scene(SQLModel, table=True):
    """A scene/beat in the story. Will be placed on a timeline later."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    title: str
    summary: str = ""
    sort_order: int = 0  # For ordering scenes in a future timeline
    created_at: datetime = Field(default_factory=_now)

    project: Optional[Project] = Relationship(back_populates="scenes")
