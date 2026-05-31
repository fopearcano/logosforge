"""DiagnosticsEngine — runs PSYKE-aware rule detectors over a project snapshot.

Phase 5 is rule-based and fast: a scan builds a read-only ``ProjectFacts``
snapshot once, runs the detectors, then filters by confidence and suppression
and dedupes by stable id. It never calls an LLM, never mutates the DB, and never
blocks on the network. High-severity diagnostics convert to Phase-4
``LogosSuggestion`` objects via :meth:`to_suggestions`.
"""

from __future__ import annotations

from storyplanner.logos.diagnostics.character_diagnostics import detect_characters
from storyplanner.logos.diagnostics.continuity_diagnostics import detect_continuity
from storyplanner.logos.diagnostics.diagnostic import (
    SEVERITY_IMPORTANT,
    NarrativeDiagnostic,
)
from storyplanner.logos.diagnostics.model import build_facts
from storyplanner.logos.diagnostics.relation_diagnostics import detect_relations
from storyplanner.logos.diagnostics.setup_payoff_diagnostics import detect_setup_payoff
from storyplanner.logos.diagnostics.structure_diagnostics import detect_structure
from storyplanner.logos.diagnostics.theme_diagnostics import detect_themes

# Default confidence below which diagnostics stay report-only (not surfaced
# as proactive suggestions). Matches the proactive engine's default.
DEFAULT_THRESHOLD = 0.65

_ALL_DETECTORS = [
    detect_characters,
    detect_themes,
    detect_relations,
    detect_continuity,
    detect_setup_payoff,
    detect_structure,
]

# Section name -> which detector outputs are relevant to that section view.
_SECTION_SECTIONS = {
    "PSYKE": {"PSYKE"},
    "Graph": {"Graph", "PSYKE"},
    "Outline": {"Outline"},
    "Plot": {"Plot", "Outline"},
    "Timeline": {"Timeline", "Outline"},
    "Manuscript": {"PSYKE", "Outline"},
}


class DiagnosticsEngine:
    def __init__(self, db, project_id: int, *, suppression=None) -> None:
        self._db = db
        self._project_id = project_id
        self._suppression = suppression

    # -- Scans ---------------------------------------------------------------

    def scan_project(self) -> list[NarrativeDiagnostic]:
        """Project-wide scan (manual). Lightweight, rule-based, no LLM."""
        facts = build_facts(self._db, self._project_id)
        raw: list[NarrativeDiagnostic] = []
        for detect in _ALL_DETECTORS:
            try:
                raw.extend(detect(facts))
            except Exception:
                continue  # a flaky detector never breaks the whole scan
        return self._dedup_sort(raw)

    def scan_section(self, section_name: str) -> list[NarrativeDiagnostic]:
        """Current-section scan — filters the project diagnostics to the
        section's relevant origins. (Detectors are cheap, so we reuse the full
        scan and slice, keeping behaviour identical to the project view.)"""
        wanted = _SECTION_SECTIONS.get(section_name)
        diags = self.scan_project()
        if not wanted:
            return diags
        return [d for d in diags if d.section_name in wanted]

    # -- Conversion to proactive suggestions ---------------------------------

    def to_suggestions(self, diagnostics, *, threshold: float = DEFAULT_THRESHOLD):
        """Convert important/critical diagnostics into LogosSuggestions.

        Only high-severity, above-threshold, non-suppressed diagnostics surface
        as proactive pills; the rest remain in the diagnostics report.
        """
        out = []
        for d in diagnostics:
            if d.confidence < threshold:
                continue
            if d.severity_rank < 2:  # info/warning stay report-only as pills
                continue
            sug = d.to_suggestion()
            if self._suppression is not None and self._suppression.is_suppressed(sug):
                continue
            out.append(sug)
        return out

    # -- Internals -----------------------------------------------------------

    def _dedup_sort(self, diagnostics):
        seen: set[str] = set()
        out = []
        for d in diagnostics:
            if self._suppression is not None:
                sug = d.to_suggestion()
                if self._suppression.is_suppressed(sug):
                    continue
            if d.id in seen:
                continue
            seen.add(d.id)
            out.append(d)
        out.sort(key=lambda d: (d.severity_rank, d.confidence), reverse=True)
        return out
