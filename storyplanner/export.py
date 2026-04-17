"""Export project data to JSON, Markdown, or CSV."""

import csv
import io
import json

from storyplanner.db import Database


def _gather_project_data(db: Database, project_id: int) -> dict:
    project = db.get_project_by_id(project_id)

    characters = db.get_all_characters(project_id)
    places = db.get_all_places(project_id)
    notes = db.get_all_notes(project_id)
    scenes = db.get_all_scenes(project_id)

    char_name_by_id = {c.id: c.name for c in characters}
    place_name_by_id = {p.id: p.name for p in places}

    scene_list = []
    for i, scene in enumerate(scenes):
        char_ids = db.get_scene_character_ids(scene.id)
        place_ids = db.get_scene_place_ids(scene.id)
        char_states = db.get_scene_character_states(scene.id)

        scene_list.append(
            {
                "title": scene.title,
                "summary": scene.summary,
                "synopsis": scene.synopsis,
                "goal": scene.goal,
                "conflict": scene.conflict,
                "outcome": scene.outcome,
                "content": scene.content,
                "beat": scene.beat,
                "tags": [t.strip() for t in scene.tags.split(",") if t.strip()] if scene.tags else [],
                "order_index": i + 1,
                "act": scene.act,
                "chapter": scene.chapter,
                "plotline": scene.plotline,
                "characters": [
                    char_name_by_id[cid]
                    for cid in char_ids
                    if cid in char_name_by_id
                ],
                "places": [
                    place_name_by_id[pid]
                    for pid in place_ids
                    if pid in place_name_by_id
                ],
                "character_states": [
                    {"character": char_name_by_id[cid], "state": state}
                    for cid, state in char_states
                    if cid in char_name_by_id
                ],
            }
        )

    return {
        "project": {
            "title": project.title if project else "Untitled",
            "description": project.description if project else "",
        },
        "characters": [
            {"name": c.name, "description": c.description} for c in characters
        ],
        "places": [
            {"name": p.name, "description": p.description} for p in places
        ],
        "notes": [
            {"title": n.title, "content": n.content} for n in notes
        ],
        "scenes": scene_list,
    }


def export_json(db: Database, project_id: int) -> str:
    data = _gather_project_data(db, project_id)
    return json.dumps(data, indent=2, ensure_ascii=False)


def export_markdown(db: Database, project_id: int) -> str:
    data = _gather_project_data(db, project_id)
    lines: list[str] = []

    # Project header
    lines.append(f"# {data['project']['title']}")
    if data["project"]["description"]:
        lines.append("")
        lines.append(data["project"]["description"])

    # Characters
    lines.append("")
    lines.append("## Characters")
    if data["characters"]:
        for char in data["characters"]:
            lines.append("")
            lines.append(f"### {char['name']}")
            if char["description"]:
                lines.append("")
                lines.append(char["description"])
    else:
        lines.append("")
        lines.append("No characters.")

    # Places
    lines.append("")
    lines.append("## Places")
    if data["places"]:
        for place in data["places"]:
            lines.append("")
            lines.append(f"### {place['name']}")
            if place["description"]:
                lines.append("")
                lines.append(place["description"])
    else:
        lines.append("")
        lines.append("No places.")

    # Notes
    lines.append("")
    lines.append("## Notes")
    if data["notes"]:
        for note in data["notes"]:
            lines.append("")
            lines.append(f"### {note['title']}")
            if note["content"]:
                lines.append("")
                lines.append(note["content"])
    else:
        lines.append("")
        lines.append("No notes.")

    # Scenes
    lines.append("")
    lines.append("## Scenes")
    if data["scenes"]:
        for scene in data["scenes"]:
            lines.append("")
            lines.append(f"### {scene['order_index']}. {scene['title']}")
            if scene["act"]:
                lines.append(f"- **Act:** {scene['act']}")
            if scene["chapter"]:
                lines.append(f"- **Chapter:** {scene['chapter']}")
            if scene["plotline"]:
                lines.append(f"- **Plotline:** {scene['plotline']}")
            if scene["beat"]:
                lines.append(f"- **Beat:** {scene['beat']}")
            if scene["tags"]:
                lines.append(f"- **Tags:** {', '.join(scene['tags'])}")
            if scene["characters"]:
                lines.append(f"- **Characters:** {', '.join(scene['characters'])}")
            if scene["places"]:
                lines.append(f"- **Places:** {', '.join(scene['places'])}")
            if scene["summary"]:
                lines.append("")
                lines.append(scene["summary"])
            if scene["synopsis"]:
                lines.append("")
                lines.append(f"**Synopsis:** {scene['synopsis']}")
            if scene["goal"]:
                lines.append(f"- **Goal:** {scene['goal']}")
            if scene["conflict"]:
                lines.append(f"- **Conflict:** {scene['conflict']}")
            if scene["outcome"]:
                lines.append(f"- **Outcome:** {scene['outcome']}")
            if scene["character_states"]:
                lines.append("")
                lines.append("**Character States:**")
                for cs in scene["character_states"]:
                    lines.append(f"- {cs['character']}: {cs['state']}")
            if scene["content"]:
                lines.append("")
                lines.append("---")
                lines.append("")
                lines.append(scene["content"])
    else:
        lines.append("")
        lines.append("No scenes.")

    lines.append("")
    return "\n".join(lines)


def export_outline_markdown(db: Database, project_id: int) -> str:
    data = _gather_project_data(db, project_id)
    lines: list[str] = []

    lines.append(f"# {data['project']['title']}")

    scenes = data["scenes"]
    if not scenes:
        lines.append("")
        lines.append("No scenes to display.")
        lines.append("")
        return "\n".join(lines)

    # Group scenes by chapter, preserving narrative order
    chapter_groups: list[tuple[str, list[dict]]] = []
    current_chapter: str | None = None
    current_group: list[dict] = []

    for scene in scenes:
        chapter = scene["chapter"] if scene["chapter"] else ""
        if chapter != current_chapter:
            if current_group:
                chapter_groups.append((current_chapter or "", current_group))
            current_chapter = chapter
            current_group = [scene]
        else:
            current_group.append(scene)
    if current_group:
        chapter_groups.append((current_chapter or "", current_group))

    for chapter_name, group_scenes in chapter_groups:
        lines.append("")
        if chapter_name:
            lines.append(f"## {chapter_name}")
        else:
            lines.append("## Uncategorized")

        for scene in group_scenes:
            lines.append("")
            lines.append(f"### {scene['order_index']}. {scene['title']}")
            if scene["act"]:
                lines.append(f"- **Act:** {scene['act']}")
            if scene["plotline"]:
                lines.append(f"- **Plotline:** {scene['plotline']}")
            if scene["beat"]:
                lines.append(f"- **Beat:** {scene['beat']}")
            if scene["tags"]:
                lines.append(f"- **Tags:** {', '.join(scene['tags'])}")
            if scene["characters"]:
                lines.append(f"- **Characters:** {', '.join(scene['characters'])}")
            if scene["places"]:
                lines.append(f"- **Places:** {', '.join(scene['places'])}")
            if scene["summary"]:
                lines.append("")
                lines.append(scene["summary"])
            if scene["synopsis"]:
                lines.append("")
                lines.append(f"**Synopsis:** {scene['synopsis']}")
            if scene["goal"]:
                lines.append(f"- **Goal:** {scene['goal']}")
            if scene["conflict"]:
                lines.append(f"- **Conflict:** {scene['conflict']}")
            if scene["outcome"]:
                lines.append(f"- **Outcome:** {scene['outcome']}")
            if scene["character_states"]:
                lines.append("")
                lines.append("**Character States:**")
                for cs in scene["character_states"]:
                    lines.append(f"- {cs['character']}: {cs['state']}")

    lines.append("")
    return "\n".join(lines)


def export_csv_scenes(db: Database, project_id: int) -> str:
    data = _gather_project_data(db, project_id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["order_index", "title", "summary", "synopsis", "goal", "conflict", "outcome",
         "beat", "tags", "act", "chapter", "plotline", "characters", "places"]
    )
    for scene in data["scenes"]:
        writer.writerow(
            [
                scene["order_index"],
                scene["title"],
                scene["summary"],
                scene["synopsis"],
                scene["goal"],
                scene["conflict"],
                scene["outcome"],
                scene["beat"],
                ", ".join(scene["tags"]),
                scene["act"],
                scene["chapter"],
                scene["plotline"],
                ", ".join(scene["characters"]),
                ", ".join(scene["places"]),
            ]
        )
    return output.getvalue()


def export_screenplay(db: Database, project_id: int) -> str:
    data = _gather_project_data(db, project_id)
    lines: list[str] = []

    title = data["project"]["title"]
    lines.append(title.upper())
    lines.append("=" * len(title))
    lines.append("")
    lines.append("")

    for scene in data["scenes"]:
        heading_parts = []
        if scene["act"]:
            heading_parts.append(scene["act"].upper())
        if scene["chapter"]:
            heading_parts.append(scene["chapter"].upper())

        heading = scene["title"].upper()
        if scene["places"]:
            heading += " — " + ", ".join(scene["places"]).upper()

        if heading_parts:
            lines.append(". ".join(heading_parts))
            lines.append("")

        lines.append(heading)
        lines.append("")

        if scene["content"]:
            lines.append(scene["content"])
        elif scene["summary"]:
            lines.append(scene["summary"])

        lines.append("")
        lines.append("")

    return "\n".join(lines)
