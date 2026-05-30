# Structure & Plotting Tools

Logosforge separates *writing* from *structuring* without separating them in your
workflow. This page documents the tools for shaping a story's architecture: the
Controlling Idea, the Outline, the Story Grid, Multi-Plot, the Timeline, the
engine-specific Plot grids, narrative versioning with Stages, and the scene and
analysis views.

All of these adapt to the project's [narrative engine](narrative-engines.md): the
unit they show (chapter / scene / page / episode) and the meaning of "time" come
from the engine profile.

---

## Controlling Idea

> Source: `storyplanner/controlling_idea.py`. Also exposed as the bundled
> *Idea di Controllo* plugin.

The **Controlling Idea** is the story's thematic spine in Robert McKee's sense —
a **VALUE + CAUSE** statement such as *"Justice prevails when the hero sacrifices
personal safety for truth."* It is stored in the project settings (no schema
change) and carries:

- a `value`, `cause`, composed `statement`, and `value_charge`
  (positive / negative / ambiguous),
- a `counter_idea` (the opposing worldview that creates dramatic tension),
- **scene alignment** — each scene can be marked *supports / opposes / tests /
  transforms* the idea,
- **PSYKE alignment** — entries can be marked the same way, and the idea can
  auto-create a mirroring PSYKE *theme* entry,
- editorial `notes`.

`gather_controlling_idea_context()` injects an `[Idea di Controllo]` block into the
AI prompt (see [ai-assistant.md](ai-assistant.md)); `check()` audits which scenes
and entries align, oppose, or are unmarked, and suggests fixes (e.g. "no
counter-idea defined"). The `/idea` console command drives it: `set`, `explain`,
`check`, `link`, and `scene <id> <alignment>`.

---

## Outline

> Source: `storyplanner/outline_templates.py`, `outline_actions.py`,
> `ui/outline_view.py`. Persisted as a tree of `OutlineNode` rows.

The Outline is an editable hierarchical tree whose node labels follow the engine's
structural units (Part/Chapter/Scene for Novel; Issue/Chapter/Page for Graphic
Novel; Season/Episode for Series; …). It can be built three ways:

- **From a template** — built-in templates ship in `outline_templates.py` (Hero's
  Journey, Three-Act, Save the Cat, Story Circle, Five-Act/Freytag, …). Plugins can
  register more — the bundled **PSYKE Outline Templates** plugin adds a large
  catalogue across classical, modern, non-Western, and genre methods (Seven-Point,
  Kishōtenketsu, Heroine's Journey, Snowflake, Mystery, Rom-Com, Quest, and more),
  and can infer the best template from the story's genre/conflict/arc/pacing.
- **By AI generation** — `outline_actions.build_outline_generation_prompt()` builds
  an engine-aware, template-aware, PSYKE-aware prompt; the model's response is
  parsed by `parse_outline_response()` (robust to Markdown headers, bullet/numbered
  lists, and keyword prefixes) into a tree of `OutlineOp`s; a preview is shown for
  confirmation, then `apply_outline_ops()` creates the nodes **additively** under
  any selected parent. This is the Assistant's **Outline Mode**.
- **By hand** — edit titles and descriptions directly in the tree.

---

## Story Grid

> Source: `storyplanner/ui/story_grid_view.py`, with flow indicators from
> `story_flow.py`.

The Story Grid lays scenes out as cards in columns grouped by act (or, for Graphic
Novel projects, pages grouped by issue). Each card shows its number/type, title,
summary, metadata (beat, tags, plotline, act), engine-specific fields (duration,
location, INT/EXT, time of day for screenplay; panel count, pacing, motifs for
graphic novel), character colour dots, and a **tension bar**. Cards support
drag-and-drop reordering within and between acts, zoom, colour labels, and a
right-click menu (open in manuscript, edit, move to act, colour, delete). A pacing
warning badge appears over runs of monotone tension.

**Story Flow** (`story_flow.py`) computes the lightweight signals the grid renders:
per-scene tension (0–10, inferred from manual tags, beat type, conflict, and
content keywords), scene type (dialogue / action / exposition / mixed by line and
word ratios), and pacing warnings (4-scene windows that are monotone-low,
monotone-high, or flat).

---

## Multi-Plot

> Source: `storyplanner/ui/multi_plot_view.py`.

Multi-Plot is a container offering several views — **Grid**, **Timeline**, **Arc**,
**Character** — over the same scenes, with a shared filter by character, tag, or
plotline. It is the home for tracking subplots and A/B/C strands and seeing how
they interleave.

---

## Timeline

> Source: `storyplanner/ui/timeline_view.py`; engine helpers in
> `graphic_novel_plot.py`, `stage_script_plot.py`, `series_plot.py`.

The Timeline shows scenes/events in reading order, grouped by plotline or chapter,
and is **engine-aware**:

- **Screenplay** adds duration, location, INT/EXT, and time-of-day to cards.
- **Graphic Novel** becomes a reading-flow view of pages with panel counts,
  density/rhythm chips, page-turn pairs (setup → reveal), reveal markers, splash
  pages, emotional beats, and motif/character chips — expandable to panel detail.
- **Stage Script** shows performance order with entrances/exits, cues, offstage
  events, prop continuity, and an emotional-pressure label per scene.
- **Series** groups episodes under seasons with A/B/C plot indicators, active arcs,
  cliffhangers, and setup/payoff markers.

The [QUANTUM Outliner](quantum-outliner.md) overlays its branch superposition and
probabilities on a parallel quantum timeline.

---

## Engine-specific Plot grids

Pure, UI-free helpers make the Plot and Timeline views engine-aware:

| Engine | Module | What it groups / surfaces |
|--------|--------|---------------------------|
| Graphic Novel | `graphic_novel_plot.py` | Blocks per **sequence** (or page); page pacing classification (quiet / dense / explosive / exposition-heavy / cinematic), density→rhythm mapping, page-turn map, silence/action pattern. |
| Stage Script | `stage_script_plot.py` | Scenes grouped by **act**; per-scene objective, dramatic turn, characters on stage, entrances/exits, cues, important props, emotional pressure. |
| Series | `series_plot.py` | Episodes grouped by **season**; A/B/C plot indicators, active arcs (setup ≤ here ≤ payoff), cliffhangers, setup/payoff markers, colour-coded plotline/arc types. |

---

## Stages — narrative versioning & branching

> Source: `storyplanner/stages.py`, `ui/stages_view.py`. Backed by the `Stage`,
> `StageSnapshot`, and `StageBranch` tables.

**Stages** are named versions of your story (or part of it) — for keeping
alternate endings, experimenting safely, and branching what-ifs. A stage has a
scope (`project` / `scene` / `chapter` / `outline` / `psyke`), a status
(`canonical` / `alternate` / `archived`), and an optional parent (a branch edge).

The core operations:

- `capture_scope()` reads the current state of a scope into a serializable snapshot.
- `save_snapshot()` stores it under a stage with an auto-generated summary.
- `restore_snapshot()` writes a snapshot back into the project — and, by default,
  **first captures a "Safety (auto)" snapshot** of the current state so any restore
  is undoable.
- `diff_payloads()` produces an added/removed/changed unified diff between two
  snapshots.
- `branch_from()` creates a child stage seeded from an existing stage's snapshot.

Quantum collapses can also be turned into stages (`create_from_quantum_collapse`),
tying the two branching systems together. The Stages view presents the stage/
snapshot tree, status controls, the diff viewer, and restore/branch/compare/delete
actions.

---

## Scenes view

> Source: `storyplanner/ui/scenes_view.py`.

The Scenes view is a scene list + editor with chapter/plotline/tag filters,
move-up/down ordering, and a content editor with PSYKE highlighting. The right
pane edits planning fields (beat, tags, act, chapter, plotline, goal/conflict/
outcome), the characters present and their per-scene states, and the
engine-specific fields (screenplay duration/location/turn; theatre objective/props/
offstage). It embeds the inline assistant and a backlinks widget, and offers a
focus mode that hides planning fields for distraction-free writing. Edits are saved
on a short debounce.

---

## Analysis views

Three lightweight, read-only dashboards roll scene metadata into HTML tables:

- **Acts** (`act_analysis_view.py`) — scenes per act, ranges, and unassigned
  scenes.
- **Beats** (`beat_analysis_view.py`) — beat counts and positions, highlighting
  key beats (Midpoint, All Is Lost, Climax, Finale, Break into Three).
- **Tags** (`tag_analysis_view.py`) — tag frequencies, per-tag scene lists, and
  untagged scenes.

See [writing-analysis.md](writing-analysis.md) for the deeper craft analyzers
(story health, pacing, character balance, structural intelligence) and
[narrative_dashboard.md](narrative_dashboard.md) for the visual story-intelligence
dashboard.
