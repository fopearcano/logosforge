# Narrative Health Engine

`storyplanner/logos/health/` turns Logos PSYKE diagnostics into an explainable,
project-level health report. Rule-based, evidence-driven, **no fake percentages**,
no background LLM, no DB mutation.

## Report

`HealthEngine.generate_report()` builds a shared `ProjectFacts` snapshot once,
runs the diagnostics, and aggregates them into one `NarrativeHealthMetric` per
category, then derives an overall status and prioritized recommendations.

### Categories (12)
Structure, Character, Relationships, Theme/Motif, Continuity, Timeline, Pacing,
Scene Purpose, Setup/Payoff, PSYKE Completeness, Graph Connectivity, Notes
Integration.

### Status labels (no scores)
`Stable` · `Needs Attention` · `Weak Area` · `Critical Risk` · **`Not Enough
Data`** (used whenever a category has no analyzable data — never a false
negative).

### Overall status
`critical` if any critical metric or ≥2 weak **core** categories
(structure/continuity/character); else `weak` / `watch` / `stable`; `unknown`
when no category has data.

## Recommendations

Deterministic, derived from important/critical diagnostics: each carries problem,
why-it-matters, evidence, a mapped **existing Logos action**, and a target. There
is no autonomous fixing — acting on a recommendation runs the Logos action
through the normal preview/confirm path.

## UI

`LogosDiagnosticsDrawer` (diagnostics) and `LogosDiagnostics`/health drawer show
status cards, top risks, strengths, and recommendations with **Ask Logos**,
**Open Target**, **Dismiss**, **Copy**, **Refresh**, and **Export JSON/MD**.
Non-modal, never steals focus, hidden by default. Dismissals share the proactive
`SuppressionStore`.

## Refresh / safety

- Current-section diagnostics rescan on section change / `project_data_changed`;
  the health report refreshes on toggle / manual refresh / project switch.
- Scans never call the LLM and never mutate the DB.
- On project switch the drawers are cleared and the engines re-pointed, so no
  stale findings from the previous project are shown.

## Assistant integration (opt-in)

`health_context.top_risks_text()` produces a compact `[Narrative Health]` block
for optional prompt inclusion (`health_include_in_assistant`, default **false**).
The Assistant is not auto-fed the report.

## Screenplay-mode categories (Phase 10C)

For projects whose writing mode is **screenplay**, the report appends mode-aware
categories computed deterministically from the screenplay diagnostics engine
(`storyplanner/screenplay_diagnostics.py`): **Visual Action, Scene Economy,
Dialogue Economy, Scene Turn, Character Objective, Setup/Payoff**. Status uses the
same no-score labels; categories with no analyzable data return *Not Enough Data*.
Phase 10D additionally populates **Dialogue Subtext, Motif Recurrence** and
**On-the-Nose Dialogue Risk** from the deterministic setup/payoff + subtext
engines. Phase 10E adds **Confirmed Setup/Payoff Coverage** (confirmed
`StoryLink`s weigh more than candidates) and **Unresolved Candidate Density**
(a cautious warning, never a hard failure). **Cinematic Continuity** remains
deferred (*Not Enough Data* until Phase 10F). No fake precision, no background
LLM, no DB mutation. Novel/other modes are unaffected.

## Settings (defaults)

`health_enabled=True`, `health_auto_refresh_on_load=True`,
`health_include_in_assistant=False`, `health_show_unknown=True`.
