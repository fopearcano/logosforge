"""PSYKE adapter — bridge between Quantum Outliner and the story bible.

Reads characters/relations for prompt context, applies state deltas
to PSYKE entries when a wavefunction collapses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from storyplanner.quantum_outliner.state import Branch, StateDelta

if TYPE_CHECKING:
    from storyplanner.db import Database


def gather_psyke_brief(db: Database, project_id: int, max_entries: int = 12) -> str:
    """Compact textual summary of PSYKE characters/places for prompt grounding."""
    entries = db.get_all_psyke_entries(project_id)
    if not entries:
        return ""

    chars = [e for e in entries if e.entry_type == "character"][:max_entries]
    places = [e for e in entries if e.entry_type == "place"][: max(3, max_entries // 3)]

    lines: list[str] = []
    if chars:
        lines.append("Characters:")
        for c in chars:
            note = (c.notes or "").strip().splitlines()
            summary = note[0] if note else ""
            lines.append(f"- {c.name}: {summary}" if summary else f"- {c.name}")
    if places:
        lines.append("")
        lines.append("Places:")
        for p in places:
            lines.append(f"- {p.name}")

    return "\n".join(lines)


def find_entry_by_name(db: Database, project_id: int, name: str):
    """Lookup PSYKE entry by exact name (case-insensitive)."""
    target = name.strip().lower()
    if not target:
        return None
    for e in db.get_all_psyke_entries(project_id):
        if e.name.lower() == target:
            return e
    return None


def apply_collapse(
    db: Database,
    project_id: int,
    branch: Branch,
) -> dict:
    """Apply a branch's state delta to PSYKE.

    - character_changes: append note to existing entry, or create new "other" entry
    - new_relations: connect two named PSYKE entries (no-op if either missing)
    - arc_updates: append note to entry, prefixed with "[arc]"

    Returns a summary of what was actually written.
    """
    delta = branch.state_delta
    summary = {
        "characters_updated": [],
        "characters_created": [],
        "relations_added": [],
        "arcs_updated": [],
        "skipped": [],
    }

    for change in delta.character_changes:
        name = (change.get("name") or "").strip()
        note = (change.get("note") or "").strip()
        if not name or not note:
            summary["skipped"].append({"reason": "missing name or note", "data": change})
            continue
        entry = find_entry_by_name(db, project_id, name)
        if entry is None:
            new_entry = db.create_psyke_entry(
                project_id=project_id,
                name=name,
                entry_type="character",
                notes=note,
            )
            summary["characters_created"].append({"id": new_entry.id, "name": name})
        else:
            combined = (entry.notes + "\n\n" + note).strip() if entry.notes else note
            db.update_psyke_entry(
                entry_id=entry.id,
                name=entry.name,
                entry_type=entry.entry_type,
                aliases=entry.aliases or "",
                notes=combined,
                is_global=bool(entry.is_global),
            )
            summary["characters_updated"].append({"id": entry.id, "name": name})

    for relation in delta.new_relations:
        a = (relation.get("from") or "").strip()
        b = (relation.get("to") or "").strip()
        if not a or not b:
            summary["skipped"].append({"reason": "missing from/to", "data": relation})
            continue
        entry_a = find_entry_by_name(db, project_id, a)
        entry_b = find_entry_by_name(db, project_id, b)
        if entry_a is None or entry_b is None:
            summary["skipped"].append({"reason": "entry not found", "data": relation})
            continue
        db.add_psyke_relation(entry_a.id, entry_b.id)
        summary["relations_added"].append({
            "from_id": entry_a.id, "to_id": entry_b.id,
            "from": entry_a.name, "to": entry_b.name,
        })

    for arc in delta.arc_updates:
        name = (arc.get("name") or "").strip()
        note = (arc.get("note") or "").strip()
        if not name or not note:
            summary["skipped"].append({"reason": "missing name or note", "data": arc})
            continue
        entry = find_entry_by_name(db, project_id, name)
        if entry is None:
            summary["skipped"].append({"reason": "entry not found for arc", "data": arc})
            continue
        prefixed = f"[arc] {note}"
        combined = (entry.notes + "\n\n" + prefixed).strip() if entry.notes else prefixed
        db.update_psyke_entry(
            entry_id=entry.id,
            name=entry.name,
            entry_type=entry.entry_type,
            aliases=entry.aliases or "",
            notes=combined,
            is_global=bool(entry.is_global),
        )
        summary["arcs_updated"].append({"id": entry.id, "name": name})

    return summary
