"""Import project data from a JSON file (matching the app's export format)."""

import json

from storyplanner.db import Database

REQUIRED_KEYS = {"project", "characters", "places", "notes", "scenes"}


def validate_import_data(raw: str) -> tuple[dict | None, str]:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None, "Invalid JSON file."

    if not isinstance(data, dict):
        return None, "Invalid story plan format: expected a JSON object."

    missing = REQUIRED_KEYS - set(data.keys())
    if missing:
        return None, f"Invalid story plan format: missing {', '.join(sorted(missing))}."

    return data, ""


def import_json(db: Database, data: dict) -> int:
    project_info = data.get("project", {})
    title = project_info.get("title", "Imported Project")
    project = db.create_project(title)
    project_id = project.id

    # Create characters and build name → id mapping
    char_id_by_name: dict[str, int] = {}
    for char_data in data.get("characters", []):
        name = char_data.get("name", "").strip()
        if not name:
            continue
        char = db.create_character(
            project_id,
            name=name,
            description=char_data.get("description", ""),
        )
        char_id_by_name[name] = char.id

    # Create places and build name → id mapping
    place_id_by_name: dict[str, int] = {}
    for place_data in data.get("places", []):
        name = place_data.get("name", "").strip()
        if not name:
            continue
        place = db.create_place(
            project_id,
            name=name,
            description=place_data.get("description", ""),
        )
        place_id_by_name[name] = place.id

    # Create notes
    for note_data in data.get("notes", []):
        title = note_data.get("title", "").strip()
        if not title:
            continue
        db.create_note(
            project_id,
            title=title,
            content=note_data.get("content", ""),
        )

    # Create scenes in order, resolving character/place names to IDs
    scenes = data.get("scenes", [])
    scenes.sort(key=lambda s: s.get("order_index", 0))

    for scene_data in scenes:
        scene_title = scene_data.get("title", "").strip()
        if not scene_title:
            continue

        char_names = scene_data.get("characters", [])
        place_names = scene_data.get("places", [])

        character_ids = [
            char_id_by_name[name]
            for name in char_names
            if name in char_id_by_name
        ]
        place_ids = [
            place_id_by_name[name]
            for name in place_names
            if name in place_id_by_name
        ]

        db.create_scene(
            project_id,
            title=scene_title,
            summary=scene_data.get("summary", ""),
            synopsis=scene_data.get("synopsis", ""),
            goal=scene_data.get("goal", ""),
            conflict=scene_data.get("conflict", ""),
            outcome=scene_data.get("outcome", ""),
            chapter=scene_data.get("chapter", ""),
            plotline=scene_data.get("plotline", ""),
            character_ids=character_ids,
            place_ids=place_ids,
        )

    return project_id
