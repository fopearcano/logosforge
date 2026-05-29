"""Plot and Timeline behavior for the Stage Script Engine.

Deterministic, pure helpers that make Plot and Timeline theatre-aware:
scenes grouped by acts as plot blocks, a performance-order timeline with
entrances/exits, cues, offstage events, prop continuity and emotional
pressure, plus compact entrance/exit and cue markers.

No UI / Tauri / filesystem / provider imports — the views consume these.
"""

from __future__ import annotations

from typing import Any


def _character_names(db: Any, project_id: int) -> dict[int, str]:
    try:
        return {c.id: c.name for c in db.get_all_characters(project_id)}
    except Exception:
        return {}


def _psyke_names(db: Any, project_id: int) -> dict[int, str]:
    try:
        return {e.id: e.name for e in db.get_all_psyke_entries(project_id)}
    except Exception:
        return {}


def _characters_on_stage(db: Any, scene_id: int, names: dict[int, str]) -> list[str]:
    try:
        cids = db.get_scene_character_ids(scene_id)
    except Exception:
        cids = []
    return [names.get(cid, f"#{cid}") for cid in cids]


def _important_props(db: Any, scene: Any, psyke_names: dict[int, str]) -> list[str]:
    props: list[str] = []
    try:
        for biz in db.get_stage_business(scene.id):
            name = psyke_names.get(biz.prop_psyke_entry_id)
            if name and name not in props:
                props.append(name)
    except Exception:
        pass
    if not props and (getattr(scene, "prop_notes", "") or "").strip():
        props.append(scene.prop_notes.strip())
    return props


def _emotional_pressure(scene: Any) -> str:
    """Compact pressure read for a scene."""
    if (getattr(scene, "dramatic_turn", "") or "").strip():
        return "turn"
    if (getattr(scene, "conflict", "") or "").strip():
        return "conflict"
    if (getattr(scene, "scene_objective", "") or "").strip():
        return "pursuit"
    return "flat"


# ---------------------------------------------------------------------------
# Plot grid (§1):  Scenes grouped by Acts
# ---------------------------------------------------------------------------

def _scene_block(db: Any, scene: Any, names: dict, psyke_names: dict) -> dict:
    ee = db.get_stage_entrances_exits(scene.id)
    return {
        "id": scene.id,
        "title": scene.title,
        "act": (scene.act or "").strip(),
        "scene_objective": getattr(scene, "scene_objective", "") or "",
        "dramatic_turn": getattr(scene, "dramatic_turn", "") or "",
        "characters_on_stage": _characters_on_stage(db, scene.id, names),
        "entrance_exit_count": len(ee),
        "important_props": _important_props(db, scene, psyke_names),
        "estimated_duration": getattr(scene, "performance_duration_minutes", 0) or 0,
    }


def get_stage_plot_blocks(db: Any, project_id: int) -> list[dict]:
    """One block per scene (with theatre metadata), in reading order."""
    names = _character_names(db, project_id)
    psyke_names = _psyke_names(db, project_id)
    return [
        _scene_block(db, s, names, psyke_names)
        for s in db.get_all_scenes(project_id)
    ]


def get_stage_plot_acts(db: Any, project_id: int) -> list[dict]:
    """Scenes grouped by act, preserving act + scene order.

    Returns [{act, scenes:[block, ...]}] with an act label (empty acts
    grouped under "")."""
    groups: list[dict] = []
    index: dict[str, dict] = {}
    for block in get_stage_plot_blocks(db, project_id):
        act = block["act"]
        if act not in index:
            grp = {"act": act, "scenes": []}
            index[act] = grp
            groups.append(grp)
        index[act]["scenes"].append(block)
    return groups


# ---------------------------------------------------------------------------
# Timeline (§2):  performance order with entrances/exits, cues, etc.
# ---------------------------------------------------------------------------

def get_stage_timeline(db: Any, project_id: int) -> list[dict]:
    """Ordered performance rows, one per scene."""
    names = _character_names(db, project_id)
    rows: list[dict] = []
    for idx, scene in enumerate(db.get_all_scenes(project_id), start=1):
        ee = db.get_stage_entrances_exits(scene.id)
        cues = db.get_stage_cues(scene.id)
        rows.append({
            "scene_id": scene.id,
            "order": idx,
            "act": (scene.act or "").strip(),
            "title": scene.title,
            "entrances_exits": [
                {"character": names.get(e.character_id, ""), "type": e.type}
                for e in ee
            ],
            "entrance_exit_count": len(ee),
            "cues": [{"type": c.cue_type, "text": c.cue_text} for c in cues],
            "cue_count": len(cues),
            "offstage_events": getattr(scene, "offstage_events", "") or "",
            "prop_continuity": _important_props(
                db, scene, _psyke_names(db, project_id),
            ),
            "emotional_pressure": _emotional_pressure(scene),
        })
    return rows


def get_act_progression(db: Any, project_id: int) -> list[str]:
    """Act labels in performance order (deduped, preserving first-seen)."""
    seen: list[str] = []
    for scene in db.get_all_scenes(project_id):
        act = (scene.act or "").strip()
        if act and act not in seen:
            seen.append(act)
    return seen


# ---------------------------------------------------------------------------
# Entrance/Exit display (§3) + Cue display (§4)
# ---------------------------------------------------------------------------

def get_entrance_exit_markers(db: Any, project_id: int, scene_id: int) -> list[dict]:
    """Compact entrance/exit markers for a scene (+ offstage flag)."""
    names = _character_names(db, project_id)
    markers = [
        {
            "character": names.get(e.character_id, ""),
            "type": e.type,                 # entrance | exit
            "moment_order": e.moment_order,
            "cue_text": e.cue_text,
        }
        for e in db.get_stage_entrances_exits(scene_id)
    ]
    scene = db.get_scene_by_id(scene_id)
    if scene is not None and (getattr(scene, "offstage_events", "") or "").strip():
        markers.append({
            "character": "",
            "type": "offstage",
            "moment_order": 9999,
            "cue_text": scene.offstage_events,
        })
    return markers


def get_cue_markers(db: Any, scene_id: int) -> list[dict]:
    """Compact cue markers for a scene (light/sound/music/movement/prop)."""
    return [
        {
            "cue_type": c.cue_type,
            "text": c.cue_text,
            "moment_order": c.moment_order,
        }
        for c in db.get_stage_cues(scene_id)
    ]
