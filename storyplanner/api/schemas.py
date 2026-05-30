"""Pydantic DTOs — the stable contract between the Python core and React.

Internal ORM objects are never returned directly; routes map them onto these
DTOs via :mod:`storyplanner.api.serializers`.  Field names are intended to stay
stable across releases.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


class ProjectDTO(BaseModel):
    id: int
    title: str
    description: str = ""
    narrative_engine: str = ""
    default_writing_format: str = ""
    format_mode: str = "novel"


class ProjectCreateDTO(BaseModel):
    title: str
    description: str = ""
    narrative_engine: str = ""
    default_writing_format: str = ""


class SettingsDTO(BaseModel):
    settings: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Scenes
# ---------------------------------------------------------------------------


class SceneDTO(BaseModel):
    id: int
    title: str
    summary: str = ""
    synopsis: str = ""
    goal: str = ""
    conflict: str = ""
    outcome: str = ""
    beat: str = ""
    act: str = ""
    chapter: str = ""
    plotline: str = ""
    color_label: str = ""
    tags: list[str] = Field(default_factory=list)
    content: str = ""
    sort_order: int = 0
    order_index: int = 0
    character_ids: list[int] = Field(default_factory=list)
    place_ids: list[int] = Field(default_factory=list)


class SceneCreateDTO(BaseModel):
    title: str
    summary: str = ""
    synopsis: str = ""
    goal: str = ""
    conflict: str = ""
    outcome: str = ""
    beat: str = ""
    act: str = ""
    chapter: str = ""
    plotline: str = ""
    content: str = ""
    tags: list[str] = Field(default_factory=list)
    character_ids: list[int] = Field(default_factory=list)
    place_ids: list[int] = Field(default_factory=list)


class SceneUpdateDTO(BaseModel):
    """All fields optional — only provided fields are changed."""

    title: str | None = None
    summary: str | None = None
    synopsis: str | None = None
    goal: str | None = None
    conflict: str | None = None
    outcome: str | None = None
    beat: str | None = None
    act: str | None = None
    chapter: str | None = None
    plotline: str | None = None
    color_label: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    sort_order: int | None = None
    time_of_day: str | None = None
    location: str | None = None
    estimated_duration_minutes: int | None = None


# ---------------------------------------------------------------------------
# Outline
# ---------------------------------------------------------------------------


class OutlineNodeDTO(BaseModel):
    id: int
    parent_id: int | None = None
    title: str
    description: str = ""
    sort_order: int = 0
    children: list["OutlineNodeDTO"] = Field(default_factory=list)


class OutlineNodeCreateDTO(BaseModel):
    title: str
    description: str = ""
    parent_id: int | None = None
    sort_order: int = 0


class OutlineNodeUpdateDTO(BaseModel):
    title: str | None = None
    description: str | None = None
    sort_order: int | None = None


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------


class PlotSceneDTO(BaseModel):
    scene_id: int | None = None
    title: str
    act: str = ""
    summary: str = ""
    beat: str = ""
    color_label: str = ""
    order_index: int = 0


class PlotBlockDTO(BaseModel):
    id: str  # the plotline name (URL-safe stable identifier)
    plotline: str
    scenes: list[PlotSceneDTO] = Field(default_factory=list)


class PlotBlockUpdateDTO(BaseModel):
    plotline: str | None = None  # rename the block
    color_label: str | None = None  # recolour all scenes in the block


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


class TimelineCharacterStateDTO(BaseModel):
    character: str
    state: str


class TimelineEventDTO(BaseModel):
    id: int  # scene id (timeline events are scene-derived)
    order_index: int = 0
    title: str
    act: str = ""
    chapter: str = ""
    time_of_day: str = ""
    location: str = ""
    duration_minutes: int = 0
    character_states: list[TimelineCharacterStateDTO] = Field(default_factory=list)


class TimelineEventCreateDTO(BaseModel):
    title: str
    act: str = ""
    chapter: str = ""
    time_of_day: str = ""
    location: str = ""
    duration_minutes: int = 0


class TimelineEventUpdateDTO(BaseModel):
    title: str | None = None
    act: str | None = None
    chapter: str | None = None
    time_of_day: str | None = None
    location: str | None = None
    duration_minutes: int | None = None
    sort_order: int | None = None


# ---------------------------------------------------------------------------
# PSYKE
# ---------------------------------------------------------------------------


class PsykeEntryDTO(BaseModel):
    id: int
    name: str
    type: str = "other"
    aliases: list[str] = Field(default_factory=list)
    notes: str = ""
    is_global: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class PsykeEntryCreateDTO(BaseModel):
    name: str
    type: str = "other"
    aliases: list[str] = Field(default_factory=list)
    notes: str = ""
    is_global: bool = False
    details: dict[str, Any] | None = None


class PsykeEntryUpdateDTO(BaseModel):
    name: str | None = None
    type: str | None = None
    aliases: list[str] | None = None
    notes: str | None = None
    is_global: bool | None = None
    details: dict[str, Any] | None = None


class PsykeRelationDTO(BaseModel):
    id: str  # synthetic "{source_id}:{target_id}"
    source_id: int
    target_id: int
    source: str = ""
    target: str = ""
    relation_type: str = ""


class PsykeRelationCreateDTO(BaseModel):
    source_id: int
    target_id: int
    relation_type: str = ""


class PsykeProgressionDTO(BaseModel):
    id: int
    entry_id: int
    text: str
    scene_id: int | None = None
    scene_title: str = ""
    sort_order: int = 0


class PsykeProgressionCreateDTO(BaseModel):
    entry_id: int
    text: str
    scene_id: int | None = None


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------


class NoteDTO(BaseModel):
    id: int
    title: str
    content: str = ""
    tags: list[str] = Field(default_factory=list)
    pinned: bool = False
    psyke_links: list[int] = Field(default_factory=list)
    scene_links: list[int] = Field(default_factory=list)


class NoteCreateDTO(BaseModel):
    title: str
    content: str = ""
    tags: list[str] = Field(default_factory=list)
    pinned: bool = False


class NoteUpdateDTO(BaseModel):
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    pinned: bool | None = None


# ---------------------------------------------------------------------------
# Assistant / Connector
# ---------------------------------------------------------------------------


class ChatMessageDTO(BaseModel):
    role: str
    content: str


class AssistantRequestDTO(BaseModel):
    message: str
    history: list[ChatMessageDTO] = Field(default_factory=list)
    system_prompt: str = ""


class AssistantResponseDTO(BaseModel):
    reply: str
    cached: bool = False


class AssistantActionRequestDTO(BaseModel):
    action: str
    args: dict[str, Any] = Field(default_factory=dict)


class AssistantSettingsDTO(BaseModel):
    provider: str = ""
    model: str = ""
    base_url: str = ""
    # api_key is intentionally write-only; never returned.
    api_key: str | None = None
    timeout: int = 0


class ConnectorActionParamDTO(BaseModel):
    name: str
    param_type: str = "str"
    required: bool = True
    default: Any = None


class ConnectorActionDTO(BaseModel):
    name: str
    description: str = ""
    category: str = ""
    params: list[ConnectorActionParamDTO] = Field(default_factory=list)


class ConnectorExecuteDTO(BaseModel):
    action: str
    args: dict[str, Any] = Field(default_factory=dict)


class ConnectorResultDTO(BaseModel):
    ok: bool
    action: str = ""
    result: Any = None
    error: str = ""


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


class ExportRequestDTO(BaseModel):
    export_type: str = "story_elements"  # story_elements | psyke_data | full_project
    format: str = "json"  # json | markdown | csv
    # Optional section overrides (default = the preset for export_type).
    include_outline: bool | None = None
    include_plot: bool | None = None
    include_timeline: bool | None = None
    include_scenes: bool | None = None
    include_psyke_entries: bool | None = None
    include_psyke_relations: bool | None = None
    include_psyke_progressions: bool | None = None
    include_notes: bool | None = None
    include_project_metadata: bool | None = None
    include_ids: bool | None = None
    include_internal_metadata: bool | None = None
    summaries_only: bool | None = None


class ExportResponseDTO(BaseModel):
    export_type: str
    format: str
    # For json: the structured payload. For markdown/csv: text content (csv = a
    # map of filename -> text).
    payload: Any = None
    content: str | None = None
    files: dict[str, str] | None = None


OutlineNodeDTO.model_rebuild()
