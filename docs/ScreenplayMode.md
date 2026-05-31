# Screenplay Mode (Phase 10A foundation)

When a project's writing mode is **Screenplay** (`Project.narrative_engine ==
"screenplay"`, exposed via `writing_modes`), Logosforge adapts the Manuscript,
Assistant, Logos, Strategy, and Export layers. Phase 10A is the *foundation* —
not a Final Draft clone.

## Project Writing Mode vs Manuscript Element Type

Two distinct concepts — never conflated:

- **Project Writing Mode** = *what kind of work this is* (Screenplay). One
  authoritative value per project (`narrative_engine`).
- **Manuscript Element Type** = *how the current text block is formatted*
  (Scene Heading / Action / Character / Dialogue / Parenthetical / Transition).
  Choosing an element type is local editor/text state; it never changes the
  project's writing mode.

## Element taxonomy (`storyplanner/screenplay.py`)

The canonical, single-source taxonomy (no scattered strings):

| Key | Label | Uppercase | Dialogue | Structural |
|---|---|---|---|---|
| scene_heading | Scene Heading | ✓ | | ✓ |
| action | Action | | | |
| character | Character | ✓ | ✓ | |
| parenthetical | Parenthetical | | ✓ | |
| dialogue | Dialogue | | ✓ | |
| transition | Transition | ✓ | | ✓ |
| shot | Shot | ✓ | | |
| note | Note | | | |

Helpers: `is_uppercase_element`, `normalize_caps`, `dialogue_elements`,
`structural_elements`, `SCENE_HEADING_PREFIXES` (INT./EXT./…), and
`character_suggestions(db, pid)` (PSYKE character names, uppercased, read-only).

## Manuscript

The editor already renders the six core elements with screenplay styling
(margins, caps, alignment) and offers them in the element selector + Ctrl+1..6
when the project mode is Screenplay (`writing_formats.SCREENPLAY`). Novel editing
is unchanged. `normalize_caps` provides safe, opt-in uppercasing for
caps elements; no aggressive autoformatting changes user text.

## Assistant context

The controlled `[Project Mode]` block (via `assistant_context_policy` →
`writing_modes.mode_context_block`) gains one short screenplay guidance line in
Screenplay mode: *prefer visible action, scene economy, subtextual dialogue,
clear scene turns, setup/payoff; avoid novelistic interior exposition unless
requested.* Deterministic, capped, no LLM/DB during assembly.

## Logos actions

New screenplay-only actions (registered with `modes=("screenplay",)`, so they
**never appear in Novel** and surface + sort first in Screenplay):

- **Manuscript:** Convert Prose to Visual Action, Check Scene Turn, Reduce
  Novelistic Interior Exposition, Clarify Character Objective, Improve Scene
  Economy (plus existing Improve Dialogue / Improve Subtext / Compress).
- **Outline:** Check Sequence Logic, Strengthen Act Turn, Clarify Central
  Dramatic Question.
- **Plot:** Track Setup/Payoff, Check Causal Chain, Check Visual Turn.

All non-destructive and run through the normal Logos preview/confirm path.

## Strategy

`StrategyRouter` already activates the Screenplay medium profile automatically
when the project mode is Screenplay; a manual override still wins, and the
strategy explanation names the mode. Go McKee / Controlling Idea still layer in
when enabled; Quantum/Lambda does not override the medium unless selected.

## Health / Diagnostics

The engines **receive** the writing mode (`HealthEngine` / `DiagnosticsEngine`).
Screenplay-specific *detectors* (no-visible-turn, expositional dialogue, unclear
objective, novelistic action, setup/payoff tracking, weak scene economy) are
**deferred to Phase 10B** rather than faked — current data does not support them
without per-block element metadata.

## Export

`export_screenplay()` produces conservative screenplay-style text: uppercased
title, a `Writing Mode: Screenplay` header line, per-scene slug lines
(`INT. PLACE — TITLE`) and scene body. Fountain/FDX/PDF helpers exist but emit
body text as generic action. JSON/Markdown metadata include `writing_mode`.
Robust when a project has no scenes or an invalid mode (falls back to novel).

## Intentionally deferred to Phase 10B

- **Per-block element persistence** — scene content is currently flat
  text/markdown; block element types live only in-memory while editing. A
  block-level screenplay document model (safely migrated) is required for true
  element-aware editing/export and is **Phase 10B**.
- Shot/Note dedicated editor styling + selector entries.
- Element-aware Fountain/FDX reconstruction; PDF pagination, revision colors,
  locked pages, production drafts, dual dialogue, scene numbering.
- Screenplay-specific Health/Diagnostics detectors and runtime estimation.
- Tab/Enter element cycling and character/scene-heading autocomplete UI
  (helpers exist in `screenplay.py`; wiring is deferred).

## Limitations

Because block element types aren't persisted yet, export cannot reconstruct
CHARACTER/DIALOGUE/PARENTHETICAL structure from saved content — it works from
flat content + scene slug metadata only. This is the primary 10B prerequisite.
