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

## Phase 10B — Screenplay block engine + export hardening

`storyplanner/screenplay_blocks.py` adds a lightweight, **non-persisted** block
layer derived on demand from flat scene text (no DB schema change):

- **`ScreenplayBlock`** — `element_type / text / scene_id / order_index /
  metadata`; element type is validated centrally (invalid → `action`).
- **`parse_screenplay_text(text, scene_id=None)`** — conservative heuristics on
  blank-line-separated chunks: `INT./EXT./EST.` → scene_heading; uppercase lines
  ending `TO:` / `FADE …` → transition; an uppercase short cue leading a chunk →
  character, with following `( … )` → parenthetical and other lines → dialogue;
  everything uncertain → **action** (no false positives, no text loss).
- **`serialize_blocks(blocks, uppercase=True)`** — round-trip-safe text;
  uppercases caps elements, normalizes parentheticals.
- **`to_fountain(blocks)`** — Fountain-like output (forced `.` headings only when
  needed, `> ` transitions, `[[ ]]` notes).
- **`character_cues(blocks)`** — unique, uppercased cues present in a scene.

**Export hardening:** `export_screenplay` and `export_fountain` now render each
scene body through the parser/serializer, so character cues / transitions /
scene headings are uppercased and parentheticals normalized — while preserving
all text. Novel export is unaffected; both carry the `Writing Mode` metadata.

**Current element in context:** `WritingCoreView.current_element_type()` exposes
the cursor block's element; the host carries it into `LogosContext.active_block_type`
(only for screenplay element keys, so Novel stays `prose`). The Assistant gains a
concise `[Screenplay Scene]` line (heading + characters present, parsed from the
scene) when the project is a screenplay and a scene is active — data-driven, capped.

**Logos (hardened set):** added `Strengthen Setup/Payoff`, `Detect Overwritten
Action` (Manuscript) and `Improve Escalation` (Outline), all screenplay-only and
preview/confirm.

## Phase 10C — deterministic screenplay diagnostics + scene economy

`storyplanner/screenplay_diagnostics.py` evaluates a scene **as a screenplay
scene** (built on the 10B block parser) — rule-based, no LLM, no DB writes,
confidence-aware.

- **`ScreenplaySceneReport`** / **`ScreenplayDiagnosticIssue`** (serializable):
  block/character counts, dominant block type, `economy_label`
  (dialogue-heavy / action-heavy / balanced / sparse), an approximate page/minute
  estimate (clearly rough), plus issues / strengths / warnings / summary.
- **Checks** (documented thresholds as module constants): scene economy ratios,
  missing scene heading, only-notes, internal-prose action, overwritten action,
  long dialogue, parenthetical overuse, single-voice scenes, transition/shot
  overuse, **scene-turn heuristic** (says *"Scene turn unclear"* with low
  confidence — never asserts absence), **character objective** (PSYKE-aware:
  missing data lowers confidence, never hard-fails), and cautious **setup/payoff
  candidates** ("Possible setup" — hooks for Phase 10D).

**Warning vs error:** every issue is a *warning/suggestion* with a severity
(`info` / `watch` / `weak` / `critical`) and confidence — never a hard error, and
nothing is auto-changed.

**Logos:** `Diagnose Scene Economy` (`sp_diagnose_scene_economy`) is a
**deterministic** action — it runs the engine with **no LLM call** (routed via
`storyplanner/logos/deterministic.py`). Generative helpers (`Tighten Dialogue
Economy`, `Suggest Visual Beat`, `Suggest Action Interruption`, plus the 10A/10B
set) call the Assistant only when the user explicitly invokes them, always
through preview/confirm. All screenplay-only and hidden in Novel.

**Assistant:** a concise `[Screenplay Diagnostics]` block (economy summary + top
3 issues) is injected for screenplay projects with an active scene
(`include_screenplay_diagnostics_in_assistant_context`, default on) — capped,
deterministic, no LLM/DB during assembly.

**Narrative Health:** for screenplay projects the report appends mode-aware
categories — Visual Action, Scene Economy, Dialogue Economy, Scene Turn,
Character Objective, Setup/Payoff — computed from the deterministic engine.
Subtext Candidate and Cinematic Continuity are present but **deferred**
(`Not Enough Data`). No fake precision; no background LLM.

**Export:** `export_screenplay_diagnostics_json(db, project_id)` emits per-scene
reports + writing mode (additive; existing exports untouched).

## Intentionally deferred to Phase 10D

- Cross-scene setup/payoff tracking engine (10C only flags candidates).
- Dedicated screenplay-diagnostics drawer + click-to-focus-block (today the
  diagnostic surfaces via the Logos toolbar action).
- Subtext / Cinematic Continuity detectors (need an LLM); precise runtime.

## (Earlier) Intentionally deferred to Phase 10C

- **Per-block element persistence** — block types are still in-memory while
  editing and re-derived (by the parser) for export/analysis; durable per-block
  storage needs a (safely migrated) schema and is **Phase 10C**.
- Shot/Note dedicated editor styling + selector entries.
- FDX export, PDF pagination, revision colors, locked pages, production drafts,
  dual dialogue, production scene numbering.
- Screenplay-specific Health/Diagnostics detectors and runtime estimation.
- Tab/Enter element cycling and character/scene-heading autocomplete UI
  (helpers exist in `screenplay.py` / `screenplay_blocks.py`; wiring deferred).

## Limitations

Block types are **derived from saved text**, not stored — so export/analysis
reconstruct structure heuristically and a hand-typed novelistic block may be
read as `action`. Durable per-block element storage is the primary 10C
prerequisite. Parsing is intentionally conservative (prefers `action`).
