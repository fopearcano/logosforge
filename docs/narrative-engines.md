# Narrative Engines

A **Narrative Engine** encodes *how a story is reasoned about*. It is the single
most important per-project choice in Logosforge: it shapes how every section —
Outline, Plot, Timeline, Graph, PSYKE, and the AI Assistant — interprets your
story.

Engines are deliberately **orthogonal to Writing Formats**. An engine governs
*reasoning*; a format governs *manuscript rendering*. See
[writing-formats.md](writing-formats.md) for the other axis.

> Source: `storyplanner/narrative_engines/`. Each engine is an immutable
> `@dataclass(frozen=True)` instance of `NarrativeEngine` (`base.py`),
> registered in `registry.py`.

---

## The five engines

| Engine | Structural units | Plot block | Timeline semantics |
|--------|------------------|-----------|--------------------|
| **Novel** | Part → Chapter → Scene | chapter | chronological chapters |
| **Screenplay** | Act → Sequence → Scene → Beat | scene | screen time |
| **Graphic Novel** | Issue → Chapter → Sequence → Page → Panel | sequence | reading progression |
| **Stage Script** | Act → Scene → Beat → Entrance/Exit → Cue | scene | performance order |
| **Series** | Series → Season → Episode → Act → Scene (+ A/B/C plotlines, Arcs) | episode | episode/season progression |

You choose an engine when creating a project (New Project dialog) and can change
it later (Project Settings). Changing the engine re-enters the project so every
view rebuilds against the new reasoning model.

---

## Anatomy of a `NarrativeEngine`

Every engine is described by the same fields (`narrative_engines/base.py`):

| Field | Meaning |
|-------|---------|
| `name`, `label`, `description` | Identity and human-readable summary. |
| `structural_units` | The hierarchy of containers available (e.g. `("part", "chapter", "scene")`). |
| `plot_block_unit` | The unit the Plot grid defaults to (`chapter`/`scene`/`page`/`sequence`/`episode`). |
| `timeline_semantics` | What "time" means for this form (`chronological_chapters`, `screen_time`, `reading_progression`, `performance_order`, `episode_season_progression`). |
| `assistant_priorities` | Ordered list of what the AI should prioritize. |
| `assistant_terminology` | Renames generic terms (`block`, `unit`, `chapter`, `scene`) per form. |
| `psyke_context_rules` | Which Story Bible signals to inject as AI context. |
| `review_checks` | The deterministic review checks this engine runs. |
| `default_format`, `compatible_formats` | The suggested Writing Format and the set it can pair with. |
| `system_prompt_overlay` | A reasoning preamble injected into the AI system prompt. |
| `feedback_patterns` | Common failure modes the assistant watches for. |

The engine's `format_context_block()` renders a compact, prompt-ready summary
(`[Narrative Engine: …]`) that the [context pipeline](ai-assistant.md) injects so
the model reasons in the right register.

### Resolving the engine for a project

Use `narrative_engines.engine_for_project(project)` or
`project_compat.get_project_narrative_engine(project)`. Both read the modern
`Project.narrative_engine` field and fall back to the legacy `format_mode` via
`project_compat.resolve_legacy_format()`. Unknown names resolve to **Novel**.

---

## Novel

*Long-form prose fiction: interiority, narrative voice, chapter pacing, character
arc, thematic recurrence.*

- **Structure:** Part → Chapter → Scene. Plot blocks are **chapters**; the
  timeline is **chronological by chapter**.
- **Assistant priorities:** interiority, narrative voice, prose rhythm, chapter
  pacing, character arc, thematic recurrence.
- **PSYKE rules:** character interior state, relationships, themes, locations, lore.
- **Review checks:** chapter purpose, scene turn, POV consistency, prose rhythm,
  character-arc movement.
- **Default format:** Novel (prose).

Novel is the default fallback engine whenever a name can't be resolved.

---

## Screenplay

*Visual, temporal, performative, production-aware storytelling.*

- **Structure:** Act → Sequence → Scene → Beat. Plot blocks are **scenes**;
  pacing is measured in **screen time**, not page count.
- **Assistant priorities:** visual action, cinematic pacing, scene duration,
  blocking, subtext, setup/payoff, dialogue economy, continuity.
- **PSYKE rules:** subtext state, character knowledge state, continuity, visual
  motifs.
- **Review checks:** scene turns, dialogue economy, visual conflict, duration,
  setup/payoff, blocking clarity.
- **Default format:** Screenplay. **Compatible with:** screenplay, series.
- **System overlay:** instructs the model to "reason cinematically" — evaluate
  every scene as a unit of screen time, prioritize what the camera sees and the
  audience hears, demand a turn, visible conflict, subtext, economical dialogue,
  honored setup/payoff, and intact continuity.

Screenplay projects unlock the full set of cinematic Scene fields (slugline,
INT/EXT, time of day, estimated duration, visual objective, dramatic turn,
blocking, subtext, setup/payoff links, montage group, plus the PSYKE cinematic
extensions: visible/hidden conflict, emotional turn, who-knows-what, physical
action, visual symbolism).

---

## Graphic Novel

*Spatial-sequential comics storytelling — meaning emerges from how images are
arranged in space and revealed in sequence.*

- **Structure:** Issue → Chapter → Sequence → Page → Panel. Plot blocks default
  to **sequences** (a run of pages with one dramatic/visual purpose), never
  chapters. The timeline is **reading progression** — page rhythm and reveal
  timing.
- **Assistant priorities:** panel rhythm, page turns, visual reveal timing,
  composition, image/text balance, visual continuity, symbolic recurrence,
  silhouette readability, panel flow, emotional page energy.
- **PSYKE rules:** character *visual identity*, motif recurrence, object/costume
  continuity, shape language, symbolic tracking. (PSYKE acts as **visual memory**
  here — see [psyke.md](psyke.md).)
- **Review checks:** panel readability, exposition density, page-turn impact,
  visual pacing, balloon overload, image/text balance, symbolic recurrence,
  panel-rhythm variety.
- **Default format:** Graphic Novel Script.
- **System overlay:** instructs the model to "reason as a comics author" — the
  page is a spatial composition and the book is a sequence of reveals.

The Graphic Novel engine activates a dedicated set of features unavailable to
other engines: the **Page Canvas / Pages view**, a page/panel-aware **Plot grid**
and **Timeline**, the **PSYKE Visual Memory** fields, the **visual-motif Graph
lens**, a deterministic **GN review** (`graphic_novel_review.py`), draft
generation from panels (`graphic_novel_manuscript.py`), and **image-prompt export**
for text-to-image tools (`graphic_novel_ai_export.py`). See
[structure-and-plot.md](structure-and-plot.md) and
[export-import.md](export-import.md).

---

## Stage Script

*Live, spatial, performative, actor-driven storytelling — everything must be
playable live by an actor on a stage in front of an audience.*

- **Structure:** Act → Scene → Beat → Entrance/Exit → Cue. Plot blocks are
  **scenes**, grouped by acts; the timeline is **performance order**.
- **Assistant priorities:** playable conflict, spoken pressure, subtext, actor
  motivation, entrances/exits, stage blocking, physical business, stageable
  action, audience visibility, prop continuity, act breaks, scene objective.
- **PSYKE rules:** character stage objective, spoken strategy, subtext,
  relationship pressure, entrances/exits, prop ownership, offstage knowledge,
  stage position. (PSYKE acts as **theatrical memory** — see [psyke.md](psyke.md).)
- **Review checks:** dialogue tension, playable action, actor motivation, blocking
  clarity, stage feasibility, dramatic pressure, actorial subtext, prop
  continuity, scene objective, act break.
- **Default format:** Stage Script.
- **System overlay:** instructs the model to "reason as a playwright and director"
  — no camera, no cut; space, bodies, and props only.

Stage Script projects add theatre-specific Scene fields (stage location, set
description, scene objective, entrance/exit notes, prop/cue notes, offstage
events, audience-visibility notes, performance duration) and the
`StageEntranceExit` / `StageCue` / `StageBusiness` tables. Props are not
duplicated — stage business references a PSYKE *object* entry. Theatrical PSYKE
relations (`pressures`, `confronts`, `avoids`, `dominates`, `submits`, `deceives`,
`overhears`, `interrupts`) model who applies pressure to whom. Deterministic
checks live in `stage_script_review.py`.

---

## Series

*Episodic, multi-episode storytelling — meaning accrues over the long arc through
recurrence, continuity, escalation, delayed payoff and A/B/C plot interplay.*

- **Structure:** Series → Season → Episode → Act → Scene, plus A/B/C **plotlines**
  and long **arcs**. Plot blocks are **episodes**; the timeline is **episode/season
  progression**.
- **Assistant priorities:** episode engine, season arc, series arc, A/B/C plot
  balance, continuity, recurring motifs, cliffhangers, callbacks, delayed payoff,
  character progression across episodes, unresolved threads, serialized-vs-
  procedural balance.
- **PSYKE rules:** long-running character states, relationship evolution across
  episodes, unresolved arcs, mystery boxes, recurring motifs, continuity ledger,
  episode memory, season-level stakes. (PSYKE acts as **long-form memory** — see
  [psyke.md](psyke.md).)
- **Review checks:** episode function, season-arc movement, A/B/C plot interaction,
  cliffhanger effectiveness, continuity integrity, long-arc progression, payoff
  timing.
- **Default format:** Screenplay. **Compatible with:** series, screenplay.
- **System overlay:** instructs the model to "reason as a showrunner" — every
  episode is both a unit and a movement in larger season/series arcs.

Series projects use the `Season` / `Episode` / `SeriesArc` / `EpisodePlotline`
tables, a season/episode-aware **Plot grid** and **Timeline**, and the
deterministic `series_review.py` checks. Arcs reuse PSYKE entries
(`SeriesArc.linked_psyke_entries`) rather than duplicating characters/themes.

---

## How engines drive the rest of the app

| Subsystem | What the engine controls |
|-----------|--------------------------|
| **AI Assistant** | Injects `format_context_block()`, the `system_prompt_overlay`, `assistant_priorities`, and `psyke_context_rules` into the prompt. The model literally reasons as a novelist / screenwriter / playwright / comics author / showrunner. |
| **Outline** | `outline_actions.build_outline_generation_prompt()` labels generated nodes with the engine's `structural_units` (Part/Chapter vs Issue/Chapter/Page vs Season/Episode). |
| **Plot & Timeline** | The grid groups by `plot_block_unit`; engine-specific helpers (`graphic_novel_plot.py`, `stage_script_plot.py`, `series_plot.py`) provide page/act/episode-aware views and `timeline_semantics`. |
| **Graph** | Default lens and available lenses adapt (e.g. Graphic Novel adds a Character-Appearance / visual-motif lens). |
| **PSYKE** | The engine selects which engine-specific memory layer is active — Visual (Graphic Novel), Theatre (Stage Script), or Series. |
| **Review** | `engine.review_checks` map to the deterministic review module for that form. |

Because the engine is a pure data profile, adding a new one is a matter of
writing a new `NarrativeEngine` instance and registering it — no changes to the
views, which read the profile generically.
