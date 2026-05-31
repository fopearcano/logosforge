"""Controlled Assistant context injection (Phase 8B).

Decides — conservatively and deterministically — whether the Strategy Layer,
Narrative Health, and PSYKE Diagnostics should contribute short, labelled blocks
to the Assistant prompt. It reads settings flags and hard caps so the Assistant
benefits from the intelligence layers without ever receiving a bloated dump.

Pure logic: no Qt, no LLM call, no DB mutation. Each builder is invoked through
the existing read-only gatherers. Returns one combined string (possibly empty)
the caller prepends to its structural context block.
"""

from __future__ import annotations

# Settings keys + conservative defaults.
_KEY_STRATEGY = "include_strategy_in_assistant_context"
_KEY_HEALTH = "include_health_in_assistant_context"
_KEY_DIAGNOSTICS = "include_diagnostics_in_assistant_context"
_KEY_MAX_HEALTH = "max_health_risks_in_context"
_KEY_MAX_DIAG = "max_diagnostics_in_context"

_DEFAULTS = {
    _KEY_STRATEGY: True,
    _KEY_HEALTH: False,        # off by default — health is expensive/broad
    _KEY_DIAGNOSTICS: True,
    _KEY_MAX_HEALTH: 3,
    _KEY_MAX_DIAG: 5,
}


def _flag(key: str) -> bool:
    try:
        from storyplanner.settings import get_manager
        val = get_manager().get(key)
        return _DEFAULTS[key] if val is None else bool(val)
    except Exception:
        return bool(_DEFAULTS.get(key, False))


def _limit(key: str) -> int:
    try:
        from storyplanner.settings import get_manager
        val = get_manager().get(key)
        return int(_DEFAULTS[key] if val is None else val)
    except Exception:
        return int(_DEFAULTS.get(key, 3))


def gather_injected_context(
    db,
    project_id: int,
    *,
    section_name: str = "",
    scene_id: int | None = None,
) -> str:
    """Assemble the (possibly empty) injected context for the Assistant prompt.

    Always reads the *current* project/section/scene passed in — never caches —
    so project switching can't leak a previous project's context.
    """
    blocks: list[str] = []

    if _flag(_KEY_STRATEGY):
        blocks.append(_strategy_block(db, project_id, section_name))
    if _flag(_KEY_HEALTH):
        blocks.append(_health_block(db, project_id, _limit(_KEY_MAX_HEALTH)))
    if _flag(_KEY_DIAGNOSTICS):
        blocks.append(_diagnostics_block(
            db, project_id, section_name, scene_id, _limit(_KEY_MAX_DIAG),
        ))

    return "\n\n".join(b for b in blocks if b).strip()


# -- Individual blocks (each short, labelled, deterministic) -----------------


def _strategy_block(db, project_id: int, section_name: str) -> str:
    try:
        from storyplanner.logos.strategy.strategy_context import (
            gather_strategy_context,
        )
        return gather_strategy_context(db, project_id, section_name)
    except Exception:
        return ""


def _health_block(db, project_id: int, max_risks: int) -> str:
    try:
        from storyplanner.logos.health import HealthEngine, top_risks_text
        report = HealthEngine(db, project_id).generate_report()
        return top_risks_text(report, max_risks=max(0, max_risks))
    except Exception:
        return ""


def _diagnostics_block(
    db, project_id: int, section_name: str, scene_id: int | None, max_items: int,
) -> str:
    """Current-target diagnostics only (scene/entry), capped — never a full dump."""
    if max_items <= 0:
        return ""
    try:
        from storyplanner.logos.diagnostics import DiagnosticsEngine
        engine = DiagnosticsEngine(db, project_id)
        diags = engine.scan_project()
    except Exception:
        return ""
    if not diags:
        return ""

    # Prefer diagnostics tied to the current scene, else the section's, else the
    # most severe project-wide ones.
    def _relevant(d) -> bool:
        if scene_id is not None:
            if str(scene_id) == str(d.target_id):
                return True
            if scene_id in (d.related_scene_ids or []):
                return True
        if section_name and d.section_name == section_name:
            return True
        return False

    focused = [d for d in diags if _relevant(d)]
    pool = focused or diags  # fall back to top project-wide findings
    pool = sorted(pool, key=lambda d: (d.severity_rank, d.confidence), reverse=True)
    chosen = pool[:max_items]
    if not chosen:
        return ""

    lines = ["[Diagnostics]"]
    for d in chosen:
        lines.append(f"- {d.title} ({d.severity}) — {d.evidence}")
    return "\n".join(lines)
