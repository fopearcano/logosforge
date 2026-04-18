"""Context Builder — constructs structured prompts from project data."""

from storyplanner.db import Database

CONTENT_MAX_CHARS = 2000
RECENT_STATES_LIMIT = 2
DESCRIPTION_MAX_CHARS = 150


def _truncate(text: str, max_chars: int = CONTENT_MAX_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n[...truncated]"


def gather_scene_context(
    db: Database,
    project_id: int,
    scene_id: int,
) -> str:
    scene = db.get_scene_by_id(scene_id)
    if scene is None:
        return ""

    scene_section = _build_scene_section(scene)
    memory_section = _build_character_memory_section(db, project_id, scene_id)
    places_section = _build_places_section(db, project_id, scene_id)
    position_section = _build_position_section(db, project_id, scene_id)

    sections: list[str] = []
    if scene_section:
        sections.append(f"[Scene Context]\n{scene_section}")
    if memory_section:
        sections.append(f"[Character Memory]\n{memory_section}")
    if places_section:
        sections.append(f"[Places]\n{places_section}")
    if position_section:
        sections.append(f"[Story Position]\n{position_section}")

    return "\n\n".join(sections)


def gather_outline_context(db: Database, project_id: int) -> str:
    scenes = db.get_all_scenes(project_id)
    if not scenes:
        return ""
    lines = ["[Story Outline]"]
    for i, s in enumerate(scenes, 1):
        line = f"  {i}. {s.title}"
        if s.chapter:
            line += f" [{s.chapter}]"
        if s.summary:
            line += f" — {s.summary[:80]}"
        lines.append(line)
    return "\n".join(lines)


def _build_scene_section(scene) -> str:
    parts: list[str] = []
    if scene.title:
        parts.append(f"Title: {scene.title}")
    if scene.act:
        parts.append(f"Act: {scene.act}")
    if scene.chapter:
        parts.append(f"Chapter: {scene.chapter}")
    if scene.plotline:
        parts.append(f"Plotline: {scene.plotline}")
    if scene.beat:
        parts.append(f"Beat: {scene.beat}")
    if scene.tags:
        parts.append(f"Tags: {scene.tags}")
    if scene.goal:
        parts.append(f"Goal: {scene.goal}")
    if scene.conflict:
        parts.append(f"Conflict: {scene.conflict}")
    if scene.outcome:
        parts.append(f"Outcome: {scene.outcome}")
    if scene.synopsis:
        parts.append(f"Synopsis: {scene.synopsis}")
    if scene.summary:
        parts.append(f"Summary: {scene.summary}")
    if scene.content:
        parts.append(f"\nScene Content:\n{_truncate(scene.content)}")
    return "\n".join(parts)


def _build_character_memory_section(
    db: Database, project_id: int, scene_id: int,
) -> str:
    char_ids = db.get_scene_character_ids(scene_id)
    if not char_ids:
        return ""

    char_map = {c.id: c for c in db.get_all_characters(project_id)}
    current_states = dict(db.get_scene_character_states(scene_id))

    blocks: list[str] = []
    for cid in char_ids:
        if cid not in char_map:
            continue
        char = char_map[cid]
        block = [char.name]
        if char.description:
            block.append(
                f"  Description: {char.description[:DESCRIPTION_MAX_CHARS]}"
            )
        current = current_states.get(cid)
        if current:
            block.append(f"  Current state: {current}")

        prior = _recent_prior_states(db, project_id, cid, scene_id)
        if prior:
            block.append(f"  Recent progression: {' → '.join(prior)}")

        blocks.append("\n".join(block))

    return "\n\n".join(blocks)


def _recent_prior_states(
    db: Database, project_id: int, character_id: int, scene_id: int,
) -> list[str]:
    arc = db.get_character_arc(project_id, character_id)
    current_idx = None
    for i, (sid, *_rest) in enumerate(arc):
        if sid == scene_id:
            current_idx = i
            break
    prior_entries = arc[:current_idx] if current_idx is not None else arc
    return [state for _sid, _title, _pos, state in prior_entries[-RECENT_STATES_LIMIT:]]


def _build_places_section(
    db: Database, project_id: int, scene_id: int,
) -> str:
    place_ids = db.get_scene_place_ids(scene_id)
    if not place_ids:
        return ""
    place_map = {p.id: p for p in db.get_all_places(project_id)}
    names = [place_map[pid].name for pid in place_ids if pid in place_map]
    if not names:
        return ""
    return ", ".join(names)


def _build_position_section(
    db: Database, project_id: int, scene_id: int,
) -> str:
    all_scenes = db.get_all_scenes(project_id)
    if not all_scenes:
        return ""

    current_idx = None
    for i, s in enumerate(all_scenes):
        if s.id == scene_id:
            current_idx = i
            break

    if current_idx is None:
        return ""

    scene = all_scenes[current_idx]
    parts = [f"Scene {current_idx + 1} of {len(all_scenes)}"]

    if scene.chapter:
        parts.append(f"Chapter: {scene.chapter}")
    if scene.plotline:
        parts.append(f"Plotline: {scene.plotline}")

    if current_idx > 0:
        parts.append(f"Previous scene: {all_scenes[current_idx - 1].title}")
    if current_idx < len(all_scenes) - 1:
        parts.append(f"Next scene: {all_scenes[current_idx + 1].title}")

    return "\n".join(parts)
