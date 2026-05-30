"""Map internal ORM objects onto the stable DTOs.

Keeping the ORM→DTO mapping in one place means routes never leak SQLModel
objects, and the wire contract stays decoupled from the database schema.
"""

from __future__ import annotations

from storyplanner.api import schemas
from storyplanner.db import Database


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [p.strip() for p in value.split(",") if p.strip()]


# -- Projects ----------------------------------------------------------------


def project_to_dto(project) -> schemas.ProjectDTO:
    from storyplanner.project_compat import (
        get_project_narrative_engine,
        get_project_writing_format,
    )

    return schemas.ProjectDTO(
        id=project.id,
        title=project.title,
        description=project.description or "",
        narrative_engine=get_project_narrative_engine(project),
        default_writing_format=get_project_writing_format(project),
        format_mode=(project.format_mode or "novel"),
    )


# -- Scenes ------------------------------------------------------------------


def scene_to_dto(db: Database, scene, order_index: int = 0) -> schemas.SceneDTO:
    return schemas.SceneDTO(
        id=scene.id,
        title=scene.title,
        summary=scene.summary or "",
        synopsis=scene.synopsis or "",
        goal=scene.goal or "",
        conflict=scene.conflict or "",
        outcome=scene.outcome or "",
        beat=scene.beat or "",
        act=scene.act or "",
        chapter=scene.chapter or "",
        plotline=scene.plotline or "",
        color_label=scene.color_label or "",
        tags=_split_csv(scene.tags),
        content=scene.content or "",
        sort_order=scene.sort_order or 0,
        order_index=order_index,
        character_ids=db.get_scene_character_ids(scene.id),
        place_ids=db.get_scene_place_ids(scene.id),
    )


def scenes_to_dtos(db: Database, scenes) -> list[schemas.SceneDTO]:
    return [scene_to_dto(db, s, i + 1) for i, s in enumerate(scenes)]


# -- Outline -----------------------------------------------------------------


def outline_tree(db: Database, project_id: int) -> list[schemas.OutlineNodeDTO]:
    nodes = db.get_outline_nodes(project_id)
    children_map: dict[int | None, list] = {}
    for node in nodes:
        children_map.setdefault(node.parent_id, []).append(node)

    def build(parent_id: int | None) -> list[schemas.OutlineNodeDTO]:
        kids = children_map.get(parent_id, [])
        kids.sort(key=lambda n: (n.sort_order, n.id or 0))
        return [
            schemas.OutlineNodeDTO(
                id=n.id,
                parent_id=n.parent_id,
                title=n.title,
                description=n.description or "",
                sort_order=n.sort_order or 0,
                children=build(n.id),
            )
            for n in kids
        ]

    return build(None)


def outline_node_to_dto(node) -> schemas.OutlineNodeDTO:
    return schemas.OutlineNodeDTO(
        id=node.id,
        parent_id=node.parent_id,
        title=node.title,
        description=node.description or "",
        sort_order=node.sort_order or 0,
        children=[],
    )


# -- Plot --------------------------------------------------------------------


def plot_blocks(db: Database, project_id: int) -> list[schemas.PlotBlockDTO]:
    scenes = db.get_all_scenes(project_id)
    blocks: dict[str, list] = {}
    order: list[str] = []
    for scene in scenes:
        plotline = (scene.plotline or "").strip() or "Unassigned"
        if plotline not in blocks:
            blocks[plotline] = []
            order.append(plotline)
        blocks[plotline].append(
            schemas.PlotSceneDTO(
                scene_id=scene.id,
                title=scene.title,
                act=scene.act or "",
                summary=scene.summary or "",
                beat=scene.beat or "",
                color_label=scene.color_label or "",
                order_index=scene.sort_order or 0,
            )
        )
    return [
        schemas.PlotBlockDTO(id=name, plotline=name, scenes=blocks[name])
        for name in order
    ]


# -- Timeline ----------------------------------------------------------------


def timeline_events(db: Database, project_id: int) -> list[schemas.TimelineEventDTO]:
    scenes = db.get_all_scenes(project_id)
    char_name_by_id = {c.id: c.name for c in db.get_all_characters(project_id)}
    events = []
    for index, scene in enumerate(scenes):
        duration = (
            scene.estimated_duration_minutes
            or getattr(scene, "performance_duration_minutes", 0)
        )
        states = [
            schemas.TimelineCharacterStateDTO(
                character=char_name_by_id.get(cid, str(cid)), state=state,
            )
            for cid, state in db.get_scene_character_states(scene.id)
        ]
        events.append(
            schemas.TimelineEventDTO(
                id=scene.id,
                order_index=index + 1,
                title=scene.title,
                act=scene.act or "",
                chapter=scene.chapter or "",
                time_of_day=scene.time_of_day or "",
                location=scene.location or scene.slugline or "",
                duration_minutes=duration or 0,
                character_states=states,
            )
        )
    return events


# -- PSYKE -------------------------------------------------------------------


def psyke_entry_to_dto(db: Database, entry) -> schemas.PsykeEntryDTO:
    return schemas.PsykeEntryDTO(
        id=entry.id,
        name=entry.name,
        type=entry.entry_type,
        aliases=_split_csv(entry.aliases),
        notes=entry.notes or "",
        is_global=bool(entry.is_global),
        details=db.get_psyke_entry_details(entry.id),
    )


def psyke_relations(db: Database, project_id: int) -> list[schemas.PsykeRelationDTO]:
    entries = db.get_all_psyke_entries(project_id)
    name_by_id = {e.id: e.name for e in entries}
    out: list[schemas.PsykeRelationDTO] = []
    seen: set[tuple] = set()
    for e in entries:
        for related, rtype in db.get_typed_related_psyke_entries(e.id):
            key = (min(e.id, related.id), max(e.id, related.id), rtype)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                schemas.PsykeRelationDTO(
                    id=f"{e.id}:{related.id}",
                    source_id=e.id,
                    target_id=related.id,
                    source=name_by_id.get(e.id, ""),
                    target=name_by_id.get(related.id, ""),
                    relation_type=rtype,
                )
            )
    return out


def psyke_progressions(db: Database, project_id: int) -> list[schemas.PsykeProgressionDTO]:
    entries = db.get_all_psyke_entries(project_id)
    scene_title_by_id = {s.id: s.title for s in db.get_all_scenes(project_id)}
    out = []
    for e in entries:
        for prog in db.get_psyke_progressions(e.id):
            out.append(
                schemas.PsykeProgressionDTO(
                    id=prog.id,
                    entry_id=e.id,
                    text=prog.text,
                    scene_id=prog.scene_id,
                    scene_title=scene_title_by_id.get(prog.scene_id, "")
                    if prog.scene_id else "",
                    sort_order=prog.sort_order or 0,
                )
            )
    return out


def progression_to_dto(db: Database, project_id: int, prog, entry_id: int) -> schemas.PsykeProgressionDTO:
    scene_title = ""
    if prog.scene_id:
        scene = db.get_scene_by_id(prog.scene_id)
        scene_title = scene.title if scene else ""
    return schemas.PsykeProgressionDTO(
        id=prog.id,
        entry_id=entry_id,
        text=prog.text,
        scene_id=prog.scene_id,
        scene_title=scene_title,
        sort_order=prog.sort_order or 0,
    )


# -- Notes -------------------------------------------------------------------


def note_to_dto(db: Database, note) -> schemas.NoteDTO:
    return schemas.NoteDTO(
        id=note.id,
        title=note.title,
        content=note.content or "",
        tags=_split_csv(note.tags),
        pinned=bool(note.pinned),
        psyke_links=db.get_note_psyke_links(note.id),
        scene_links=db.get_note_scene_links(note.id),
    )
