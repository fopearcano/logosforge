# PSYKE — The Story Bible

**PSYKE** is Logosforge's Story Bible: a persistent, structured knowledge base of
everything in your story world — characters, places, objects, themes, and lore —
plus their aliases, relationships, and how they change over narrative time. PSYKE
is the memory the AI Assistant reasons from, the source of the highlighting and
hover previews in the manuscript, and the backbone of the Graph.

> Source: `storyplanner/models/models.py` (`PsykeEntry`, `PsykeRelation`,
> `PsykeProgression`), `storyplanner/models/psyke_details.py` (field schemas),
> and the `storyplanner/psyke_*.py` modules. UI lives in
> `storyplanner/ui/psyke_view.py` and `psyke_console.py`.

---

## Entries

A `PsykeEntry` is one item in the bible:

| Field | Meaning |
|-------|---------|
| `name` | Display name. |
| `entry_type` | `character` · `place` · `object` · `lore` · `theme` · `other`. |
| `aliases` | Comma-separated nicknames/titles, used for matching and highlighting. |
| `notes` | Free-form notes. |
| `details_json` | Structured, type-specific fields (see below), plus nested engine-memory sections. |
| `is_global` | When true, the entry is always-relevant context (injected into every prompt). |

### Type-specific detail schemas

Each entry type exposes a rich, sectioned set of fields defined in
`psyke_details.py` as `FieldSpec`s (`get_detail_schema(entry_type)`), rendered as
line / multiline / combo widgets in the PSYKE editor:

- **character** — Identity (full name, age, gender, role, archetype), Appearance,
  Psychology (personality, strengths, flaws, fears, desires, needs, lie/misbelief),
  Background (backstory, occupation, skills, relationships), Voice & Arc, plus a
  **Screenplay** section (spoken voice, gesture vocabulary, silence pattern,
  performance mask, subtext strategy, physical behavior).
- **place** — Geography, Sensory (sights/sounds/smells/atmosphere), Society
  (population, culture, politics, economy, religion), History & Narrative.
- **object** — Physical, Properties (function, powers, limitations, activation),
  Provenance (origin, owners, significance, symbolism).
- **lore** — Core (category, summary, scope), Rules & Structure (rules, costs,
  hierarchy, exceptions), Context (history, public knowledge, secrets, impact,
  foreshadowing).
- **theme** — Thesis (statement, central question, argument), Exploration
  (positive/negative/contrary manifestations, symbols, dialogue hooks),
  Characters & Plot (protagonist/antagonist relation, subplots, arc integration).
- **other** — category, summary, details, references.

The `role` combo offers Protagonist / Antagonist / Mentor / Foil / Shadow /
Trickster / Guardian and more; `place.type`, `object.type`, and `lore.category`
have their own curated option lists.

---

## Relations

`PsykeRelation` links two entries and is stored **bidirectionally** (both A→B and
B→A). `relation_type` is usually empty (a generic association) but can be typed —
the type system is engine-aware:

- **Screenplay / general:** `supports_setup` ↔ `payoff`, `thematic_echo`,
  `visual_motif`, `subtext_opposition`.
- **Stage Script (theatrical):** `pressures`, `confronts`, `avoids`, `dominates` ↔
  `submits`, `deceives`, `overhears`, `interrupts`.

The Assistant follows relations one or two hops out when gathering context, and
the Graph renders typed relations as distinct edges (see [graph.md](graph.md)).

---

## Progressions & Temporal PSYKE

A `PsykeProgression` is a **state-change note anchored to a scene**. Progressions
are what let PSYKE answer the central continuity question: *what is the state of
this entry as of scene N?*

`temporal_psyke.TemporalGraph` builds an in-memory index from entries, relations,
progressions, and scene order. Its key query, `get_entry_state_at(entry_id,
scene_order)`, returns an `EntryState` reflecting the most recent progression at
or before that point in the story (falling back to the latest unanchored
progression). It also surfaces which related entries are "active" as of a scene
and an `inspect()` debug view.

Temporal state drives:

- the **entity hover** preview in the editor (state as of the current scene),
- the Assistant's PSYKE context block (current progression per relevant entry),
- the **Context Assistant**'s stale-progression and co-occurrence-gap hints
  (see [context_assistant.md](context_assistant.md)),
- the QUANTUM Outliner's PSYKE consistency scoring.

---

## Engine-specific memory layers

Beyond the flat detail fields, PSYKE stores **engine-specific memory** inside
nested sections of `details_json`. The active layer depends on the project's
narrative engine, and each is read/written through dedicated `Database` accessors.

### Visual Memory — Graphic Novel
`psyke_visual.py`, stored under `details_json["visual"]`. Tracks how things *look*
and how that look recurs: per-character silhouette, shape language, colour
identity, costume state, pose/gesture vocabulary, facial range, visual symbolism;
per-place architecture, lighting mood, palette, environmental motifs, recurring
camera angles, spatial continuity; per-object appearance/scale/continuity state;
per-theme visual manifestations, symbolic colours, recurring shapes, motif family.
It also computes motif recurrence, object reappearances, and visual callbacks
across pages/panels, and contributes a `[Visual Memory]` context block and review
checks (single-use motifs, missing visual identity, missing continuity states).

### Theatre Memory — Stage Script
`psyke_theatre.py`, stored under `details_json["theatre"]`. Tracks per-character
stage objective, spoken/subtext strategy, physical business, gesture vocabulary,
stage presence, relationship pressure, and offstage knowledge; per-set stage
layout, entrances/exits, levels, available props, audience visibility, spatial
constraints; per-prop status, owner, first appearance, use, continuity notes. It
builds a `[Theatre Memory]` block (who wants what, who pressures whom, who knows
what, which props matter, staging concerns).

### Series Memory — Series
`psyke_series.py`, stored under `details_json["series"]`. Tracks long-form
character arcs (season arc, episode state, long-term goals, unresolved conflicts,
per-episode status), relationship evolution beats, recurring lines/objects/motifs,
and callbacks. Combined with the `Season` / `Episode` / `SeriesArc` /
`EpisodePlotline` tables it derives mystery threads, unresolved threads, and
per-episode setup/payoff memory, and builds a `[Series Memory]` block (seasons,
current episode, active arcs, continuity risks).

---

## The PSYKE Console

The PSYKE Console (`ui/psyke_console.py`) is an omnibox: a single input that
accepts free-text search, natural-language phrases, and slash-commands, with a
live, debounced suggestion dropdown. It is the fastest way to navigate and mutate
the bible.

The pipeline behind it:

1. **Suggestions** (`psyke_suggestions.py`) blend intents, NL actions, slash
   commands, and entity matches — boosting entries that appear in the current
   scene.
2. **Intent detection** (`psyke_intents.py`) maps natural language to a structured
   `Intent` via fast regex rules: *"open scene 3"*, *"create character John"*,
   *"next scene"*, *"insert John"*, *"rewrite"*, *"delete John"*, *"rename John to
   Jean"*. When no rule matches, `psyke_intent_llm.py` can optionally ask a local
   LLM to classify the intent into the same action vocabulary (returning `null`
   when nothing fits, never raising).
3. **Search** (`psyke_search.py`) is a fuzzy, cached index over names and aliases
   with a clear scoring ladder (exact → starts-with → contains → fuzzy →
   word-initial), and a confidence threshold for single-best resolution.

### Commands

Commands are parsed (`psyke_commands.py`), resolved against a registry
(`psyke_command_registry.py`), validated (`psyke_command_validator.py`), and
dispatched to handlers (`psyke_system_commands.py`). Built-in commands include:

| Command | Effect |
|---------|--------|
| *(free text)* | Search the bible. |
| `/create <type> [name]` | Create an entry (type ∈ character/place/object/lore/theme/other). |
| `/open scene <id>` · `/open psyke <name>` | Navigate to a scene or entry. |
| `/go scene next\|previous\|<id>` | Move through scenes. |
| `/insert <name>` | Insert an entity reference at the cursor. |
| `/ai <action>` | Run a writing action (rewrite, expand, summarize, condense, dialogue, tension, pacing…). |
| `/delete <name>` · `/rename <old> to <new>` | Destructive — require a confirm step. |
| `/idea …` | Manage the [Controlling Idea](structure-and-plot.md#controlling-idea). |
| `/gn …` · `/series …` | Engine review reports (Graphic Novel / Series). |

Validation flags destructive commands (`delete`, `rename`) as **CONFIRM** before
they run, and all data mutations route through the **Connector**
(`connector_executor.execute_action`, with settings enforcement bypassed for
explicit console commands). Navigation is handled by UI callbacks rather than the
Connector.

---

## The PSYKE editor and in-manuscript integration

- **PSYKE view** (`ui/psyke_view.py`) — a two-pane Story Bible editor: a filtered,
  searchable list on the left; on the right the entry's basic fields, the dynamic
  detail schema (grouped by section), the Visual/Theatre/Series memory section when
  the engine calls for it, relations, progressions, and scene references.
- **Highlighter** (`ui/psyke_highlighter.py`) — colours entry names/aliases in the
  manuscript by type; **Ctrl+Click** jumps to the entry.
- **Entity hover** (`ui/entity_hover.py`) — a floating preview showing an entry's
  type, temporal state as of the current scene, and a notes excerpt.
- **Quick create** (`ui/psyke_quick_create.py`) — a lightweight dialog to add an
  entry from the scene editor (used by [Auto-Link](auto_link.md)).
- **Link preview & backlinks** (`ui/link_preview.py`) — renders `[[Entity]]`
  wiki-links and shows what references an entry.

Voice profiles (`VoiceProfile`, see [writing-analysis.md](writing-analysis.md))
can be synced onto a character's PSYKE entry, so the bible and the voice system
stay aligned.
