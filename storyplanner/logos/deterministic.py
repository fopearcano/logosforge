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


# -- Phase 10H — professional output (DOCX / PDF / FDX) -----------------------


def _output_report(db, project_id: int, target: str):
    from storyplanner.screenplay_output_validation import validate_professional_output
    return validate_professional_output(db, project_id, target_format=target)


def _validate_professional_output(db, context: LogosContext) -> LogosResult:
    action = "sp_validate_professional_output"
    try:
        rep = _output_report(db, context.project_id, "docx")
    except Exception as exc:
        return LogosResult.failure(action, f"Output validation failed: {exc}")
    lines = [f"Available formats: {', '.join(rep.available_formats)}",
             f"Target: {rep.target_format} ({rep.compatibility_level})",
             f"Export-safe: {'yes' if rep.is_export_safe else 'NO'}"]
    if rep.blocking_errors:
        lines += ["Blocking:"] + [f"- {e}" for e in rep.blocking_errors]
    if rep.warnings:
        lines += ["Warnings:"] + [f"- {w}" for w in rep.warnings[:6]]
    return LogosResult(ok=True, action=action, title="Validate Professional Output",
                       message="\n".join(lines), suggestions=list(rep.suggestions[:5]),
                       proposed_operations=[])


def _output_readiness_report(db, context: LogosContext) -> LogosResult:
    action = "sp_output_readiness_report"
    try:
        from storyplanner.screenplay_output_validation import available_output_formats
        from storyplanner.screenplay_render import build_render_document, get_title_page
        doc = build_render_document(db, context.project_id)
        title = (get_title_page(db, context.project_id).get("title") or "").strip()
    except Exception as exc:
        return LogosResult.failure(action, f"Report failed: {exc}")
    lines = [f"Formats: {', '.join(available_output_formats())}",
             f"Title page: {title or '(none)'}",
             f"Blocks: {len(doc.blocks)}"]
    if doc.estimated_pages is not None:
        lines.append(f"Approx. length: ~{doc.estimated_pages} pages (approximate)")
    return LogosResult(ok=True, action=action, title="Output Readiness Report",
                       message="\n".join(lines), suggestions=[], proposed_operations=[])


def _preview_output(db, context: LogosContext) -> LogosResult:
    action = "sp_preview_output"
    try:
        from storyplanner.export import export_professional_preview_html
        html = export_professional_preview_html(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Preview failed: {exc}")
    return LogosResult(ok=True, action=action, title="Preview Screenplay Output",
                       message=f"Preview HTML generated ({len(html)} chars). "
                               "Open it in a browser and print to PDF for best fidelity.",
                       suggestions=[], proposed_operations=[])


def _check_pdf_readiness(db, context: LogosContext) -> LogosResult:
    action = "sp_check_pdf_readiness"
    rep = _output_report(db, context.project_id, "pdf")
    msg = (f"PDF target: {rep.compatibility_level}. "
           + ("Export-safe. " if rep.is_export_safe else "NOT safe. ")
           + " ".join(rep.warnings[:3]))
    return LogosResult(ok=True, action=action, title="Check PDF Readiness",
                       message=msg, suggestions=list(rep.suggestions[:3]),
                       proposed_operations=[])


def _check_fdx_feasibility(db, context: LogosContext) -> LogosResult:
    action = "sp_check_fdx_feasibility"
    rep = _output_report(db, context.project_id, "fdx")
    msg = (f"FDX target: {rep.compatibility_level} (experimental, unverified). "
           + " ".join(rep.warnings[:3]))
    return LogosResult(ok=True, action=action, title="Check FDX Feasibility",
                       message=msg, suggestions=["Prefer .fountain for Final Draft."],
                       proposed_operations=[])


def _explain_export_warnings(db, context: LogosContext) -> LogosResult:
    action = "sp_explain_export_warnings"
    rep = _output_report(db, context.project_id, "docx")
    msg = ("No export warnings." if not rep.warnings
           else "Export warnings (deterministic):\n"
           + "\n".join(f"- {w}" for w in rep.warnings))
    return LogosResult(ok=True, action=action, title="Explain Export Warnings",
                       message=msg, suggestions=[], proposed_operations=[])


def _prepare_professional(db, context: LogosContext) -> LogosResult:
    action = "sp_prepare_professional_export"
    rep = _output_report(db, context.project_id, "docx")
    steps = list(rep.blocking_errors) + list(rep.warnings)
    msg = ("Ready for professional export (DOCX stable; PDF preview; FDX experimental)."
           if not steps else "Before professional export:\n"
           + "\n".join(f"- {s}" for s in steps[:8]))
    return LogosResult(ok=True, action=action, title="Prepare Screenplay for Professional Export",
                       message=msg, suggestions=steps[:5], proposed_operations=[])


register("sp_validate_professional_output", _validate_professional_output)
register("sp_output_readiness_report", _output_readiness_report)
register("sp_preview_output", _preview_output)
register("sp_check_pdf_readiness", _check_pdf_readiness)
register("sp_check_fdx_feasibility", _check_fdx_feasibility)
register("sp_explain_export_warnings", _explain_export_warnings)
register("sp_prepare_professional_export", _prepare_professional)


# -- Phase 10J — production draft (read-only status/validation; mutations are a
#    separate, explicit service API) ------------------------------------------


def _production_status(db, context: LogosContext) -> LogosResult:
    action = "sp_production_status"
    try:
        from storyplanner.screenplay_production import production_status
        st = production_status(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Status failed: {exc}")
    if not st.get("active"):
        msg = "Spec draft (production mode not enabled)."
    else:
        msg = "\n".join([
            f"Mode: production — {st.get('draft_label', '')}",
            f"Scene numbering: {'on' if st.get('scene_numbering_enabled') else 'off'}",
            f"Numbered scenes: {st.get('numbered_scenes', 0)}; "
            f"omitted: {st.get('omitted_scenes', 0)}",
            f"Revision sets: {st.get('revision_sets', 0)}"
            + (f" (latest: {st['active_revision_set']})" if st.get('active_revision_set') else ""),
            f"Page locking: {st.get('page_locking_status', 'disabled')}",
        ])
        if st.get("warnings"):
            msg += "\nWarnings:\n" + "\n".join(f"- {w}" for w in st["warnings"][:3])
    return LogosResult(ok=True, action=action, title="Production Draft Status",
                       message=msg, suggestions=[], proposed_operations=[])


def _validate_production(db, context: LogosContext) -> LogosResult:
    action = "sp_validate_production"
    try:
        from storyplanner.screenplay_production import validate_production_draft
        rep = validate_production_draft(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Validation failed: {exc}")
    lines = [f"Readiness: {rep.readiness_level}"]
    if rep.blocking_errors:
        lines += ["Blocking:"] + [f"- {e}" for e in rep.blocking_errors]
    if rep.warnings:
        lines += ["Warnings:"] + [f"- {w}" for w in rep.warnings[:5]]
    if rep.suggestions:
        lines += ["Suggestions:"] + [f"- {s}" for s in rep.suggestions[:3]]
    return LogosResult(ok=True, action=action, title="Validate Production Draft",
                       message="\n".join(lines), suggestions=list(rep.suggestions[:3]),
                       proposed_operations=[])


def _check_duplicate_scene_numbers(db, context: LogosContext) -> LogosResult:
    action = "sp_check_duplicate_scene_numbers"
    try:
        from storyplanner.screenplay_production import validate_scene_numbers
        problems = validate_scene_numbers(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Check failed: {exc}")
    dupes = [p for p in problems if "Duplicate" in p]
    msg = ("No duplicate scene numbers." if not dupes
           else "\n".join(f"- {d}" for d in dupes))
    return LogosResult(ok=True, action=action, title="Check Duplicate Scene Numbers",
                       message=msg, suggestions=[], proposed_operations=[])


def _summarize_revision_set(db, context: LogosContext) -> LogosResult:
    action = "sp_summarize_revision_set"
    try:
        draft = db.get_active_production_draft(context.project_id)
        revs = db.get_revision_sets(draft.id) if draft else []
    except Exception as exc:
        return LogosResult.failure(action, f"Summary failed: {exc}")
    if not revs:
        msg = "No revision sets."
    else:
        changes = db.get_revision_changes(draft.id)
        latest = revs[-1]
        n = sum(1 for c in changes if c.revision_set_id == latest.id)
        msg = (f"Latest revision: {latest.label} ({latest.color_name}, "
               f"{latest.status}) — {n} scene change(s). Total sets: {len(revs)}.")
    return LogosResult(ok=True, action=action, title="Summarize Revision Set",
                       message=msg, suggestions=[], proposed_operations=[])


def _explain_page_locking(db, context: LogosContext) -> LogosResult:
    action = "sp_explain_page_locking"
    msg = ("Page locking is APPROXIMATE: pagination is line-count based, not "
           "page-accurate, so true page locking (stable page labels, 10A inserts) "
           "is deferred. Use scene numbers + revision sets for production tracking.")
    return LogosResult(ok=True, action=action, title="Explain Page Locking Status",
                       message=msg, suggestions=[], proposed_operations=[])


def _check_fountain_production_export(db, context: LogosContext) -> LogosResult:
    action = "sp_check_fountain_production_export"
    try:
        from storyplanner.export import export_production_fountain
        text = export_production_fountain(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Export check failed: {exc}")
    has_numbers = "#" in text
    msg = ("Production Fountain export ready"
           + (" (scene numbers present)." if has_numbers
              else " (no scene numbers — assign them first)."))
    return LogosResult(ok=True, action=action, title="Check Fountain Production Export",
                       message=msg, suggestions=[], proposed_operations=[])


def _prepare_production_export(db, context: LogosContext) -> LogosResult:
    action = "sp_prepare_production_export"
    try:
        from storyplanner.screenplay_production import validate_production_draft
        rep = validate_production_draft(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Preparation failed: {exc}")
    steps = list(rep.blocking_errors) + list(rep.warnings)
    msg = (f"Readiness: {rep.readiness_level}. "
           + ("Ready for production export." if not steps
              else "Review:\n" + "\n".join(f"- {s}" for s in steps[:6])))
    return LogosResult(ok=True, action=action,
                       title="Prepare Screenplay for Production Export",
                       message=msg, suggestions=steps[:5], proposed_operations=[])


register("sp_production_status", _production_status)
register("sp_validate_production", _validate_production)
register("sp_check_duplicate_scene_numbers", _check_duplicate_scene_numbers)
register("sp_summarize_revision_set", _summarize_revision_set)
register("sp_explain_page_locking", _explain_page_locking)
register("sp_check_fountain_production_export", _check_fountain_production_export)
register("sp_prepare_production_export", _prepare_production_export)


# -- Phase 10K — revision intelligence (read-only; saving a report is a separate
#    explicit service call) -----------------------------------------------------


def _impact_map(db, context: LogosContext):
    from storyplanner.revision_intelligence.impact_map import build_revision_impact_map
    return build_revision_impact_map(db, context.project_id,
                                     scene_id=context.current_scene_id)


def _needs_scene(action: str, title: str) -> LogosResult:
    return LogosResult(ok=True, action=action, title=title,
                       message="Open a scene to run revision intelligence.",
                       suggestions=[], proposed_operations=[])


def _revision_impact(db, context: LogosContext) -> LogosResult:
    action = "sp_revision_impact"
    if context.current_scene_id is None:
        return _needs_scene(action, "Revision Impact Map")
    try:
        m = _impact_map(db, context)
    except Exception as exc:
        return LogosResult.failure(action, f"Impact map failed: {exc}")
    lines = [m.summary]
    if m.impacted_scenes:
        lines.append("Impacted scenes: " + ", ".join(
            f"{s['label']} ({s['confidence']})" for s in m.impacted_scenes[:3]))
    if m.impacted_psyke_entries:
        lines.append("PSYKE: " + ", ".join(
            p["name"] for p in m.impacted_psyke_entries[:3]))
    if m.limitations:
        lines.append("Limitations: " + "; ".join(m.limitations))
    return LogosResult(ok=True, action=action, title="Generate Revision Impact Map",
                       message="\n".join(lines), suggestions=[], proposed_operations=[])


def _check_psyke_impact(db, context: LogosContext) -> LogosResult:
    action = "sp_check_psyke_impact"
    if context.current_scene_id is None:
        return _needs_scene(action, "Check PSYKE Impact")
    m = _impact_map(db, context)
    if not m.impacted_psyke_entries:
        msg = "No PSYKE entries detected in this scene."
    else:
        msg = "\n".join(f"- {p['name']} ({p['impact_kind']}, {p['confidence']})"
                        for p in m.impacted_psyke_entries[:10])
    return LogosResult(ok=True, action=action, title="Check PSYKE Impact",
                       message=msg, suggestions=[], proposed_operations=[])


def _check_setup_payoff_impact(db, context: LogosContext) -> LogosResult:
    action = "sp_check_setup_payoff_impact"
    if context.current_scene_id is None:
        return _needs_scene(action, "Check Setup/Payoff Impact")
    m = _impact_map(db, context)
    if not m.setup_payoff_impacts:
        msg = "No setup/payoff chains connected to this scene."
    else:
        msg = "\n".join(f"- {s['label']} ({s['impact_kind']})"
                        for s in m.setup_payoff_impacts[:10])
    return LogosResult(ok=True, action=action, title="Check Setup/Payoff Impact",
                       message=msg, suggestions=[], proposed_operations=[])


def _check_continuity_impact(db, context: LogosContext) -> LogosResult:
    action = "sp_check_continuity_impact"
    if context.current_scene_id is None:
        return _needs_scene(action, "Check Continuity Impact")
    m = _impact_map(db, context)
    msg = "\n".join(f"- {c['label']} ({c['confidence']})"
                    for c in m.continuity_impacts[:10])
    return LogosResult(ok=True, action=action, title="Check Continuity Impact",
                       message=msg, suggestions=[], proposed_operations=[])


def _check_impacted_scenes(db, context: LogosContext) -> LogosResult:
    action = "sp_check_impacted_scenes"
    if context.current_scene_id is None:
        return _needs_scene(action, "Check Impacted Scenes")
    m = _impact_map(db, context)
    if not m.impacted_scenes:
        msg = "No dependent scenes detected."
    else:
        msg = "\n".join(f"- {s['label']}: {s['impact_kind']} "
                        f"({s['confidence']}) — {s['explanation']}"
                        for s in m.impacted_scenes[:12])
    return LogosResult(ok=True, action=action, title="Check Impacted Scenes",
                       message=msg, suggestions=[], proposed_operations=[])


def _prepare_revision_followup(db, context: LogosContext) -> LogosResult:
    action = "sp_prepare_revision_followup"
    if context.current_scene_id is None:
        return _needs_scene(action, "Prepare Revision Follow-up Checklist")
    m = _impact_map(db, context)
    checks = []
    for s in m.impacted_scenes[:5]:
        if s.get("suggested_action"):
            checks.append(f"{s['label']}: {s['suggested_action']}")
    for sp in m.setup_payoff_impacts[:3]:
        if sp.get("suggested_action"):
            checks.append(sp["suggested_action"])
    if not checks:
        checks = ["No follow-up checks flagged by deterministic analysis."]
    return LogosResult(ok=True, action=action,
                       title="Prepare Revision Follow-up Checklist",
                       message="\n".join(f"- {c}" for c in checks),
                       suggestions=checks[:5], proposed_operations=[])


register("sp_revision_impact", _revision_impact)
register("sp_check_psyke_impact", _check_psyke_impact)
register("sp_check_setup_payoff_impact", _check_setup_payoff_impact)
register("sp_check_continuity_impact", _check_continuity_impact)
register("sp_check_impacted_scenes", _check_impacted_scenes)
register("sp_prepare_revision_followup", _prepare_revision_followup)


# -- Phase 10L — rewrite sandbox (writing-mode-aware, read-only status/score;
#    generation + apply are the explicit engine API) ---------------------------


def _rw_status(db, context: LogosContext) -> LogosResult:
    action = "rw_sandbox_status"
    try:
        from storyplanner.rewrite_sandbox.engine import session_status
        st = session_status(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Sandbox status failed: {exc}")
    if not st.get("active"):
        msg = ("No open rewrite session. Use the Rewrite Sandbox to generate "
               "variants for a selection/scene — nothing is applied automatically.")
    else:
        lines = [f"Source: {st['source_type']} ({st['writing_mode']})",
                 f"Variants: {st['variant_count']}"
                 + (f"; preferred: {st['preferred']}" if st.get("preferred") else ""),
                 f"Stale source: {'yes' if st['stale'] else 'no'}"]
        if st.get("psyke_terms_removed"):
            lines.append(f"PSYKE references removed across variants: "
                         f"{st['psyke_terms_removed']}")
        if st.get("warnings"):
            lines.append("Warnings: " + "; ".join(st["warnings"]))
        msg = "\n".join(lines)
    return LogosResult(ok=True, action=action, title="Rewrite Sandbox",
                       message=msg, suggestions=[], proposed_operations=[])


def _rw_explain_tradeoffs(db, context: LogosContext) -> LogosResult:
    action = "rw_explain_tradeoffs"
    import json
    try:
        sess = db.get_latest_rewrite_session(context.project_id, status="open")
        variants = db.get_rewrite_variants(sess.id) if sess else []
    except Exception as exc:
        return LogosResult.failure(action, f"Tradeoffs failed: {exc}")
    if not variants:
        msg = "No variants to compare. Generate rewrite variants first."
    else:
        lines = []
        for v in variants[:6]:
            try:
                s = json.loads(v.score_json or "{}")
            except Exception:
                s = {}
            lines.append(f"- {v.label}: {s.get('summary', 'no score')}")
        msg = "Variant tradeoffs:\n" + "\n".join(lines)
    return LogosResult(ok=True, action=action, title="Explain Rewrite Tradeoffs",
                       message=msg, suggestions=[], proposed_operations=[])


def _rw_score_variants(db, context: LogosContext) -> LogosResult:
    action = "rw_score_variants"
    try:
        from storyplanner.rewrite_sandbox.engine import score_rewrite_variant
        sess = db.get_latest_rewrite_session(context.project_id, status="open")
        variants = db.get_rewrite_variants(sess.id) if sess else []
        for v in variants:
            score_rewrite_variant(db, context.project_id, v.id)
    except Exception as exc:
        return LogosResult.failure(action, f"Scoring failed: {exc}")
    return LogosResult(ok=True, action=action, title="Score Rewrite Variants",
                       message=f"Re-scored {len(variants)} variant(s) "
                               "(deterministic).", suggestions=[],
                       proposed_operations=[])


def _rw_check_psyke_preservation(db, context: LogosContext) -> LogosResult:
    action = "rw_check_psyke_preservation"
    import json
    try:
        sess = db.get_latest_rewrite_session(context.project_id, status="open")
        variants = db.get_rewrite_variants(sess.id) if sess else []
    except Exception as exc:
        return LogosResult.failure(action, f"Check failed: {exc}")
    if not variants:
        msg = "No variants to check."
    else:
        lines = []
        for v in variants[:6]:
            try:
                s = json.loads(v.score_json or "{}")
            except Exception:
                s = {}
            lines.append(f"- {v.label}: preserved {s.get('psyke_terms_preserved', 0)}, "
                         f"removed {s.get('psyke_terms_removed', 0)}, "
                         f"added {s.get('psyke_terms_added', 0)}")
        msg = "PSYKE preservation per variant:\n" + "\n".join(lines)
    return LogosResult(ok=True, action=action, title="Check PSYKE Preservation",
                       message=msg, suggestions=[], proposed_operations=[])


register("rw_sandbox_status", _rw_status)
register("rw_explain_tradeoffs", _rw_explain_tradeoffs)
register("rw_score_variants", _rw_score_variants)
register("rw_check_psyke_preservation", _rw_check_psyke_preservation)


# -- Phase 10M — controlled apply (read-only status/conflict explainers) -------


def _ca_history(db, context: LogosContext) -> LogosResult:
    action = "ca_apply_history"
    try:
        from storyplanner.controlled_apply.service import get_apply_history
        ops = get_apply_history(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"History failed: {exc}")
    if not ops:
        msg = "No controlled-apply operations yet."
    else:
        lines = [f"- {o.source_type} → {o.target_type} ({o.status})"
                 for o in ops[-8:]]
        msg = "Recent apply operations:\n" + "\n".join(lines)
    return LogosResult(ok=True, action=action, title="Apply History",
                       message=msg, suggestions=[], proposed_operations=[])


def _ca_explain_conflicts(db, context: LogosContext) -> LogosResult:
    action = "ca_explain_conflicts"
    import json
    try:
        from storyplanner.controlled_apply.service import get_apply_history
        ops = [o for o in get_apply_history(db, context.project_id)
               if o.status in ("draft", "previewed")]
    except Exception as exc:
        return LogosResult.failure(action, f"Explain failed: {exc}")
    if not ops:
        msg = "No pending apply previews to explain."
    else:
        op = ops[-1]
        try:
            conflicts = json.loads(op.conflict_json or "[]")
        except Exception:
            conflicts = []
        if not conflicts:
            msg = f"Pending apply to {op.target_type}: no conflicts."
        else:
            lines = [f"- [{c['severity']}] {c['conflict_type']}: {c['message']}"
                     for c in conflicts]
            msg = (f"Pending apply to {op.target_type} — conflicts:\n"
                   + "\n".join(lines))
    return LogosResult(ok=True, action=action, title="Explain Apply Conflicts",
                       message=msg, suggestions=[], proposed_operations=[])


register("ca_apply_history", _ca_history)
register("ca_explain_conflicts", _ca_explain_conflicts)


# -- Phase 10N — project intelligence dashboard (read-only summaries) ----------


def _pi_dashboard_status(db, context: LogosContext) -> LogosResult:
    action = "pi_dashboard_status"
    try:
        from storyplanner.project_intelligence import build_project_intelligence_report
        rep = build_project_intelligence_report(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Dashboard failed: {exc}")
    ov, st, pk = rep.overview, rep.structure, rep.psyke
    lines = [rep.summary_line(),
             f"Words: {ov.get('total_words', 0)}; chapters: {ov.get('total_chapters', 0)}; "
             f"acts: {ov.get('total_acts', 0)}; notes: {ov.get('total_notes', 0)}",
             f"Scenes without summary: {st.get('scenes_without_summary', 0)}"]
    if pk.get("available"):
        lines.append(f"PSYKE: {pk.get('total', 0)} entries, "
                     f"{pk.get('empty_notes', 0)} with empty notes")
    if rep.health.get("available"):
        lines.append(f"Health: {rep.health.get('overall', 'unknown')}")
    return LogosResult(ok=True, action=action, title="Project Intelligence",
                       message="\n".join(lines), suggestions=[], proposed_operations=[])


def _pi_decision_radar(db, context: LogosContext) -> LogosResult:
    action = "pi_decision_radar"
    try:
        from storyplanner.project_intelligence import build_project_intelligence_report
        rep = build_project_intelligence_report(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Radar failed: {exc}")
    if not rep.radar:
        msg = "Decision Radar is clear — no flagged decisions."
    else:
        lines = [f"- [{c.severity}] {c.title}"
                 + (f" → {c.suggested_action}" if c.suggested_action else "")
                 for c in rep.radar[:10]]
        msg = "Decision Radar:\n" + "\n".join(lines)
    return LogosResult(ok=True, action=action, title="Decision Radar",
                       message=msg,
                       suggestions=[c.suggested_action for c in rep.top_cards(5)
                                    if c.suggested_action],
                       proposed_operations=[])


register("pi_dashboard_status", _pi_dashboard_status)
register("pi_decision_radar", _pi_decision_radar)


# -- Guided workflows (Phase 10O) -------------------------------------------

def _wf_active_workflows(db, context: LogosContext) -> LogosResult:
    action = "wf_active_workflows"
    try:
        from storyplanner.guided_workflows import get_active_workflows
        views = get_active_workflows(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Workflows failed: {exc}")
    if not views:
        return LogosResult(ok=True, action=action, title="Active Workflows",
                           message="No active guided workflows.",
                           suggestions=[], proposed_operations=[])
    lines: list[str] = []
    for v in views:
        lines.append(v.progress_line())
        cur = v.current_step
        if cur is not None:
            lines.append(f"  Current: {cur.title}"
                         + (f" (open {cur.section_name})" if cur.section_name else ""))
    return LogosResult(ok=True, action=action, title="Active Workflows",
                       message="\n".join(lines), suggestions=[],
                       proposed_operations=[])


def _wf_recommend_workflows(db, context: LogosContext) -> LogosResult:
    action = "wf_recommend_workflows"
    try:
        from storyplanner.guided_workflows import build_workflow_recommendations
        recs = build_workflow_recommendations(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Recommendations failed: {exc}")
    if not recs:
        return LogosResult(ok=True, action=action, title="Recommend Workflows",
                           message="No workflow recommendations right now.",
                           suggestions=[], proposed_operations=[])
    lines = [f"- {r.title}: {r.reason}" for r in recs]
    return LogosResult(ok=True, action=action, title="Recommend Workflows",
                       message="Suggested workflows:\n" + "\n".join(lines),
                       suggestions=[r.title for r in recs], proposed_operations=[])


register("wf_active_workflows", _wf_active_workflows)
register("wf_recommend_workflows", _wf_recommend_workflows)


# -- Narrative Knowledge Graph (Phase 10P) ----------------------------------

def _kg_build(db, context: LogosContext) -> LogosResult:
    action = "kg_build_graph"
    try:
        from storyplanner.knowledge_graph import build_knowledge_graph
        res = build_knowledge_graph(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Graph build failed: {exc}")
    lines = [res.summary_line()]
    if res.central:
        lines.append("Central: " + ", ".join(
            f"{n.label}({d})" for n, d in res.central[:5]))
    if res.graph.unavailable:
        lines.append("Deferred sources: " + ", ".join(sorted(set(res.graph.unavailable))))
    return LogosResult(ok=True, action=action, title="Knowledge Graph",
                       message="\n".join(lines), suggestions=[],
                       proposed_operations=[])


def _kg_refresh(db, context: LogosContext) -> LogosResult:
    action = "kg_refresh_graph"
    try:
        from storyplanner.knowledge_graph import build_knowledge_graph, persist_snapshot
        res = build_knowledge_graph(db, context.project_id)
        persist_snapshot(db, context.project_id, res)
    except Exception as exc:
        return LogosResult.failure(action, f"Graph refresh failed: {exc}")
    return LogosResult(ok=True, action=action, title="Knowledge Graph",
                       message="Refreshed. " + res.summary_line(),
                       suggestions=[], proposed_operations=[])


def _kg_scene_neighborhood(db, context: LogosContext) -> LogosResult:
    action = "kg_scene_neighborhood"
    if not context.current_scene_id:
        return LogosResult(ok=True, action=action, title="Scene Neighborhood",
                           message="Open a scene to see its neighborhood.",
                           suggestions=[], proposed_operations=[])
    try:
        from storyplanner.knowledge_graph import (
            build_knowledge_graph, get_scene_context_graph)
        from storyplanner.knowledge_graph.serializers import explain_node
        from storyplanner.knowledge_graph.models import node_key
        from storyplanner.knowledge_graph import provenance as P
        graph = build_knowledge_graph(db, context.project_id).graph
        key = node_key(P.NT_SCENE, "scene", context.current_scene_id)
        msg = explain_node(graph, key)
    except Exception as exc:
        return LogosResult.failure(action, f"Neighborhood failed: {exc}")
    return LogosResult(ok=True, action=action, title="Scene Neighborhood",
                       message=msg, suggestions=[], proposed_operations=[])


def _kg_psyke_neighborhood(db, context: LogosContext) -> LogosResult:
    action = "kg_psyke_neighborhood"
    eid = context.current_psyke_entry_id or context.selected_psyke_entry_id
    if not eid:
        return LogosResult(ok=True, action=action, title="PSYKE Neighborhood",
                           message="Select a PSYKE entry to see its neighborhood.",
                           suggestions=[], proposed_operations=[])
    try:
        from storyplanner.knowledge_graph import (
            build_knowledge_graph, get_psyke_entry_context_graph)
        graph = build_knowledge_graph(db, context.project_id).graph
        res = get_psyke_entry_context_graph(db, context.project_id, eid, graph=graph)
        lines = [res.explanation]
        for e in res.edges[:10]:
            lines.append(f"- {e.edge_type} [{e.confidence}] ({e.source_system})")
        msg = "\n".join(lines)
    except Exception as exc:
        return LogosResult.failure(action, f"Neighborhood failed: {exc}")
    return LogosResult(ok=True, action=action, title="PSYKE Neighborhood",
                       message=msg, suggestions=[], proposed_operations=[])


def _kg_find_orphans(db, context: LogosContext) -> LogosResult:
    action = "kg_find_orphans"
    try:
        from storyplanner.knowledge_graph import get_orphan_nodes
        orphans = get_orphan_nodes(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Orphan scan failed: {exc}")
    if not orphans:
        msg = "No orphan nodes — every story element is connected."
    else:
        msg = "Orphan nodes:\n" + "\n".join(
            f"- {n.node_type}: {n.label}" for n in orphans[:15])
    return LogosResult(ok=True, action=action, title="Orphan Nodes",
                       message=msg, suggestions=[], proposed_operations=[])


def _kg_find_weak_links(db, context: LogosContext) -> LogosResult:
    action = "kg_find_weak_links"
    try:
        from storyplanner.knowledge_graph import build_knowledge_graph, get_weak_links
        from storyplanner.knowledge_graph.serializers import _label
        graph = build_knowledge_graph(db, context.project_id).graph
        weak = get_weak_links(db, context.project_id, graph=graph)
    except Exception as exc:
        return LogosResult.failure(action, f"Weak-link scan failed: {exc}")
    if not weak:
        msg = "No inferred edges needing review."
    else:
        msg = "Inferred edges (review/confirm):\n" + "\n".join(
            f"- {_label(graph, e.source)} {e.edge_type} {_label(graph, e.target)} "
            f"[{e.confidence}]" for e in weak[:15])
    return LogosResult(ok=True, action=action, title="Weak Links",
                       message=msg, suggestions=[], proposed_operations=[])


def _kg_find_undefined_terms(db, context: LogosContext) -> LogosResult:
    action = "kg_find_undefined_terms"
    try:
        from storyplanner.knowledge_graph import build_knowledge_graph
        res = build_knowledge_graph(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Term scan failed: {exc}")
    if not res.undefined_terms:
        msg = "No undefined note terms detected."
    else:
        msg = ("Note terms not defined in PSYKE (review before creating):\n"
               + "\n".join(f"- {t}" for t in res.undefined_terms[:20]))
    return LogosResult(ok=True, action=action, title="Undefined Terms",
                       message=msg,
                       suggestions=res.undefined_terms[:5], proposed_operations=[])


def _kg_decision_cards(db, context: LogosContext) -> LogosResult:
    action = "kg_decision_cards"
    try:
        from storyplanner.knowledge_graph import build_graph_decision_cards
        cards = build_graph_decision_cards(db, context.project_id)
    except Exception as exc:
        return LogosResult.failure(action, f"Card generation failed: {exc}")
    if not cards:
        msg = "No graph-derived decisions right now."
    else:
        msg = "Graph decisions:\n" + "\n".join(
            f"- [{c.severity}] {c.title}" for c in cards)
    return LogosResult(ok=True, action=action, title="Graph Decision Cards",
                       message=msg,
                       suggestions=[c.suggested_action for c in cards
                                    if c.suggested_action], proposed_operations=[])


register("kg_build_graph", _kg_build)
register("kg_refresh_graph", _kg_refresh)
register("kg_scene_neighborhood", _kg_scene_neighborhood)
register("kg_psyke_neighborhood", _kg_psyke_neighborhood)
register("kg_find_orphans", _kg_find_orphans)
register("kg_find_weak_links", _kg_find_weak_links)
register("kg_find_undefined_terms", _kg_find_undefined_terms)
register("kg_decision_cards", _kg_decision_cards)
