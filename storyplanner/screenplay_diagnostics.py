"""Deterministic screenplay diagnostics + scene economy (Phase 10C).

Evaluates a screenplay scene *as a screenplay scene* — using the Phase 10B block
parser — with conservative, rule-based heuristics. No LLM, no DB writes, no Qt.

Everything here is evidence-based and confidence-aware: where semantics can't be
known without an LLM (scene turn, subtext) the report says so ("unclear") rather
than inventing precision. Thresholds are module constants and documented.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from storyplanner import screenplay_blocks as sb

# -- Severity (issue-local scale) --------------------------------------------
SEV_INFO = "info"
SEV_WATCH = "watch"
SEV_WEAK = "weak"
SEV_CRITICAL = "critical"
_SEV_RANK = {SEV_INFO: 0, SEV_WATCH: 1, SEV_WEAK: 2, SEV_CRITICAL: 3}

# -- Documented thresholds ---------------------------------------------------
ACTION_BLOCK_LONG_WORDS = 60        # an action paragraph this long may be overwritten
LONG_DIALOGUE_WORDS = 50            # a single dialogue block this long ~ monologue
PARENTHETICAL_RATIO_HIGH = 0.4      # parentheticals / dialogue blocks
DIALOGUE_ACTION_RATIO_HIGH = 4.0    # dialogue-heavy if dlg/action exceeds this
ACTION_DIALOGUE_RATIO_HIGH = 6.0    # action-heavy if action blocks dominate
TRANSITION_OVERUSE = 2              # more than this many transitions in one scene
SHOT_OVERUSE = 3                    # more than this many explicit shots
INTERNAL_WORDS_PER_BLOCK = 2        # internal-state words in one action block
LINES_PER_PAGE = 55                 # rough screenplay page (1 page ~ 1 minute)

# Internal-state vocabulary — action should show, not narrate interiority.
INTERNAL_STATE_WORDS = (
    "thinks", "think", "thought", "remembers", "remember", "remembered",
    "feels", "feel", "felt", "realizes", "realises", "realized", "realised",
    "understands", "understood", "wonders", "wondered", "knows", "knew",
    "believes", "believed", "decides", "decided", "considers", "imagines",
    "recalls", "wishes", "hopes",
)
# Turn / contrast markers — weak signals that a scene shifts value.
TURN_MARKERS = (
    "but", "however", "instead", "suddenly", "then", "finally", "until",
    "despite", "yet", "no longer", "everything changes",
)
# Objective markers — a character appears to want something.
OBJECTIVE_MARKERS = (
    "want", "wants", "wanted", "need", "needs", "needed", "has to", "have to",
    "must", "trying to", "going to", "i'll", "we have to", "let's",
)
# Setup/payoff candidate markers (hooks for the Phase 10D setup/payoff engine).
SETUP_MARKERS = (
    "remember", "promise", "swear", "don't forget", "one day", "someday",
    "i'll be back", "keep this", "never forget", "if anything happens",
)


def _words(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


@dataclass
class ScreenplayDiagnosticIssue:
    id: str
    label: str
    severity: str = SEV_INFO
    confidence: float = 0.0
    evidence: str = ""
    target_block_index: int | None = None
    suggested_action: str = ""
    logos_action_id: str | None = None

    @property
    def severity_rank(self) -> int:
        return _SEV_RANK.get(self.severity, 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "severity": self.severity,
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
            "target_block_index": self.target_block_index,
            "suggested_action": self.suggested_action,
            "logos_action_id": self.logos_action_id,
        }


@dataclass
class ScreenplaySceneReport:
    scene_id: int | None = None
    scene_heading: str = ""
    block_count: int = 0
    action_block_count: int = 0
    dialogue_block_count: int = 0
    character_cue_count: int = 0
    unique_characters: list[str] = field(default_factory=list)
    estimated_page_fraction: float = 0.0
    estimated_minutes: float = 0.0
    dominant_block_type: str = ""
    economy_label: str = ""           # dialogue-heavy | action-heavy | balanced | sparse
    issues: list[ScreenplayDiagnosticIssue] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    confidence: float = 0.0
    summary: str = ""

    def top_issues(self, n: int = 3) -> list[ScreenplayDiagnosticIssue]:
        return sorted(
            self.issues, key=lambda i: (i.severity_rank, i.confidence), reverse=True,
        )[:n]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "scene_heading": self.scene_heading,
            "block_count": self.block_count,
            "action_block_count": self.action_block_count,
            "dialogue_block_count": self.dialogue_block_count,
            "character_cue_count": self.character_cue_count,
            "unique_characters": list(self.unique_characters),
            "estimated_page_fraction": self.estimated_page_fraction,
            "estimated_minutes": self.estimated_minutes,
            "dominant_block_type": self.dominant_block_type,
            "economy_label": self.economy_label,
            "issues": [i.to_dict() for i in self.issues],
            "strengths": list(self.strengths),
            "warnings": list(self.warnings),
            "confidence": round(self.confidence, 2),
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Core analysis (pure: operates on parsed blocks)
# ---------------------------------------------------------------------------


def analyze_scene(
    blocks: list[sb.ScreenplayBlock],
    *,
    scene_id: int | None = None,
    scene_heading: str = "",
    psyke_characters: dict[str, bool] | None = None,
) -> ScreenplaySceneReport:
    """Deterministically analyze one scene's blocks.

    *psyke_characters* maps uppercased character name -> has-objective-data, used
    only to raise/lower the character-objective confidence. Absent data lowers
    confidence; it never hard-fails.
    """
    report = ScreenplaySceneReport(scene_id=scene_id, scene_heading=scene_heading)
    psyke_characters = psyke_characters or {}

    counts: dict[str, int] = {}
    for b in blocks:
        counts[b.element_type] = counts.get(b.element_type, 0) + 1

    report.block_count = len(blocks)
    report.action_block_count = counts.get("action", 0)
    report.dialogue_block_count = counts.get("dialogue", 0)
    report.character_cue_count = counts.get("character", 0)
    report.unique_characters = sb.character_cues(blocks)

    # Rough runtime estimate (clearly approximate: ~1 screenplay page/minute).
    line_count = sum(max(1, b.text.count("\n") + 1) for b in blocks)
    report.estimated_page_fraction = round(line_count / LINES_PER_PAGE, 2)
    report.estimated_minutes = report.estimated_page_fraction  # 1 page ≈ 1 min

    if counts:
        report.dominant_block_type = max(counts, key=lambda k: counts[k])

    issues: list[ScreenplayDiagnosticIssue] = []

    # --- Empty / notes-only / no-heading ---
    if not blocks:
        report.economy_label = "sparse"
        report.summary = "Empty scene — no screenplay content to analyze."
        report.confidence = 1.0
        return report

    if counts.get("note", 0) == len(blocks):
        issues.append(ScreenplayDiagnosticIssue(
            id="only_notes", label="Scene contains only notes", severity=SEV_WEAK,
            confidence=0.9, evidence="Every block is a note; no action or dialogue.",
            suggested_action="Add scene action and/or dialogue.",
        ))

    has_heading = bool(scene_heading.strip()) or counts.get("scene_heading", 0) > 0
    if not has_heading:
        issues.append(ScreenplayDiagnosticIssue(
            id="missing_scene_heading", label="Scene heading missing", severity=SEV_WATCH,
            confidence=0.8,
            evidence="No INT./EXT. scene heading was found for this scene.",
            suggested_action="Add a scene heading (INT./EXT. LOCATION - TIME).",
        ))

    # --- Scene economy (ratios) ---
    a = report.action_block_count
    d = report.dialogue_block_count
    if a == 0 and d == 0:
        report.economy_label = "sparse"
    elif d >= 1 and (a == 0 or d / max(a, 1) >= DIALOGUE_ACTION_RATIO_HIGH):
        report.economy_label = "dialogue-heavy"
        issues.append(ScreenplayDiagnosticIssue(
            id="dialogue_heavy", label="Scene is dialogue-heavy", severity=SEV_WATCH,
            confidence=0.6,
            evidence=f"{d} dialogue block(s) vs {a} action block(s).",
            suggested_action="Add visual action beats between dialogue.",
            logos_action_id="sp_suggest_action_interruption",
        ))
    elif a >= 1 and (d == 0 or a / max(d, 1) >= ACTION_DIALOGUE_RATIO_HIGH):
        report.economy_label = "action-heavy"
        if d == 0:
            issues.append(ScreenplayDiagnosticIssue(
                id="no_dialogue", label="Scene has no dialogue", severity=SEV_INFO,
                confidence=0.5,
                evidence=f"{a} action block(s), no dialogue.",
                suggested_action="Confirm a silent/visual scene is intended.",
            ))
    else:
        report.economy_label = "balanced"

    # --- Visual action: internal-state language ---
    for idx, b in enumerate(blocks):
        if b.element_type != "action":
            continue
        low = b.text.lower()
        hits = sum(1 for w in INTERNAL_STATE_WORDS if re.search(rf"\b{re.escape(w)}\b", low))
        if hits >= INTERNAL_WORDS_PER_BLOCK:
            issues.append(ScreenplayDiagnosticIssue(
                id=f"internal_action_{idx}", label="Action may read as internal prose",
                severity=SEV_WATCH, confidence=0.55, target_block_index=idx,
                evidence=(f"Action block uses {hits} internal-state words "
                          "(thinks/feels/realizes…)."),
                suggested_action="This may read as internal prose rather than "
                                 "visible action; externalize it.",
                logos_action_id="sp_visual_action",
            ))
        if _words(b.text) >= ACTION_BLOCK_LONG_WORDS:
            issues.append(ScreenplayDiagnosticIssue(
                id=f"overwritten_action_{idx}", label="Action block may be overwritten",
                severity=SEV_WATCH, confidence=0.5, target_block_index=idx,
                evidence=f"Action block is {_words(b.text)} words.",
                suggested_action="Consider tightening to essential visible beats.",
                logos_action_id="sp_overwritten_action",
            ))

    # --- Dialogue economy ---
    for idx, b in enumerate(blocks):
        if b.element_type == "dialogue" and _words(b.text) >= LONG_DIALOGUE_WORDS:
            issues.append(ScreenplayDiagnosticIssue(
                id=f"long_dialogue_{idx}", label="Long dialogue block", severity=SEV_WATCH,
                confidence=0.5, target_block_index=idx,
                evidence=f"Dialogue block is {_words(b.text)} words (monologue-like).",
                suggested_action="Consider breaking up or interrupting with action.",
                logos_action_id="sp_tighten_dialogue",
            ))
    # Parenthetical overuse.
    paren = counts.get("parenthetical", 0)
    if d > 0 and paren / d >= PARENTHETICAL_RATIO_HIGH:
        issues.append(ScreenplayDiagnosticIssue(
            id="parenthetical_overuse", label="Parentheticals may be overused",
            severity=SEV_WATCH, confidence=0.6,
            evidence=f"{paren} parenthetical(s) across {d} dialogue block(s).",
            suggested_action="Trust the dialogue; cut redundant parentheticals.",
        ))
    # Single-voice scene.
    if d >= 3 and len(report.unique_characters) <= 1:
        issues.append(ScreenplayDiagnosticIssue(
            id="single_voice", label="Scene dominated by one voice", severity=SEV_WATCH,
            confidence=0.55,
            evidence="Multiple dialogue blocks but only one speaking character.",
            suggested_action="Consider another voice or visual response.",
        ))

    # --- Transition / shot overuse ---
    if counts.get("transition", 0) > TRANSITION_OVERUSE:
        issues.append(ScreenplayDiagnosticIssue(
            id="transition_overuse", label="Transitions may be overused", severity=SEV_INFO,
            confidence=0.6,
            evidence=f"{counts['transition']} transitions in one scene.",
            suggested_action="Most scenes need at most one transition out.",
        ))
    if counts.get("shot", 0) > SHOT_OVERUSE:
        issues.append(ScreenplayDiagnosticIssue(
            id="shot_overuse", label="Explicit shots may be overused", severity=SEV_INFO,
            confidence=0.6,
            evidence=f"{counts['shot']} explicit shot directions.",
            suggested_action="Let action imply coverage; reserve shots for emphasis.",
        ))

    # --- Scene turn heuristic (confidence-aware, never asserts absence) ---
    body = " ".join(b.text.lower() for b in blocks
                    if b.element_type in ("action", "dialogue"))
    has_turn_marker = any(re.search(rf"\b{re.escape(m)}\b", body) for m in TURN_MARKERS)
    if report.block_count >= 2 and not has_turn_marker:
        issues.append(ScreenplayDiagnosticIssue(
            id="scene_turn_unclear", label="Scene turn unclear", severity=SEV_WATCH,
            confidence=0.4,
            evidence="No contrast/turn markers detected (deterministic check only).",
            suggested_action="Check that the scene's value changes start-to-end.",
            logos_action_id="sp_check_scene_turn",
        ))

    # --- Character objective (PSYKE-aware, confidence scaled) ---
    if report.character_cue_count == 0 and a > 0:
        issues.append(ScreenplayDiagnosticIssue(
            id="no_active_character", label="No active speaking character", severity=SEV_INFO,
            confidence=0.4, evidence="Action present but no character cues.",
            suggested_action="Confirm a character drives the scene.",
        ))
    else:
        has_objective_lang = any(
            re.search(rf"\b{re.escape(m)}\b", body) for m in OBJECTIVE_MARKERS
        )
        known = [c for c in report.unique_characters if c in psyke_characters]
        has_psyke_goal = any(psyke_characters.get(c) for c in known)
        if not has_objective_lang and not has_psyke_goal:
            conf = 0.3 if not psyke_characters else 0.45
            issues.append(ScreenplayDiagnosticIssue(
                id="objective_unclear", label="Character objective unclear",
                severity=SEV_WATCH, confidence=conf,
                evidence=("No want/need language and no PSYKE objective for the "
                          "scene's characters."),
                suggested_action=("Clarify what the character wants here"
                                  + ("" if psyke_characters else
                                     "; consider adding an objective in PSYKE.")),
                logos_action_id="sp_clarify_objective",
            ))

    # --- Setup/payoff candidates (hooks only — cautious) ---
    for idx, b in enumerate(blocks):
        low = b.text.lower()
        if any(re.search(rf"\b{re.escape(m)}\b", low) for m in SETUP_MARKERS):
            issues.append(ScreenplayDiagnosticIssue(
                id=f"setup_candidate_{idx}", label="Possible setup", severity=SEV_INFO,
                confidence=0.35, target_block_index=idx,
                evidence="Promise/recall language — untracked setup candidate.",
                suggested_action="Track this setup's payoff (Phase 10D).",
                logos_action_id="sp_track_setup_payoff",
            ))

    # --- Strengths ---
    if report.economy_label == "balanced":
        report.strengths.append("Action/dialogue balance looks healthy.")
    if has_turn_marker:
        report.strengths.append("Contains a possible value turn.")
    if has_heading:
        report.strengths.append("Scene heading present.")

    report.issues = issues
    report.warnings = [i.evidence for i in issues if i.severity == SEV_WATCH]
    # Overall confidence: deterministic structure is reliable; semantic checks
    # are not — report a moderate, honest confidence.
    report.confidence = 0.7 if blocks else 1.0
    report.summary = _summary(report)
    return report


def _summary(report: ScreenplaySceneReport) -> str:
    top = report.top_issues(3)
    head = f"Scene economy: {report.economy_label or 'unknown'}."
    if not top:
        return head + " No notable screenplay issues detected."
    bullets = "; ".join(f"{i.label}" for i in top)
    return f"{head} Top issues: {bullets}."


# ---------------------------------------------------------------------------
# DB adapter (read-only): analyze a project's scenes
# ---------------------------------------------------------------------------

_OBJECTIVE_KEYS = (
    "goal", "objective", "want", "visual_objective", "scene_objective",
    "stage_objective", "motivation",
)


def _psyke_character_map(db, project_id: int) -> dict[str, bool]:
    """Uppercased PSYKE character name -> whether it has objective-ish data."""
    out: dict[str, bool] = {}
    try:
        entries = db.get_all_psyke_entries(project_id)
    except Exception:
        return out
    for e in entries:
        if (getattr(e, "entry_type", "") or "").lower() != "character":
            continue
        name = (getattr(e, "name", "") or "").strip().upper()
        if not name:
            continue
        has_goal = False
        try:
            details = db.get_psyke_entry_details(e.id) or {}
            has_goal = any(str(details.get(k, "")).strip() for k in _OBJECTIVE_KEYS)
        except Exception:
            has_goal = False
        out[name] = has_goal
    return out


def _scene_heading(scene) -> str:
    return (getattr(scene, "slugline", "") or getattr(scene, "title", "") or "").strip()


def analyze_project(db, project_id: int) -> list[ScreenplaySceneReport]:
    """Analyze every scene of a project (read-only). Tolerant of failures."""
    reports: list[ScreenplaySceneReport] = []
    try:
        scenes = db.get_all_scenes(project_id)
    except Exception:
        return reports
    psyke = _psyke_character_map(db, project_id)
    for scene in scenes:
        content = getattr(scene, "content", "") or ""
        blocks = sb.parse_screenplay_text(content, scene_id=scene.id)
        reports.append(analyze_scene(
            blocks, scene_id=scene.id, scene_heading=_scene_heading(scene),
            psyke_characters=psyke,
        ))
    return reports


def _status_for_fraction(frac: float):
    """Conservative status from the fraction of scenes flagged (never critical)."""
    from storyplanner.logos.health import metric as M
    if frac <= 0.0:
        return M.STATUS_STABLE
    if frac <= 0.34:
        return M.STATUS_WATCH
    return M.STATUS_WEAK


def screenplay_health_metrics(db, project_id: int) -> list:
    """Build screenplay-mode :class:`NarrativeHealthMetric`s from deterministic
    diagnostics. Subtext / Cinematic Continuity are deferred (always *unknown*);
    no fake precision — categories with no analyzable data return *unknown*.
    """
    from storyplanner.logos.health import metric as M

    reports = [r for r in analyze_project(db, project_id) if r.block_count > 0]
    n = len(reports)

    def metric(cat: str, ids: tuple[str, ...], note: str, confidence: float):
        if n == 0:
            return M.NarrativeHealthMetric(category=cat, status=M.STATUS_UNKNOWN,
                                           evidence="No screenplay scenes to analyze.")
        flagged = sum(
            1 for r in reports if any(
                any(i.id.startswith(p) for p in ids) for i in r.issues
            )
        )
        status = _status_for_fraction(flagged / n)
        if status == M.STATUS_STABLE:
            evidence = f"No {note} issues across {n} scene(s)."
        else:
            evidence = f"{flagged} of {n} scene(s) flagged for {note}."
        return M.NarrativeHealthMetric(category=cat, status=status,
                                       confidence=confidence, evidence=evidence)

    metrics = [
        metric(M.CAT_SCENE_ECONOMY,
               ("dialogue_heavy", "action_heavy", "no_dialogue", "only_notes"),
               "scene economy", 0.6),
        metric(M.CAT_VISUAL_ACTION, ("internal_action", "overwritten_action"),
               "visual action", 0.55),
        metric(M.CAT_DIALOGUE_ECONOMY,
               ("long_dialogue", "parenthetical_overuse", "single_voice"),
               "dialogue economy", 0.55),
        metric(M.CAT_SCENE_TURN, ("scene_turn_unclear",), "unclear scene turn", 0.4),
        metric(M.CAT_CHARACTER_OBJECTIVE,
               ("objective_unclear", "no_active_character"),
               "unclear character objective", 0.45),
    ]
    # -- Setup/Payoff + Motif (Phase 10D — deterministic tracker) --
    try:
        from storyplanner.screenplay_setup_payoff import analyze_setup_payoff
        sp = analyze_setup_payoff(db, project_id)
    except Exception:
        sp = None
    if n == 0 or sp is None:
        metrics.append(M.NarrativeHealthMetric(
            category=M.CAT_SP_SETUP_PAYOFF, status=M.STATUS_UNKNOWN,
            evidence="No screenplay scenes to analyze."))
        metrics.append(M.NarrativeHealthMetric(
            category=M.CAT_MOTIF_RECURRENCE, status=M.STATUS_UNKNOWN,
            evidence="No screenplay scenes to analyze."))
    else:
        un = len(sp.unresolved_setups)
        sp_status = M.STATUS_WATCH if un else M.STATUS_STABLE
        metrics.append(M.NarrativeHealthMetric(
            category=M.CAT_SP_SETUP_PAYOFF, status=sp_status, confidence=0.45,
            evidence=(f"{un} unresolved setup candidate(s); "
                      f"{len(sp.possible_payoffs)} possible payoff(s).")))
        motif_status = M.STATUS_STABLE if sp.recurring_motifs else M.STATUS_UNKNOWN
        metrics.append(M.NarrativeHealthMetric(
            category=M.CAT_MOTIF_RECURRENCE, status=motif_status, confidence=0.4,
            evidence=(f"{len(sp.recurring_motifs)} recurring motif candidate(s)."
                      if sp.recurring_motifs else "No recurring motifs detected.")))

    # -- Subtext + On-the-Nose (Phase 10D — deterministic subtext) --
    try:
        from storyplanner.screenplay_subtext import (
            analyze_subtext_project, S_ON_THE_NOSE_RISK,
        )
        sub_reports = analyze_subtext_project(db, project_id)
        sub_reports = [r for r in sub_reports if r.signals or True]
    except Exception:
        sub_reports = []
    sub_scenes = [r for r in (sub_reports or []) if r.scene_id is not None]
    if not sub_scenes or n == 0:
        for cat in (M.CAT_SUBTEXT, M.CAT_ON_THE_NOSE):
            metrics.append(M.NarrativeHealthMetric(
                category=cat, status=M.STATUS_UNKNOWN,
                evidence="No screenplay dialogue to analyze."))
    else:
        flagged_sub = sum(1 for r in sub_scenes if r.signals)
        metrics.append(M.NarrativeHealthMetric(
            category=M.CAT_SUBTEXT, status=_status_for_fraction(flagged_sub / len(sub_scenes)),
            confidence=0.45,
            evidence=f"{flagged_sub} of {len(sub_scenes)} scene(s) have subtext signals."))
        otn = sum(1 for r in sub_scenes
                  if any(s.signal_type == S_ON_THE_NOSE_RISK for s in r.signals))
        metrics.append(M.NarrativeHealthMetric(
            category=M.CAT_ON_THE_NOSE, status=_status_for_fraction(otn / len(sub_scenes)),
            confidence=0.45,
            evidence=f"{otn} of {len(sub_scenes)} scene(s) flagged on-the-nose."))

    # -- Confirmed-link coverage + candidate density (Phase 10E) --
    try:
        confirmed = db.get_story_links(project_id, status="confirmed")
        resolved = db.get_story_links(project_id, status="resolved")
    except Exception:
        confirmed, resolved = [], []
    n_confirmed = len(confirmed) + len(resolved)
    unresolved_cands = len(sp.unresolved_setups) if sp else 0
    # Confirmed links carry more weight: coverage is stable once any setup/payoff
    # is confirmed; unknown when there's nothing tracked yet.
    if n_confirmed > 0:
        cov_status, cov_ev = M.STATUS_STABLE, f"{n_confirmed} confirmed story link(s)."
    elif unresolved_cands > 0:
        cov_status = M.STATUS_WATCH
        cov_ev = f"{unresolved_cands} candidate(s) but none confirmed yet."
    else:
        cov_status, cov_ev = M.STATUS_UNKNOWN, "No story links tracked."
    metrics.append(M.NarrativeHealthMetric(
        category=M.CAT_LINK_COVERAGE, status=cov_status, confidence=0.45,
        evidence=cov_ev))
    # Candidate density: many unresolved candidates -> watch (a warning, not fail).
    dens_status = M.STATUS_WATCH if unresolved_cands >= 3 else (
        M.STATUS_STABLE if (sp and (sp.candidates or n_confirmed)) else M.STATUS_UNKNOWN)
    metrics.append(M.NarrativeHealthMetric(
        category=M.CAT_CANDIDATE_DENSITY, status=dens_status, confidence=0.4,
        evidence=f"{unresolved_cands} unresolved candidate(s)."))

    # -- Export / format readiness (Phase 10F — format health, NOT narrative) --
    # Capped at WATCH so a formatting issue never flips the narrative overall to
    # weak/critical: format problems are distinct from craft problems.
    try:
        from storyplanner.screenplay_export_validation import (
            validate_screenplay_export,
        )
        from storyplanner.screenplay_render import get_export_prefs, get_title_page
        prefs = get_export_prefs(db, project_id)
        val = validate_screenplay_export(
            db, project_id, target_format=prefs.get("export_target", "fountain"),
            prefs=prefs)
        title = (get_title_page(db, project_id).get("title") or "").strip()
    except Exception:
        val, title = None, ""

    if n == 0 or val is None:
        for cat in (M.CAT_EXPORT_READINESS, M.CAT_TITLE_PAGE,
                    M.CAT_SCENE_HEADING_INTEGRITY, M.CAT_DIALOGUE_FORMAT):
            metrics.append(M.NarrativeHealthMetric(
                category=cat, status=M.STATUS_UNKNOWN,
                evidence="No screenplay scenes to assess."))
    else:
        readiness = M.STATUS_STABLE if (val.is_export_safe and not val.warnings) else M.STATUS_WATCH
        metrics.append(M.NarrativeHealthMetric(
            category=M.CAT_EXPORT_READINESS, status=readiness, confidence=0.5,
            evidence=val.summary))
        metrics.append(M.NarrativeHealthMetric(
            category=M.CAT_TITLE_PAGE,
            status=M.STATUS_STABLE if title else M.STATUS_WATCH, confidence=0.5,
            evidence=("Title page set." if title else "No title page set.")))
        heading_warn = any("scene heading" in w for w in val.warnings)
        metrics.append(M.NarrativeHealthMetric(
            category=M.CAT_SCENE_HEADING_INTEGRITY,
            status=M.STATUS_WATCH if heading_warn else M.STATUS_STABLE, confidence=0.5,
            evidence=next((w for w in val.warnings if "scene heading" in w),
                         "Scene headings present.")))
        dlg_warn = any(("dialogue block" in w or "parenthetical" in w)
                       for w in val.warnings)
        metrics.append(M.NarrativeHealthMetric(
            category=M.CAT_DIALOGUE_FORMAT,
            status=M.STATUS_WATCH if dlg_warn else M.STATUS_STABLE, confidence=0.5,
            evidence=next((w for w in val.warnings
                           if "dialogue block" in w or "parenthetical" in w),
                          "Dialogue formatting looks consistent.")))

    # -- Fountain readiness (Phase 10G — format health, capped at WATCH) --
    try:
        from storyplanner.export import export_screenplay_fountain_result
        from storyplanner.screenplay_fountain import validate_fountain_export
        res = export_screenplay_fountain_result(db, project_id)
        fval = validate_fountain_export(res.text)
    except Exception:
        res, fval = None, None
    if n == 0 or fval is None:
        for cat in (M.CAT_FOUNTAIN_READINESS, M.CAT_UNSUPPORTED_ELEMENTS):
            metrics.append(M.NarrativeHealthMetric(
                category=cat, status=M.STATUS_UNKNOWN,
                evidence="No screenplay scenes to assess."))
    else:
        f_status = M.STATUS_STABLE if (fval.is_valid and not fval.warnings) else M.STATUS_WATCH
        metrics.append(M.NarrativeHealthMetric(
            category=M.CAT_FOUNTAIN_READINESS, status=f_status, confidence=0.5,
            evidence=fval.summary))
        # Forcing syntax indicates an element that didn't map cleanly; omitted
        # notes are an intentional pref, not an unsupported element.
        unsupported = [w for w in (res.warnings if res else [])
                       if "forced" in w.lower()]
        metrics.append(M.NarrativeHealthMetric(
            category=M.CAT_UNSUPPORTED_ELEMENTS,
            status=M.STATUS_WATCH if unsupported else M.STATUS_STABLE, confidence=0.45,
            evidence=(unsupported[0] if unsupported
                      else "All elements map cleanly to Fountain.")))

    # -- Professional output readiness (Phase 10H — format health, capped WATCH) --
    try:
        from storyplanner.screenplay_output_validation import (
            validate_professional_output,
        )
        oval = validate_professional_output(db, project_id, target_format="docx")
    except Exception:
        oval = None
    if n == 0 or oval is None:
        metrics.append(M.NarrativeHealthMetric(
            category=M.CAT_PRO_OUTPUT_READINESS, status=M.STATUS_UNKNOWN,
            evidence="No screenplay scenes to assess."))
    else:
        o_status = (M.STATUS_STABLE if (oval.is_export_safe and not oval.warnings)
                    else M.STATUS_WATCH)
        metrics.append(M.NarrativeHealthMetric(
            category=M.CAT_PRO_OUTPUT_READINESS, status=o_status, confidence=0.5,
            evidence=(f"Formats: {', '.join(oval.available_formats)}. "
                      + (oval.warnings[0] if oval.warnings else "DOCX export ready."))))
    # FDX is always experimental/unverified -> a standing watch (never critical).
    metrics.append(M.NarrativeHealthMetric(
        category=M.CAT_FDX_COMPAT_RISK,
        status=(M.STATUS_WATCH if n else M.STATUS_UNKNOWN), confidence=0.4,
        evidence="FDX export is experimental and unverified — prefer .fountain."))

    # Cinematic Continuity stays deferred (needs semantics / Phase 10I).
    metrics.append(M.NarrativeHealthMetric(
        category=M.CAT_CINEMATIC_CONTINUITY, status=M.STATUS_UNKNOWN,
        evidence="Deferred — not deterministically assessable yet (Phase 10I)."))
    return metrics


def analyze_scene_by_id(db, project_id: int, scene_id: int) -> ScreenplaySceneReport:
    """Analyze a single scene by id (read-only)."""
    scene = None
    try:
        scene = db.get_scene_by_id(scene_id)
    except Exception:
        scene = None
    if scene is None:
        return ScreenplaySceneReport(scene_id=scene_id, summary="Scene not found.")
    blocks = sb.parse_screenplay_text(getattr(scene, "content", "") or "", scene_id=scene_id)
    return analyze_scene(
        blocks, scene_id=scene_id, scene_heading=_scene_heading(scene),
        psyke_characters=_psyke_character_map(db, project_id),
    )
