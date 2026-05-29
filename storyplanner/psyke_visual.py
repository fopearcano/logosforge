"""PSYKE visual-memory layer for the Graphic Novel Engine.

Graphic novels need PSYKE to remember how things LOOK and how those
looks RECUR. This module stores visual storytelling metadata on PSYKE
entries (under details_json["visual"]) and derives recurrence/callback
information from the page/panel/continuity tables — without duplicating
PSYKE or adding a second codex.

Pure core/app logic: no UI, no Tauri, no filesystem, no providers.
"""

from __future__ import annotations

from typing import Any


# Visual fields for a character PSYKE entry (entry_type == "character").
CHARACTER_VISUAL_FIELDS: tuple[str, ...] = (
    "silhouette",
    "shape_language",
    "color_identity",
    "costume_state",
    "pose_language",
    "gesture_vocabulary",
    "visual_symbolism",
)

# Visual fields for a place/location PSYKE entry (entry_type == "place").
LOCATION_VISUAL_FIELDS: tuple[str, ...] = (
    "architecture",
    "lighting_mood",
    "environmental_motifs",
    "recurring_objects",
)

# Kinds of recurring motif (for a motif tracked as a theme/object entry).
MOTIF_KINDS: tuple[str, ...] = (
    "symbol",
    "object",
    "color",
    "pose",
    "framing",
    "composition",
)


def visual_fields_for_type(entry_type: str) -> tuple[str, ...]:
    """Return the relevant visual field names for a PSYKE entry type."""
    et = (entry_type or "").lower()
    if et == "character":
        return CHARACTER_VISUAL_FIELDS
    if et == "place":
        return LOCATION_VISUAL_FIELDS
    return ()


def get_visual_memory(db: Any, entry_id: int) -> dict:
    """Visual metadata stored on a PSYKE entry (may be empty)."""
    return db.get_psyke_visual_memory(entry_id)


def set_visual_memory(db: Any, entry_id: int, **fields: Any) -> None:
    """Merge visual metadata onto a PSYKE entry. Empty values clear a key."""
    db.set_psyke_visual_memory(entry_id, dict(fields))


# ---------------------------------------------------------------------------
# Panel context — where motifs appeared, where objects reappear, callbacks.
# ---------------------------------------------------------------------------

def get_motif_recurrences(db: Any, project_id: int) -> dict[str, list[int]]:
    """Map each visual-motif token to the panel ids it appears in.

    Reads GraphicNovelPanel.visual_motifs (CSV). A motif appearing in more
    than one panel is a genuine recurrence/callback.
    """
    recurrences: dict[str, list[int]] = {}
    for page in db.get_gn_pages(project_id):
        for panel in db.get_gn_panels_for_page(page.id):
            for motif in db.csv_split(panel.visual_motifs):
                recurrences.setdefault(motif, []).append(panel.id)
    return recurrences


def get_object_reappearances(db: Any, project_id: int) -> dict[str, list[dict]]:
    """Map each continuity item to its ordered appearances (page/panel/state).

    Captures object persistence and visual callbacks across the book.
    """
    result: dict[str, list[dict]] = {}
    for item in db.get_gn_continuity_items(project_id):
        appearances = db.get_gn_continuity_appearances(item.id)
        result[item.name] = [
            {
                "page_id": a.page_id,
                "panel_id": a.panel_id,
                "state": a.state_description,
                "status": a.continuity_status,
            }
            for a in appearances
        ]
    return result


def get_visual_callbacks(db: Any, project_id: int) -> dict[str, list[int]]:
    """Motifs that recur (appear in 2+ panels) — i.e. visual callbacks."""
    return {
        motif: panels
        for motif, panels in get_motif_recurrences(db, project_id).items()
        if len(panels) >= 2
    }


# ---------------------------------------------------------------------------
# Assistant context block
# ---------------------------------------------------------------------------

_MAX_ENTRIES = 8
_MAX_MOTIFS = 10


def build_visual_memory_context(
    db: Any, project_id: int, entry_id: int | None = None,
) -> str:
    """Compact ``[Visual Memory]`` block for the Assistant.

    With *entry_id*, focuses on that entry's visual identity. Otherwise it
    summarizes character/location visual identity plus tracked motifs and
    recurring objects across the project. Returns "" when there is nothing
    visual to report.
    """
    lines: list[str] = []

    if entry_id is not None:
        entry = db.get_psyke_entry_by_id(entry_id)
        if entry is not None:
            visual = db.get_psyke_visual_memory(entry_id)
            if visual:
                lines.append(f"{entry.name} ({entry.entry_type}):")
                for key, value in visual.items():
                    lines.append(f"- {key.replace('_', ' ')}: {value}")
    else:
        entries = db.get_all_psyke_entries(project_id)
        shown = 0
        for entry in entries:
            visual = db.get_psyke_visual_memory(entry.id)
            if not visual:
                continue
            bits = ", ".join(
                f"{k.replace('_', ' ')}: {v}" for k, v in list(visual.items())[:4]
            )
            lines.append(f"- {entry.name} ({entry.entry_type}): {bits}")
            shown += 1
            if shown >= _MAX_ENTRIES:
                break

        callbacks = get_visual_callbacks(db, project_id)
        if callbacks:
            motif_bits = ", ".join(
                f"{m} (×{len(p)})" for m, p in list(callbacks.items())[:_MAX_MOTIFS]
            )
            lines.append(f"Recurring motifs: {motif_bits}")

        objects = get_object_reappearances(db, project_id)
        recurring_objs = [
            f"{name} (×{len(apps)})"
            for name, apps in objects.items() if len(apps) >= 2
        ]
        if recurring_objs:
            lines.append("Recurring objects: " + ", ".join(recurring_objs[:_MAX_MOTIFS]))

    if not lines:
        return ""
    return "[Visual Memory]\n" + "\n".join(lines)
