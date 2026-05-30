# The Narrative Graph

The **Graph** is Logosforge's interactive map of the story: characters, scenes,
places, PSYKE entries, motifs, pages/panels, episodes, and the many relationships
between them. It is not a single fixed diagram but a set of **lenses** — focused,
filterable views that answer specific structural questions, each adapted to the
project's [narrative engine](narrative-engines.md).

> Source: `storyplanner/ui/focus_graph_view.py` (the main view),
> `graph_analysis.py`, `graph_flow.py`, `graph_gravity.py`, `graph_meaning.py`,
> `graph_suggestions.py`, and the simpler `ui/graph_view.py`.

---

## Nodes and edges

The graph models the project as a typed node/edge set (`GraphNode` / `GraphEdge`).
Node kinds span every engine: **character, place, scene, object, act, theme, lore,
note, other**; **wavefunction / branch** (Quantum); **page / panel / motif**
(Graphic Novel); **cue / offstage** (Stage Script); **season / episode / arc /
mystery / plotline** (Series). Each kind has its own colour and shape.

Edges are equally rich and typed — participation, containment, mention,
generic link, and PSYKE relation, plus engine-specific edges such as causality,
setup→payoff, knowledge state, subtext opposition, and visual motif (Screenplay);
page-flow, panel causality, symbol echo, object continuity, character-present
(Graphic Novel); pressure, entrance/exit, prop use, blocking, cue, offstage
(Stage Script); contains, continues, sets-up/pays-off/resolves/delays/escalates,
echoes, contradicts (Series); and wavefunction→branch (Quantum). Edge colour,
width, and dash style encode the relationship type.

---

## Lenses (modes)

Rather than show everything at once, the Graph offers many **lenses**, each a
profile that selects which node kinds and edge types to show and which layout to
use. The default is **Structure-first** (acts and scenes as a linear timeline).
Representative lenses:

- **General:** All, Structure, Relationship, Theme, Meaning, PSYKE, Quantum.
- **Screenplay:** Causality, Setup/Payoff, Knowledge, Subtext, Visual Motifs,
  Continuity.
- **Graphic Novel:** Visual Motif, Panel Causality, Symbol Recurrence, Page Rhythm,
  Object Continuity, Character Appearance.
- **Stage Script:** Character Pressure, Entrance/Exit, Prop Continuity, Blocking/
  Spatial, Subtext Conflict, Offstage Knowledge.
- **Series:** Season Arc, Episode Dependency, A/B/C Plot, Mystery Payoff, Character
  Progression, Relationship Evolution, Continuity Risk.

A **layers panel** toggles visibility of the core node groups (character, place,
object, theme, lore, scene, act, note, other), with character/theme/act treated as
the always-emphasized skeleton. Other controls include text search, zoom, a
temporal slider (filter by scene-order range), and neighbourhood isolation
(N-hop focus around a node). The current lens, visible layers, zoom, search, and
focus are persisted in the `graph_state` setting, and named filter sets in
`graph_presets`.

---

## Story Gravity

> Source: `storyplanner/graph_gravity.py`.

**Story Gravity** weights each node by narrative importance, blending three
components — **narrative** (scene participation, connectivity, entity density),
**thematic** (theme alignment, Controlling-Idea resonance), and **structural**
(position in the arc: opening / first quarter / midpoint / climax, and plot
anchoring). The composite gravity drives the visualization: heavier nodes are
larger, gain a glow halo past a threshold, and are pulled toward the centre of
circular layouts — so the protagonists and load-bearing scenes literally stand out.

---

## Meaning, Flow, and analysis

- **Meaning** (`graph_meaning.py`) overlays semantic annotations: per-node
  importance, an emotional **state warmth** (cool / warm / hot, from the character's
  current state words), "dead zones" (isolated nodes with ≤1 connection),
  "psyke glow" hubs (≥3 connections), and arc grouping by plotline.
- **Flow** (`graph_flow.py`) computes ordered narrative progression through scenes
  — Timeline, Acts, Arc (reshaped into a Freytag curve), or Causal (only links
  where one scene references another). Segments are colour-banded
  beginning / middle / ending.
- **Analysis** (`graph_analysis.py`) provides per-node analysis (adjacent themes,
  relations, scenes, arcs, and Controlling-Idea alignment) and global insights
  (structural overview, disconnected nodes, weak thematic clusters, suggested
  missing relations). It also composes the `[Graph]` context block the
  [AI Assistant](ai-assistant.md) consumes.
- **Suggestions** (`graph_suggestions.py`) turns graph structure into concrete,
  deterministic narrative ideas — Escalation, Reversal, Expansion, Internal Shift —
  each tied to the nodes that justify it so they can be highlighted in the view.

Together, the Graph is both a navigational map and an analytical instrument: it
shows you the shape of the story and where it is thin, isolated, or unbalanced.
