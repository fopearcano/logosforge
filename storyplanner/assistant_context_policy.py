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
_KEY_PROJECT_MODE = "include_project_mode_in_assistant_context"
_KEY_SCREENPLAY_DIAG = "include_screenplay_diagnostics_in_assistant_context"
_KEY_SCREENPLAY_TRACK = "include_screenplay_tracking_in_assistant_context"
_KEY_SCREENPLAY_LINKS = "include_screenplay_links_in_assistant_context"
_KEY_SCREENPLAY_EXPORT = "include_screenplay_export_in_assistant_context"
_KEY_STRATEGY = "include_strategy_in_assistant_context"
_KEY_HEALTH = "include_health_in_assistant_context"
_KEY_DIAGNOSTICS = "include_diagnostics_in_assistant_context"
_KEY_MAX_HEALTH = "max_health_risks_in_context"
_KEY_MAX_DIAG = "max_diagnostics_in_context"

_DEFAULTS = {
    _KEY_PROJECT_MODE: True,   # on by default — tiny, deterministic, always relevant
    _KEY_SCREENPLAY_DIAG: True,  # screenplay-only; concise top-issues summary
    _KEY_SCREENPLAY_TRACK: True,  # screenplay-only; setup/payoff + subtext summaries
    _KEY_SCREENPLAY_LINKS: True,  # screenplay-only; confirmed + candidate story links
    _KEY_SCREENPLAY_EXPORT: True,  # screenplay-only; export readiness summary
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

    if _flag(_KEY_PROJECT_MODE):
        blocks.append(_project_mode_block(db, project_id))
        blocks.append(_screenplay_scene_block(db, project_id, scene_id))
    if _flag(_KEY_SCREENPLAY_DIAG):
        blocks.append(_screenplay_diagnostics_block(db, project_id, scene_id))
    if _flag(_KEY_SCREENPLAY_TRACK):
        blocks.append(_screenplay_setup_payoff_block(db, project_id, scene_id))
        blocks.append(_screenplay_subtext_block(db, project_id, scene_id))
    if _flag(_KEY_SCREENPLAY_LINKS):
        blocks.append(_screenplay_links_block(db, project_id, scene_id))
    if _flag(_KEY_SCREENPLAY_EXPORT):
        blocks.append(_screenplay_export_block(db, project_id, scene_id))
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


def _project_mode_block(db, project_id: int) -> str:
    """Tiny ``[Project Mode]`` block — mode name + primary medium constraints."""
    try:
        from storyplanner.writing_modes import (
            get_project_writing_mode_by_id,
            mode_context_block,
        )
        return mode_context_block(get_project_writing_mode_by_id(db, project_id))
    except Exception:
        return ""


def _screenplay_scene_block(db, project_id: int, scene_id: int | None) -> str:
    """Concise ``[Screenplay Scene]`` line — only for screenplay projects with a
    current scene. Lists the character cues actually present in the scene (parsed
    from its text) plus the scene heading. Data-driven, capped, no LLM/DB write.
    """
    if scene_id is None:
        return ""
    try:
        from storyplanner.writing_modes import get_project_writing_mode_by_id
        if get_project_writing_mode_by_id(db, project_id) != "screenplay":
            return ""
        scene = db.get_scene_by_id(scene_id)
        if scene is None:
            return ""
        from storyplanner.screenplay_blocks import (
            character_cues,
            parse_screenplay_text,
        )
        blocks = parse_screenplay_text(getattr(scene, "content", "") or "")
        cues = character_cues(blocks)[:8]
        lines = ["[Screenplay Scene]"]
        heading = (getattr(scene, "slugline", "") or getattr(scene, "title", "")
                   or "").strip()
        if heading:
            lines.append(f"Heading: {heading.upper()}")
        if cues:
            lines.append("Characters present: " + ", ".join(cues))
        return "\n".join(lines) if len(lines) > 1 else ""
    except Exception:
        return ""


def _screenplay_diagnostics_block(db, project_id: int, scene_id: int | None) -> str:
    """Concise ``[Screenplay Diagnostics]`` block — economy summary + top 3 issues.

    Screenplay projects with a current scene only. Deterministic (rule-based), no
    LLM, no DB write; capped at three issues so the prompt never bloats.
    """
    if scene_id is None:
        return ""
    try:
        from storyplanner.writing_modes import get_project_writing_mode_by_id
        if get_project_writing_mode_by_id(db, project_id) != "screenplay":
            return ""
        from storyplanner.screenplay_diagnostics import analyze_scene_by_id
        report = analyze_scene_by_id(db, project_id, scene_id)
        if report.block_count == 0:
            return ""
        lines = ["[Screenplay Diagnostics]",
                 f"Scene economy: {report.economy_label or 'unknown'}."]
        top = report.top_issues(3)
        if top:
            lines.append("Top issues:")
            for n, i in enumerate(top, 1):
                lines.append(f"{n}. {i.label}.")
        return "\n".join(lines)
    except Exception:
        return ""


def _is_screenplay(db, project_id: int) -> bool:
    try:
        from storyplanner.writing_modes import get_project_writing_mode_by_id
        return get_project_writing_mode_by_id(db, project_id) == "screenplay"
    except Exception:
        return False


def _screenplay_setup_payoff_block(db, project_id: int, scene_id: int | None) -> str:
    """Capped ``[Screenplay Setup/Payoff]`` — 3 unresolved / 3 payoffs / 3 motifs."""
    if scene_id is None or not _is_screenplay(db, project_id):
        return ""
    try:
        from storyplanner.screenplay_setup_payoff import analyze_setup_payoff
        report = analyze_setup_payoff(db, project_id)
        if not (report.unresolved_setups or report.possible_payoffs
                or report.recurring_motifs):
            return ""
        lines = ["[Screenplay Setup/Payoff]"]
        for label, items in (
            ("Unresolved setups", report.unresolved_setups),
            ("Possible payoffs", report.possible_payoffs),
            ("Recurring motifs", report.recurring_motifs),
        ):
            for c in items[:3]:
                lines.append(f"- {label[:-1] if label.endswith('s') else label}: {c.label}")
        return "\n".join(lines)
    except Exception:
        return ""


def _screenplay_subtext_block(db, project_id: int, scene_id: int | None) -> str:
    """Capped ``[Screenplay Subtext]`` — status + top 3 signals for the scene."""
    if scene_id is None or not _is_screenplay(db, project_id):
        return ""
    try:
        from storyplanner.screenplay_subtext import analyze_subtext_by_id
        report = analyze_subtext_by_id(db, project_id, scene_id)
        if not report.signals:
            return ""
        lines = ["[Screenplay Subtext]", report.summary]
        for s in report.top_signals(3):
            lines.append(f"- {s.signal_type}: {s.evidence}")
        return "\n".join(lines)
    except Exception:
        return ""


def _screenplay_links_block(db, project_id: int, scene_id: int | None) -> str:
    """Capped ``[Screenplay Story Links]`` — confirmed + candidate links."""
    if scene_id is None or not _is_screenplay(db, project_id):
        return ""
    try:
        from storyplanner.screenplay_graph import build_screenplay_graph
        graph = build_screenplay_graph(db, project_id)
        if not graph.edges:
            return ""
        confirmed = [e for e in graph.edges if e.status in ("confirmed", "resolved")]
        setup_cand = [e for e in graph.edges
                      if e.status == "candidate" and e.edge_type == "setup_to_payoff"]
        motif = [e for e in graph.edges if e.edge_type == "motif_recurrence"]
        if not (confirmed or setup_cand or motif):
            return ""
        lines = ["[Screenplay Story Links]"]
        for label, items in (("Confirmed", confirmed),
                             ("Candidate setup/payoff", setup_cand),
                             ("Motif", motif)):
            for e in items[:3]:
                lines.append(f"- {label}: {e.label}")
        return "\n".join(lines)
    except Exception:
        return ""


def _screenplay_export_block(db, project_id: int, scene_id: int | None) -> str:
    """Capped ``[Screenplay Export Readiness]`` — target, top issues, title, length."""
    if scene_id is None or not _is_screenplay(db, project_id):
        return ""
    try:
        from storyplanner.screenplay_render import get_export_prefs, get_title_page
        from storyplanner.screenplay_export_validation import (
            validate_screenplay_export,
        )
        prefs = get_export_prefs(db, project_id)
        rep = validate_screenplay_export(
            db, project_id, target_format=prefs.get("export_target", "fountain"),
            prefs=prefs)
        title = (get_title_page(db, project_id).get("title") or "").strip()
        lines = ["[Screenplay Export Readiness]",
                 f"Target: {rep.target_format}",
                 f"Title page: {'set' if title else 'missing'}"]
        if rep.blocking_errors:
            lines.append("Blocking: " + "; ".join(rep.blocking_errors[:3]))
        if rep.warnings:
            lines.append("Warnings: " + "; ".join(rep.warnings[:3]))
        if len(lines) == 3 and rep.is_export_safe:
            lines.append("No blocking issues.")
        return "\n".join(lines)
    except Exception:
        return ""


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
