"""Deterministic Logos action handlers (Phase 10C).

Some Logos actions are *diagnostic* and must run without an LLM — they compute a
rule-based result and return it directly. ``LogosController.run`` consults this
registry first; if an action has a handler here, the controller never resolves a
provider or calls the chat backend. Handlers are read-only (no DB writes) and
return a :class:`LogosResult` (preview-only — never auto-applies).
"""

from __future__ import annotations

from collections.abc import Callable

from storyplanner.logos.context import LogosContext
from storyplanner.logos.result import LogosResult

# action_name -> handler(db, context) -> LogosResult
_HANDLERS: dict[str, Callable[[object, LogosContext], LogosResult]] = {}


def register(action_name: str, handler: Callable[[object, LogosContext], LogosResult]) -> None:
    _HANDLERS[action_name] = handler


def get_handler(action_name: str):
    return _HANDLERS.get(action_name)


def is_deterministic(action_name: str) -> bool:
    return action_name in _HANDLERS


# -- Handlers ----------------------------------------------------------------


def _diagnose_scene_economy(db, context: LogosContext) -> LogosResult:
    """Run the deterministic screenplay scene-economy diagnostics for the scene."""
    action = "sp_diagnose_scene_economy"
    scene_id = context.current_scene_id
    if scene_id is None:
        return LogosResult(
            ok=True, action=action, title="Diagnose Scene Economy",
            message="Open a scene in the Manuscript to run screenplay diagnostics.",
            suggestions=[], proposed_operations=[],
        )
    try:
        from storyplanner.screenplay_diagnostics import analyze_scene_by_id
        report = analyze_scene_by_id(db, context.project_id, scene_id)
    except Exception as exc:  # never crash the UI
        return LogosResult.failure(action, f"Diagnostics failed: {exc}")

    lines = [report.summary, ""]
    lines.append(
        f"Blocks: {report.block_count}  ·  Action: {report.action_block_count}  ·  "
        f"Dialogue: {report.dialogue_block_count}  ·  Characters: "
        f"{', '.join(report.unique_characters) or '—'}"
    )
    if report.estimated_minutes:
        lines.append(f"Approx. length: ~{report.estimated_minutes} min (rough).")
    suggestions: list[str] = []
    if report.issues:
        lines.append("")
        lines.append("Issues:")
        for i in report.top_issues(8):
            lines.append(f"- [{i.severity}] {i.label} — {i.evidence}")
            if i.suggested_action:
                suggestions.append(f"{i.label}: {i.suggested_action}")
    if report.strengths:
        lines.append("")
        lines.append("Strengths: " + "; ".join(report.strengths))

    return LogosResult(
        ok=True, action=action, title="Diagnose Scene Economy",
        message="\n".join(lines), suggestions=suggestions,
        proposed_operations=[],  # diagnostic only — no mutation
    )


register("sp_diagnose_scene_economy", _diagnose_scene_economy)


def _detect_setup_payoff(db, context: LogosContext) -> LogosResult:
    action = "sp_detect_setup_payoff"
    try:
        from storyplanner.screenplay_setup_payoff import analyze_setup_payoff
        report = analyze_setup_payoff(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Setup/payoff analysis failed: {exc}")
    lines = [report.summary, ""]
    if report.unresolved_setups:
        lines.append("Unresolved setups:")
        for c in report.unresolved_setups[:5]:
            lines.append(f"- {c.label} — {c.evidence}")
    if report.possible_payoffs:
        lines.append("")
        lines.append("Possible payoffs:")
        for c in report.possible_payoffs[:5]:
            lines.append(f"- {c.label} — {c.evidence}")
    if report.recurring_motifs:
        lines.append("")
        lines.append("Recurring motifs:")
        for c in report.recurring_motifs[:5]:
            lines.append(f"- {c.label} — {c.evidence}")
    suggestions = [f"{c.label}: {c.suggested_action}"
                   for c in report.unresolved_setups[:5]]
    return LogosResult(ok=True, action=action, title="Detect Setup/Payoff Candidates",
                       message="\n".join(lines).strip(), suggestions=suggestions,
                       proposed_operations=[])


def _track_unresolved_setups(db, context: LogosContext) -> LogosResult:
    action = "sp_track_unresolved_setups"
    try:
        from storyplanner.screenplay_setup_payoff import analyze_setup_payoff
        report = analyze_setup_payoff(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Setup/payoff analysis failed: {exc}")
    items = report.unresolved_setups
    if not items:
        msg = "No unresolved setup candidates detected."
    else:
        msg = "Unresolved setup candidates:\n" + "\n".join(
            f"- {c.label} (scene {c.scene_id}) — {c.evidence}" for c in items[:10]
        )
    return LogosResult(ok=True, action=action, title="Track Unresolved Setups",
                       message=msg, suggestions=[], proposed_operations=[])


def _find_possible_payoffs(db, context: LogosContext) -> LogosResult:
    action = "sp_find_possible_payoffs"
    try:
        from storyplanner.screenplay_setup_payoff import analyze_setup_payoff
        report = analyze_setup_payoff(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Setup/payoff analysis failed: {exc}")
    items = report.possible_payoffs
    if not items:
        msg = "No possible payoffs detected (need a planted element to recur)."
    else:
        msg = "Possible payoffs:\n" + "\n".join(
            f"- {c.label} (scene {c.scene_id}) — {c.evidence}" for c in items[:10]
        )
    return LogosResult(ok=True, action=action, title="Find Possible Payoffs",
                       message=msg, suggestions=[], proposed_operations=[])


def _check_subtext(db, context: LogosContext) -> LogosResult:
    action = "sp_check_subtext"
    scene_id = context.current_scene_id
    if scene_id is None:
        return LogosResult(ok=True, action=action, title="Check Dialogue Subtext",
                           message="Open a scene to check dialogue subtext.",
                           suggestions=[], proposed_operations=[])
    try:
        from storyplanner.screenplay_subtext import analyze_subtext_by_id
        report = analyze_subtext_by_id(db, context.project_id, scene_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Subtext analysis failed: {exc}")
    lines = [report.summary]
    if report.signals:
        lines.append("")
        for s in report.top_signals(8):
            lines.append(f"- [{s.signal_type}] {s.evidence}")
    suggestions = [s.suggested_action for s in report.top_signals(5)
                   if s.suggested_action]
    return LogosResult(ok=True, action=action, title="Check Dialogue Subtext",
                       message="\n".join(lines), suggestions=suggestions,
                       proposed_operations=[])


def _find_exposition(db, context: LogosContext) -> LogosResult:
    action = "sp_find_exposition"
    scene_id = context.current_scene_id
    if scene_id is None:
        return LogosResult(ok=True, action=action, title="Find Exposition in Dialogue",
                           message="Open a scene to scan dialogue for exposition.",
                           suggestions=[], proposed_operations=[])
    try:
        from storyplanner.screenplay_subtext import (
            analyze_subtext_by_id, S_EXPOSITION_RISK,
        )
        report = analyze_subtext_by_id(db, context.project_id, scene_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Subtext analysis failed: {exc}")
    exp = [s for s in report.signals if s.signal_type == S_EXPOSITION_RISK]
    if not exp:
        msg = "No obvious exposition markers detected in this scene's dialogue."
    else:
        msg = "Possible exposition:\n" + "\n".join(f"- {s.evidence}" for s in exp)
    return LogosResult(ok=True, action=action, title="Find Exposition in Dialogue",
                       message=msg, suggestions=[], proposed_operations=[])


register("sp_detect_setup_payoff", _detect_setup_payoff)
register("sp_track_unresolved_setups", _track_unresolved_setups)
register("sp_find_possible_payoffs", _find_possible_payoffs)
register("sp_check_subtext", _check_subtext)
register("sp_find_exposition", _find_exposition)


def _show_story_links(db, context: LogosContext) -> LogosResult:
    action = "sp_show_story_links"
    try:
        from storyplanner.screenplay_graph import build_screenplay_graph
        graph = build_screenplay_graph(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Graph build failed: {exc}")
    lines = [graph.summary]
    confirmed = [e for e in graph.edges if e.status in ("confirmed", "resolved")]
    candidates = [e for e in graph.edges if e.status == "candidate"]
    if confirmed:
        lines.append("")
        lines.append("Confirmed links:")
        for e in confirmed[:8]:
            lines.append(f"- {e.edge_type}: {e.label}")
    if candidates:
        lines.append("")
        lines.append("Candidate links:")
        for e in candidates[:8]:
            lines.append(f"- {e.edge_type}: {e.label} ({e.evidence})")
    return LogosResult(ok=True, action=action, title="Show Story Link Graph",
                       message="\n".join(lines), suggestions=[],
                       proposed_operations=[])


def _explain_link(db, context: LogosContext) -> LogosResult:
    """Deterministic, evidence-first explanation of the current scene's links."""
    action = "sp_explain_link"
    try:
        from storyplanner.screenplay_graph import build_screenplay_graph
        graph = build_screenplay_graph(db, context.project_id,
                                       scene_id=context.current_scene_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Graph build failed: {exc}")
    edges = [e for e in graph.edges if e.evidence]
    if not edges:
        msg = "No story links with explicit evidence for the current scope."
    else:
        msg = "Story links (evidence):\n" + "\n".join(
            f"- {e.edge_type}: {e.label} — {e.evidence}" for e in edges[:10]
        )
    return LogosResult(ok=True, action=action, title="Explain This Link",
                       message=msg, suggestions=[], proposed_operations=[])


register("sp_show_story_links", _show_story_links)
register("sp_explain_link", _explain_link)


def _validation_report(db, project_id: int):
    from storyplanner.screenplay_export_validation import validate_screenplay_export
    from storyplanner.screenplay_render import get_export_prefs
    prefs = get_export_prefs(db, project_id)
    return validate_screenplay_export(
        db, project_id, target_format=prefs.get("export_target", "fountain"),
        prefs=prefs)


def _validate_export(db, context: LogosContext) -> LogosResult:
    action = "sp_validate_export"
    try:
        rep = _validation_report(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Validation failed: {exc}")
    lines = [rep.summary]
    if rep.blocking_errors:
        lines += ["", "Blocking errors:"] + [f"- {e}" for e in rep.blocking_errors]
    if rep.warnings:
        lines += ["", "Warnings:"] + [f"- {w}" for w in rep.warnings]
    if rep.suggestions:
        lines += ["", "Suggestions:"] + [f"- {s}" for s in rep.suggestions]
    return LogosResult(ok=True, action=action, title="Validate Screenplay Export",
                       message="\n".join(lines),
                       suggestions=list(rep.warnings[:5]), proposed_operations=[])


def _export_readiness_report(db, context: LogosContext) -> LogosResult:
    action = "sp_export_readiness_report"
    try:
        rep = _validation_report(db, context.project_id)
        from storyplanner.screenplay_render import build_render_document
        doc = build_render_document(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Report failed: {exc}")
    lines = [
        f"Target: {rep.target_format}",
        f"Export-safe: {'yes' if rep.is_export_safe else 'NO'}",
        f"Title: {doc.title or '(none)'}",
    ]
    if doc.estimated_pages is not None:
        lines.append(f"Approx. length: ~{doc.estimated_pages} pages / "
                     f"~{doc.estimated_minutes} min (approximate)")
    lines.append(rep.summary)
    return LogosResult(ok=True, action=action, title="Export Readiness Report",
                       message="\n".join(lines), suggestions=[],
                       proposed_operations=[])


def _preview_render(db, context: LogosContext) -> LogosResult:
    action = "sp_preview_render"
    try:
        from storyplanner.screenplay_render import build_render_document
        doc = build_render_document(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Render prep failed: {exc}")
    msg = (f"Render document: {len(doc.blocks)} block(s); "
           f"title '{doc.title or '(none)'}'.")
    if doc.estimated_pages is not None:
        msg += f" ~{doc.estimated_pages} pages (approximate)."
    if doc.warnings:
        msg += "\nWarnings:\n" + "\n".join(f"- {w}" for w in doc.warnings)
    return LogosResult(ok=True, action=action, title="Preview Screenplay Render",
                       message=msg, suggestions=[], proposed_operations=[])


def _find_orphans(db, context: LogosContext, *, want: str) -> LogosResult:
    action = f"sp_find_orphan_{want}"
    try:
        rep = _validation_report(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Validation failed: {exc}")
    needle = "dialogue block" if want == "dialogue" else "parenthetical"
    hits = [w for w in rep.warnings if needle in w]
    msg = ("\n".join(f"- {h}" for h in hits) if hits
           else f"No orphan {want} detected.")
    title = ("Find Orphan Dialogue" if want == "dialogue"
             else "Find Orphan Parentheticals")
    return LogosResult(ok=True, action=action, title=title, message=msg,
                       suggestions=[], proposed_operations=[])


def _check_production_polish(db, context: LogosContext) -> LogosResult:
    action = "sp_check_production_polish"
    try:
        rep = _validation_report(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Validation failed: {exc}")
    n = len(rep.blocking_errors) + len(rep.warnings)
    head = ("Looks production-clean." if n == 0
            else f"{n} format issue(s) to review before export.")
    lines = [head] + [f"- {w}" for w in (rep.blocking_errors + rep.warnings)[:8]]
    return LogosResult(ok=True, action=action, title="Check Production Polish",
                       message="\n".join(lines), suggestions=[],
                       proposed_operations=[])


register("sp_validate_export", _validate_export)
register("sp_export_readiness_report", _export_readiness_report)
register("sp_preview_render", _preview_render)
register("sp_find_orphan_dialogue", lambda db, c: _find_orphans(db, c, want="dialogue"))
register("sp_find_orphan_parenthetical",
         lambda db, c: _find_orphans(db, c, want="parenthetical"))
register("sp_check_production_polish", _check_production_polish)


def _fountain_text(db, project_id: int) -> str:
    from storyplanner.export import export_screenplay_fountain
    return export_screenplay_fountain(db, project_id)


def _fountain_validate(db, context: LogosContext) -> LogosResult:
    action = "sp_validate_fountain_export"
    try:
        from storyplanner.screenplay_fountain import validate_fountain_export
        rep = validate_fountain_export(_fountain_text(db, context.project_id))
    except Exception as exc:
        return LogosResult.failure(action, f"Fountain validation failed: {exc}")
    lines = [rep.summary]
    if rep.blocking_errors:
        lines += ["", "Blocking:"] + [f"- {e}" for e in rep.blocking_errors]
    if rep.warnings:
        lines += ["", "Warnings:"] + [f"- {w}" for w in rep.warnings]
    return LogosResult(ok=True, action=action, title="Validate Fountain Export",
                       message="\n".join(lines), suggestions=list(rep.warnings[:5]),
                       proposed_operations=[])


def _fountain_preview(db, context: LogosContext) -> LogosResult:
    action = "sp_preview_fountain"
    try:
        text = _fountain_text(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Fountain export failed: {exc}")
    head = "\n".join(text.splitlines()[:24])
    more = "" if text.count("\n") <= 24 else "\n…(truncated preview)"
    return LogosResult(ok=True, action=action, title="Preview Fountain Output",
                       message=head + more, suggestions=[], proposed_operations=[])


def _fountain_compat(db, context: LogosContext) -> LogosResult:
    action = "sp_check_fountain_compatibility"
    try:
        from storyplanner.export import export_screenplay_fountain_result
        res = export_screenplay_fountain_result(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Fountain export failed: {exc}")
    if not res.warnings:
        msg = "Screenplay maps cleanly to Fountain — no compatibility warnings."
    else:
        msg = "Fountain compatibility notes:\n" + "\n".join(
            f"- {w}" for w in res.warnings[:10])
    return LogosResult(ok=True, action=action, title="Check Fountain Compatibility",
                       message=msg, suggestions=[], proposed_operations=[])


def _fountain_ambiguous(db, context: LogosContext) -> LogosResult:
    action = "sp_find_ambiguous_fountain"
    try:
        from storyplanner.export import export_screenplay_fountain_result
        res = export_screenplay_fountain_result(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Fountain export failed: {exc}")
    amb = [w for w in res.warnings if "ambiguous" in w.lower() or "forced" in w.lower()]
    msg = ("\n".join(f"- {w}" for w in amb) if amb
           else "No ambiguous Fountain elements detected.")
    return LogosResult(ok=True, action=action, title="Find Ambiguous Fountain Elements",
                       message=msg, suggestions=[], proposed_operations=[])


def _fountain_explain_warning(db, context: LogosContext) -> LogosResult:
    action = "sp_explain_fountain_warning"
    try:
        from storyplanner.screenplay_fountain import validate_fountain_export
        rep = validate_fountain_export(_fountain_text(db, context.project_id))
    except Exception as exc:
        return LogosResult.failure(action, f"Fountain validation failed: {exc}")
    if not rep.warnings:
        msg = "No Fountain warnings to explain."
    else:
        msg = ("Fountain warnings (deterministic):\n"
               + "\n".join(f"- {w}" for w in rep.warnings))
    return LogosResult(ok=True, action=action, title="Explain Fountain Warning",
                       message=msg, suggestions=[], proposed_operations=[])


def _fountain_prepare(db, context: LogosContext) -> LogosResult:
    action = "sp_prepare_for_fountain"
    try:
        from storyplanner.screenplay_fountain import validate_fountain_export
        from storyplanner.screenplay_render import get_title_page
        rep = validate_fountain_export(_fountain_text(db, context.project_id))
        title = (get_title_page(db, context.project_id).get("title") or "").strip()
    except Exception as exc:
        return LogosResult.failure(action, f"Preparation failed: {exc}")
    steps = []
    if not title:
        steps.append("Set a title page (Title/Author).")
    for w in rep.warnings:
        steps.append(f"Review: {w}")
    msg = ("Ready to export as .fountain." if not steps
           else "Before exporting as .fountain:\n" + "\n".join(f"- {s}" for s in steps))
    return LogosResult(ok=True, action=action, title="Prepare Screenplay for Fountain Export",
                       message=msg, suggestions=steps[:5], proposed_operations=[])


register("sp_validate_fountain_export", _fountain_validate)
register("sp_preview_fountain", _fountain_preview)
register("sp_check_fountain_compatibility", _fountain_compat)
register("sp_find_ambiguous_fountain", _fountain_ambiguous)
register("sp_explain_fountain_warning", _fountain_explain_warning)
register("sp_prepare_for_fountain", _fountain_prepare)
