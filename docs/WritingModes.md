# Project Writing Mode (Phase 9)

A project declares **what kind of work it is** — Novel, Screenplay, Graphic
Novel, Stage Script, or Series — and every major section adapts to that
declaration. Writing mode is a real **project-level source of truth**, not a
per-view dropdown.

## The canonical field

The writing mode **is** the existing `Project.narrative_engine` column. Its
allowed values already match the five modes exactly, it migrates safely (legacy
`format_mode` is backfilled to an engine, defaulting to `novel`), and
`project_compat` already validates it. A second `writing_mode` column would
duplicate this and risk divergence, so it was deliberately **not** added.

`storyplanner/writing_modes.py` is the single unified API:

- `ALL_MODES`, `DEFAULT_MODE` (`novel`), `MODE_LABELS`
- `is_valid_mode()`, `normalize_mode()` (invalid/missing → `novel`)
- `get_project_writing_mode(project)` / `get_project_writing_mode_by_id(db, id)`
- `set_project_writing_mode(db, id, mode)` (writes the canonical field)
- `structural_units()` / `structural_vocabulary()` — display hierarchy
- `medium_constraints()` / `mode_context_block()` — Assistant `[Project Mode]` block

## Structural vocabulary (display)

| Mode | Vocabulary |
|---|---|
| Novel | Acts / Chapters / Scenes |
| Screenplay | Acts / Sequences / Scenes |
| Graphic Novel | Chapters / Pages / Panels |
| Stage Script | Acts / Scenes / Beats / Stage Directions |
| Series | Seasons / Episodes / A/B/C Plots / Scenes |

This is the friendly **presentation** layer. The finer generation-level
structural units live on each `NarrativeEngine` (`engine_structural_units`) and
drive the Outline.

## Propagation

- **Projects** — engine picker on create (`new_project_dialog`) and edit
  (`project_settings_dialog`, which confirms before changing). Saving re-enters
  the project so every view rebuilds.
- **Dashboard** — shows the mode chip plus a `Structure: …` vocabulary line.
- **Manuscript** — `writing_core_view` loads the mode's `WritingFormat`.
- **Outline** — labels and the generation prompt come from the mode's engine
  units (non-destructive — no schema conversion).
- **Assistant** — a short, gated `[Project Mode]` block
  (`include_project_mode_in_assistant_context`, default **on**) via
  `assistant_context_policy`. No LLM/DB during assembly.
- **Logos** — `LogosContext.writing_mode` carries the mode to every action.
- **Strategy Layer** — `medium_profiles` + `router` route by mode; the
  explanation names the mode. Priority: user override → project mode → template
  → plugins → section → default (`novel`).
- **Health / Diagnostics** — `HealthEngine` / `DiagnosticsEngine` accept and
  resolve `writing_mode`; the report records it. No metrics are invented.
- **Export** — JSON metadata and the Markdown header include `writing_mode`.

## Remaining limitations / deferred

- No full medium-specific engines yet (screenplay PDF, graphic-novel script,
  stage-play format, series-bible export) — documented for a later phase.
- Health/Diagnostics carry the mode but do not yet re-weight categories per
  mode (no fabricated metrics).
- PSYKE/Plot/Timeline/Graph are mode-*aware* (receive the mode) but keep their
  generic schema; mode-specific fields are deferred.
- Project-settings confirmation triggers on any engine change (a safe superset
  of "only when the project has data").
