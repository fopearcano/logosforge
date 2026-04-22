# Logosforge

**A narrative operating system for structured writing.**

Logosforge helps you plan, write, and evolve your story with AI — without losing control.

---

## Overview

Most writing tools split the workflow:

- Editors let you write, but not structure
- Planners organize, but don't help you write
- AI tools generate text, but ignore narrative intent

**Logosforge unifies writing, structure, and AI in a single system.**

It is a PySide6 desktop application with a SQLite backend, designed for novelists, screenwriters, and narrative designers who want deep structural awareness alongside their prose.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| UI Framework | PySide6 (Qt 6) |
| ORM / Database | SQLModel + SQLite |
| AI Integration | OpenAI-compatible API (local or cloud) |
| Architecture | MVC with layered context engines |

**Codebase:** ~27,300 lines of source across 95 modules, with 1,094 tests (~12,400 lines of test code).

---

## Installation & Run

### Requirements

- Python 3.10+
- pip

### Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 run.py
```

### Windows

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

### Run Tests

```bash
python -m pytest tests/ -v
```

---

## Features

### Writing & Editing

#### Structured Writing
- Scene-based writing workflow with automatic ordering
- Characters, places, and notes management
- Scene metadata: goal, conflict, outcome, synopsis, summary
- Acts, chapters, plotlines, beats, and tags per scene

#### Focus Mode
- Distraction-free writing with centered text
- Enlarged canvas, minimal UI
- Toggle per session

#### Manuscript View
- Continuous prose view across all scenes
- Serif/sans-serif toggle
- Word count tracking
- Auto-save with debounce
- Format toolbar: bold, italic, underline, headings, alignment, lists, blockquote
- Typewriter mode (current line pinned to vertical center)
- Per-scene auto-save indicator

#### PSYKE-Aware Semantic Editor
The manuscript editor doubles as a semantic surface linked to the Story Bible.

- Inline highlighting of PSYKE entries (characters, themes, places) as you type
- Hover tooltip shows the entry's current temporal state
- Ctrl+Click on a highlighted entity jumps to the PSYKE view and selects it
- Highlight palette differentiates entry types (character / theme / location / lore)
- Live refresh as new entries or aliases are added

#### Auto-Link (Manuscript ↔ PSYKE)
Bidirectional suggestion layer between your prose and your Story Bible.

- Detects recurring capitalized entities and offers to create PSYKE entries
- Learns aliases for existing entries (e.g. "El Capitán" → Captain)
- Proposes relations when two known entities co-occur in a scene
- Extracts progression/memory candidates from state-verb sentences ("Alice realized…")
- Non-intrusive inline banner with Accept / Dismiss / Ignore actions
- **Suggest, never auto-commit** — the user is always in control
- Persistent ignore list (remembered across sessions)
- Rate-limited: one suggestion per scene at a time, debounced after edits

#### Export & Import
- **Export formats:** JSON, Markdown, CSV, DOCX, Fountain (screenwriting), PDF, Final Draft XML (`.fdx`), HTML
- **Import:** JSON (full project restore)

---

### Narrative Structure

#### Timeline
- Visual scene ordering with drag-and-drop reordering
- Act/chapter grouping

#### Story Grid
- Matrix view of scenes vs. characters
- Presence tracking at a glance

#### Multi-Plot View
- Plotline-based scene organization
- Arc tracking across parallel threads

#### Outline Views
- **Outline** — Full metadata reference (acts, beats, characters, GCO)
- **Writer Outline** — Clean synopsis-only view for writing
- **Structure** — Scenes organized by narrative beat (Save the Cat order)

#### Act & Beat Analysis
- Scene distribution across acts
- Beat assignment and structural gaps

---

### Story Bible (PSYKE)

A persistent knowledge base for worldbuilding, characters, rules, and lore.

#### Entries
- Named entries with type classification (character, location, lore, rule, etc.)
- Aliases for cross-referencing
- Structured details (key-value fields)
- Notes and free-form content

#### Temporal Progressions
- Entries evolve over time — each progression is anchored to a scene
- The system resolves the correct state at any narrative position
- Temporal queries: "What did this character know at scene 12?"

#### Relations
- Entries link to other entries (bidirectional)
- Related entries surface automatically in context

#### AI Integration
- PSYKE entries inject into AI prompts automatically
- Mode-aware orchestration: different actions (rewrite, expand, dialogue) get different PSYKE subsets
- Inline highlighting of PSYKE references in scene text

---

### AI Assistant System

#### Assistant Panel
- Global side panel accessible from any view
- Scene selector with context-aware prompt building
- Preset actions: Rewrite, Expand, Dialogue, Summarize, Tension, Pacing, Next Beat, Alternatives
- Custom free-form prompts
- Apply results: Replace, Insert, Append, As Synopsis, As Summary
- Provider settings: supports any OpenAI-compatible endpoint (LM Studio, Ollama, OpenAI, Anthropic)
- Response caching with TTL

#### Inline AI Editing
- Selection-based actions in the scene editor
- Rewrite, Expand, Dialogue, Tighten, Tension
- Diff view (original vs. proposed)
- Accept/reject workflow
- Slash commands: `/rewrite`, `/expand`, `/dialogue`, `/tension`, `/tighten`

#### COUNTERPART Mode
A dialogic narrative assistant — a reflective, critical second mind for the writer.

- **Not** an authoring tool — it critiques, questions, and interprets
- Modes: Feedback, Critique, Interpret, Ask Back, Compare
- Never produces replacement prose
- Never mutates content
- Segmented mode selector (Assistant | Counterpart) in the panel

#### Adaptive AI Mode Engine
Automatically adjusts AI behavior based on story state:

- **Story stage detection**: Early / Mid / Late (based on scene count and structure)
- **Health state**: Balanced / Uneven / Fragmented
- **Mode selection**: Structure / Balance / Refinement
- Mode-specific suggestions (what's missing, what's uneven, what's improvable)
- User override via mode strip widget

#### Context Pipeline
Every AI request assembles rich context from:
- Active scene (content, metadata, characters)
- Story outline (condensed scene list)
- Story memory (scored, scene-relevant entries)
- PSYKE / Story Bible (temporal-aware, mode-orchestrated)
- Graph context (character relationships, node importance)
- Structural intelligence (narrative weakness detection)
- Adaptive mode guidance
- IRRATIONAL fragments (when activated)

#### Proactive Context-Aware Assistant
A lightweight heuristic engine that detects what you're writing and surfaces non-intrusive hints in real time.

- **Writing mode detection** — identifies dialogue-heavy, descriptive, or short/long scenes
- **Structural hints** — flags missing metadata (no conflict, no beat assignment, empty synopsis)
- **PSYKE temporal hints** — detects stale character progressions and co-occurrence gaps
- Rate-limited: per-type cooldown (60s), global cooldown (15s), deduplication
- Resets on scene change
- Dismiss / Ignore / Apply actions per hint
- Non-intrusive inline banner (never blocks writing)

#### Structural Intelligence (PSYKE-Driven)
Analyzes narrative structure using PSYKE data, scenes, and outline to detect weaknesses across 7 detectors:

- **Act Balance** — flags acts with disproportionately low word count
- **Arc Completion** — detects character arcs that start but never progress
- **Climax Preparation** — checks whether late-story tension builds adequately
- **Tension Curve** — identifies flat or declining tension trends
- **Theme Continuity** — flags themes that disappear for extended stretches
- **Character Presence** — detects characters missing from long spans of the story
- **Beat Placement** — checks Save-the-Cat beats against expected position ranges

Results surface in the Review overlay and feed into the AI context pipeline. Cached with 30s TTL and dirty-flag invalidation.

#### IRRATIONAL Mode
A PSYKE rule-disruption engine that breaks narrative causality on demand.

Activated via **"Go Irrational"** toggle in the Assistant panel. Generates surreal provocations from your Story Bible:

- **Temporal Displacement** — pulls character progressions out of timeline order
- **Entity Blend** — merges unrelated PSYKE entries using surreal templates
- **Arc Inversion** — inverts character or theme arcs
- **Temporal Echo** — cross-references scenes in dreamlike ways
- **Reality Rupture** — breaks world rules using places, lore, and themes

Deterministic (same scene = same output via seeded RNG). Re-rollable. Read-only — never writes to the database. Injected into the AI prompt as an `[IRRATIONAL MODE]` block that instructs the assistant to weave the fragments into its response.

---

### Story Memory

#### Extraction
Automatically extracts continuity-relevant facts from scene structured fields:
- **Character state** — from scene character states
- **Key events** — from scene outcomes
- **Relationships** — from scene conflicts (when 2+ characters present)
- **Decisions** — from scene goals (when outcome exists)

#### Management
- Priority scoring: key events/decisions = high, relationships/states = medium
- Recency-based decay (recent memories stay relevant longer)
- Superseding: older character states demoted when newer ones exist
- Context limit: top 20 entries surface in AI prompts

#### Memory-Aware Context
- Scene-relevant selection with proximity boost (adjacent scenes)
- Character overlap boost (shared characters in active scene)
- Compact format with scene labels: `(S3)`
- Combines with global story memory (themes, motifs, arc)

---

### Analysis & Insights

#### Narrative Dashboard
Visual story intelligence at a glance. Four synchronized panels computed from scenes and PSYKE:

- **Tension Curve** — per-scene score from character count, relation density, conflict keywords, and progression activity. Filled-area polyline with hover breakdown and click-to-open-scene. Flags flat sections, spikes, and weak first-third buildup.
- **Character Presence** — horizontal strip per character with dots marking scenes where they appear. Click a name to toggle visibility. Flags over-dominance (>80% of scenes) and long absences (≥3 consecutive scenes).
- **Act / Structure Distribution** — segmented bar showing word-count weight per act. Uses `scene.act` labels when present, otherwise infers a 25 / 50 / 25 three-act split. Flags weak sections and weak middles.
- **Theme Continuity** — bar-style presence map per theme. Flags underused themes (<20% of scenes) and multi-scene disappearances.

Dashboard is read-only, deterministic (no AI call), computed in a single pass, and lives in its own sidebar view so it stays non-intrusive.

#### Story Health
Four structural health signals with percentage indicators:
- Connectivity, completeness, balance, depth

#### Character Balance
- Per-character presence ratio
- Flags: dominant, underused
- Per-arc span and thin-arc detection

#### Pacing Insights
Five rhythm detectors:
- **Disappearance** — character gaps > 40%
- **Monotony** — 4+ consecutive same-type scenes
- **Stagnation** — low diversity in middle third
- **Arc neglect** — underrepresented plotlines
- **Clustering** — presence compressed into narrow span

Max 5 insights, sorted by severity.

#### Graph Analysis
- Character/scene relationship graph
- Node importance (connections, PSYKE influence)
- Dead zone detection
- Graph-driven narrative suggestions

#### Story Flow
- Tension curves inferred from beat type + conflict + content
- Pacing analysis (action vs. reflection rhythm)

#### Creative Layer
- Context hints (missing conflict, absent characters)
- Paragraph rhythm variation

---

### CONNECTOR — Local AI Control Bridge

A structured action API for local AI models to interact with Logosforge programmatically.

#### Supported Actions (14)

**Read (10):**
- `get_project`, `list_scenes`, `get_scene`, `list_characters`
- `list_psyke_entries`, `get_psyke_entry`, `list_notes`, `get_note`
- `search`, `list_available_actions`

**Write (4, non-destructive):**
- `create_scene`, `update_scene_title`, `create_psyke_entry`, `create_note`

#### Safety
- All inputs validated by type and schema
- No deletes, no content overwrites, no raw DB access
- Cross-project access blocked
- Structured responses: `{"ok": true, "result": ...}` or `{"ok": false, "error": "..."}`

---

### Plugin System (PSYKE-Aware)

Plugins operate on structured narrative context, never on raw database access.

#### Architecture
- `LogosforgePlugin` base class with `execute(PluginContext) -> PluginResult`
- `PluginContext` — immutable snapshot from all context engines (scenes, characters, PSYKE, memory, graph)
- `PluginResult` — structured suggestions with category, severity, target
- Registry with dynamic loading

#### Built-in Plugins
- **Dialogue Tension** — analyzes dialogue density, tension signals, rhythm uniformity, silent characters
- **Character Presence** — tracks distribution gaps, clustering, disappearances, balance

#### McKee Craft Knowledge (External Plugin)
An optional writing-intelligence plugin based on Robert McKee's three craft domains: story structure, character, and dialogue.

Three canonical JSON knowledge systems with 57 operational methods, 40 triggers, 17 diagnostic checks, and 25 cross-method conflict resolution rules. Designed as a runtime decision engine — methods act as constraints on generation, not templates to quote.

**[Download McKee Plugin](https://drive.google.com/drive/folders/1t5j4dFIW82U-MT81vBiQDQTfCyIMQMZV?usp=sharing)**

#### Safety
- Plugins never see the database
- Plugins cannot mutate state
- Crashed plugins return structured error results

---

### Narrative Suggestions

#### Beat Suggestions
- Context-aware narrative direction proposals
- Built from PSYKE temporal state + scene context
- Structured output (not prose)

#### Graph Suggestions
- Structural suggestions from relationship graph
- Deterministic (no AI call needed)

#### Mode Suggestions
- Structure mode: what's missing from the skeleton
- Balance mode: what's uneven in distribution
- Refinement mode: what could be better in existing content

---

### UI & Appearance

#### Themes
- Dark mode (default)
- Light Green
- Light Warm

#### Sidebar Navigation
Projects, Dashboard, Characters, Places, Notes, Scenes, Manuscript, Timeline, Grid, Plot, Outline, Writer, Structure, Acts, Beats, Tags, Graph, Arcs, Health, Balance, Pacing, Adapt, Narrative, Search, PSYKE, Plugins, Assistant

#### Overlay Mode
- Assistant panel can float as overlay
- Contextual dimming during typing

---

## Architecture

```
storyplanner/
├── app.py                    # Application factory
├── db/                       # SQLModel database layer
│   └── database.py           # All CRUD operations
├── models/                   # SQLModel data models
│   └── models.py             # Project, Scene, Character, Place, Note, PSYKE, Memory
├── ui/                       # PySide6 views and widgets (46 files)
│   ├── main_window.py            # Main window with sidebar navigation
│   ├── assistant_view.py         # AI assistant panel
│   ├── inline_assistant.py       # Inline scene editor AI
│   ├── writing_core_view.py      # Manuscript/focus mode editor
│   ├── format_toolbar.py         # Rich-text formatting toolbar
│   ├── manuscript_highlighter.py # Base manuscript syntax highlighting
│   ├── psyke_highlighter.py      # PSYKE entity highlighting in prose
│   ├── entity_hover.py           # Hover tooltip for PSYKE entities
│   ├── link_preview.py           # Ctrl+Click link preview widget
│   ├── suggestion_banner.py      # Auto-link suggestion banner
│   ├── context_hint_banner.py    # Context-aware assistant hint banner
│   ├── psyke_quick_create.py     # Quick-create dialog for new PSYKE entries
│   ├── narrative_dashboard_view.py # Narrative Dashboard top-level view
│   ├── dashboard_widgets.py      # Tension curve, presence, structure, theme panels
│   └── ...                       # 32 more view/widget files
├── assistant.py              # AI prompt construction and API client
├── counterpart.py            # COUNTERPART dialogic assistant
├── context_builder.py        # Context gathering from all systems
├── memory_context.py         # Scene-relevant memory selection
├── memory_manager.py         # Priority, decay, superseding
├── story_memory.py           # Memory extraction from scenes
├── temporal_psyke.py         # Time-aware story bible resolution
├── orchestration.py          # Mode-aware PSYKE context composition
├── narrative_dashboard.py    # Tension, presence, structure, theme computations
├── auto_link.py              # Manuscript ↔ PSYKE suggestion engine
├── narrative_suggestions.py  # Beat suggestion engine
├── graph_meaning.py          # Graph-based narrative metrics
├── graph_suggestions.py      # Graph-driven direction suggestions
├── pacing_insights.py        # Rhythm and pacing detectors
├── adaptive_mode.py          # AI mode engine (Structure/Balance/Refinement)
├── mode_suggestions.py       # Mode-specific suggestion generators
├── character_balance.py      # Character/arc distribution analysis
├── story_health.py           # Structural health indicators
├── story_flow.py             # Tension and pacing curves
├── creative_layer.py         # Context hints and rhythm analysis
├── context_assistant.py      # Proactive heuristic hint engine (3 detection layers)
├── structural_intelligence.py # PSYKE-driven structural analysis (7 detectors)
├── irrational.py             # IRRATIONAL mode — surreal PSYKE rule-disruption
├── analytics.py              # Writing metrics (word count, dialogue ratio)
├── connector_registry.py     # CONNECTOR action registry
├── connector_actions.py      # CONNECTOR action definitions + handlers
├── connector_executor.py     # CONNECTOR validation and dispatch
├── plugin_base.py            # Plugin interfaces (base class, context, result)
├── plugin_registry.py        # Plugin registration and lookup
├── plugin_executor.py        # Plugin context building and execution
├── plugin_manager.py         # Dynamic plugin loading
├── plugins/                  # Built-in plugins
│   ├── dialogue_tension.py   # Dialogue analysis plugin
│   └── character_presence.py # Character distribution plugin
├── providers.py              # LLM provider configuration
├── prompt_router.py          # Keyword-based prompt routing
├── export.py                 # Multi-format export
├── import_data.py            # JSON project import
├── preferences.py            # User preference persistence
├── settings.py               # Settings manager
└── recent_projects.py        # Recent project tracking
```

---

## AI Provider Configuration

Logosforge works with any OpenAI-compatible API endpoint:

| Provider | Base URL | Notes |
|----------|----------|-------|
| LM Studio | `http://localhost:1234/v1` | Default, local |
| Ollama | `http://localhost:11434/v1` | Local |
| OpenAI | `https://api.openai.com/v1` | Requires API key |
| Anthropic | Via proxy or compatible endpoint | Requires API key |

Configure in the Assistant panel under Settings.

---

## Design Principles

1. **Structure over generation** — The system helps you organize and think, not write for you
2. **Context-aware AI** — Every AI interaction understands your story's full context
3. **Non-destructive** — Templates scaffold, memory informs, analysis suggests — nothing overwrites without consent
4. **Deterministic analysis** — Pacing, health, balance, structural intelligence, and suggestions compute without AI calls
5. **Temporal awareness** — Story bible entries evolve over narrative time
6. **Plugin safety** — Plugins see snapshots, never databases; they suggest, never mutate
7. **Suggest, never auto-commit** — Auto-link proposes; the user always decides before PSYKE is touched
8. **Local-first** — Works offline with local models, no cloud dependency required
9. **Proactive, not intrusive** — Context hints and structural warnings surface automatically but never block writing
10. **Opt-in disruption** — IRRATIONAL mode breaks rules only when the writer explicitly activates it

---

## Further Reading

- [`docs/narrative_dashboard.md`](docs/narrative_dashboard.md) — panels, scoring formulas, flag rules
- [`docs/auto_link.md`](docs/auto_link.md) — detection rules, suggestion flow, safety guarantees
- [`docs/plugins.md`](docs/plugins.md) — writing and registering plugins
- [`docs/structural_intelligence.md`](docs/structural_intelligence.md) — 7 detectors, heuristic rules, data flow
- [`docs/irrational_mode.md`](docs/irrational_mode.md) — fragment generators, seeding, AI integration
- [`docs/context_assistant.md`](docs/context_assistant.md) — detection layers, rate limiting, hint types

---

## License

See repository for license information.
