# Writing Formats

A **Writing Format** encodes *how the manuscript renders and exports* — the set of
block element types available in the editor and their typography (font size,
weight, caps, alignment, margins, spacing, colour). It is the rendering axis,
deliberately **orthogonal** to the [Narrative Engine](narrative-engines.md)
reasoning axis.

> Source: `storyplanner/writing_formats.py`. Each format is an immutable
> `@dataclass(frozen=True)` `WritingFormat` holding a list of `ElementStyle`s,
> registered in `ALL_FORMATS`.

---

## Engine vs Format

| | Narrative Engine | Writing Format |
|---|------------------|----------------|
| Governs | *How the story reasons* | *How the manuscript renders/exports* |
| Examples | screen-time pacing, A/B/C plots, panel rhythm | scene-heading caps, dialogue margins, caption styling |
| Lives in | `narrative_engines/` | `writing_formats.py` |

The two never reference each other. A project stores both
`Project.narrative_engine` and `Project.default_writing_format`. When you change
the engine, `project_compat.default_format_for_engine()` suggests a matching
format, but you can pair them independently.

---

## The five rendered formats

`ALL_FORMATS` (order in pickers: `FORMAT_ORDER`) defines five concrete formats,
each a set of styled block elements:

| Format | Default block | Block elements |
|--------|---------------|----------------|
| **Novel** | `body` | chapter, scene_break, body |
| **Screenplay** | `action` | scene_heading, action, character, dialogue, parenthetical, transition |
| **Graphic Novel** | `panel` | page, panel, description, character, dialogue, internal_thought, caption, sfx, art_direction, transition, note |
| **Stage Script** | `dialogue` | act_heading, scene_heading, character, dialogue, stage_direction, parenthetical, aside, cue, transition, note |
| **Series** | `action` | season_heading, episode_heading, act_heading, scene_heading, action, character, dialogue, a_plot, b_plot, c_plot, teaser, cold_open, tag, cliffhanger, recap_note, continuity_note |

### `ElementStyle` fields

Each block element carries the visual/behavioural rules the editor applies:

`name`, `shortcut`, `font_size`, `bold`, `italic`, `all_caps`, `align`,
`left_margin`, `right_margin`, `top_spacing`, `bottom_spacing`,
`first_line_indent`, `line_height`, `color_key` (`text`/`muted`/`secondary`/
`accent`), `background_key` (`""`/`panel`/`sfx`/`note` — a subtle band).

Margins are in pixels, calibrated for a 720 px text area (≈ 6.0 in US-letter
text width, so 1 in ≈ 120 px). Screenplay margins follow the Final Draft / WGA
standard.

In the editor (`writing_core_view.py`) you switch the active element with the
**element combo** in the toolbar, via the per-element **Ctrl+1…6** shortcuts,
or by pressing **Tab / Shift+Tab** to cycle. The `/` **command palette** can
insert structural blocks too.

---

## Format detail

### Novel
Generous, sustained-reading prose. `chapter` is a 26 pt bold heading with large
top space; `scene_break` is a centred separator; `body` is 18 pt at 1.5 line
height. Designed to disappear so the prose carries.

### Screenplay
Industry-standard layout where differentiation comes from margins, caps and
alignment rather than font size (everything is 15 pt, the Courier-12 equivalent):

| Element | Rule |
|---------|------|
| Scene Heading | full width, bold, ALL CAPS |
| Action | full width |
| Character | 2.2 in left indent, ALL CAPS |
| Dialogue | 1.0 in left / 1.5 in right |
| Parenthetical | italic, 1.5 in left / 2.0 in right |
| Transition | right-aligned, ALL CAPS |

### Graphic Novel
A "full script" comics workspace (Dark Horse / DC style). `page` and `panel` are
bold headers; `description` is the panel's staging on a subtle panel band;
`character`/`dialogue` indent toward the balloon column; `internal_thought` is a
secondary-colour thought balloon; `caption` is a muted narration box; `sfx` is
loud accent-coloured lettering on a band; `art_direction` and `note` are muted
italic asides to the artist.

### Stage Script
Samuel French / standard playwriting layout. **Dialogue is the widest element**,
running margin-to-margin. Character names, act and scene headings are centred and
capitalised; `stage_direction` is muted italic on a band; `cue` is a compact
accent-coloured technical marker.

### Series
Follows the screenplay rules for scene-level elements and adds episodic
structure: `season_heading` / `episode_heading` / `act_heading` markers,
colour-tagged `a_plot` / `b_plot` / `c_plot` labels, distinctive `teaser` /
`cold_open` / `tag` opener blocks, an accent `cliffhanger`, and muted
`recap_note` / `continuity_note` editorial blocks.

---

## Abstract (non-rendered) formats

The compatibility layer (`project_compat.py`) defines three extra format *names*
that have no block grammar in the editor and are used as planning/labels rather
than rendered manuscripts:

| Constant | Label |
|----------|-------|
| `FORMAT_TREATMENT` | Treatment |
| `FORMAT_BEAT_SHEET` | Beat Sheet |
| `FORMAT_OUTLINE` | Outline |

Together with the five concrete formats (`prose`, `screenplay`, `stage_script`,
`graphic_novel`, `series`) these make up `project_compat.ALL_FORMATS`. Only the
five concrete ones appear in `writing_formats.ALL_FORMATS` and drive editor
rendering.

---

## Default format per engine

When the engine changes, `project_compat.default_format_for_engine()` suggests:

| Engine | Suggested format |
|--------|------------------|
| Novel | Prose |
| Screenplay | Screenplay |
| Stage Script | Stage Script |
| Graphic Novel | Graphic Novel Script |
| Series | Screenplay |

`get_project_writing_format(project)` resolves the active format, reading
`Project.default_writing_format` and falling back to the legacy `format_mode`
mapping. Export honours the resolved format's structure and typography — see
[export-import.md](export-import.md).
