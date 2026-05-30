# Architecture

Logosforge is a **PySide6 (Qt 6) desktop application** with a **SQLite/SQLModel**
backend and an **OpenAI-compatible AI layer**. It is a single-process, local-first
program: there is no server, no account, and (by default) no network traffic
unless you point it at a cloud AI provider.

This document explains how the pieces fit together. For the data schema see
[data-model.md](data-model.md); for individual subsystems follow the links in the
[documentation index](README.md).

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.10+ |
| UI | PySide6 (Qt 6 widgets, `QPainter` for custom charts) |
| Persistence | SQLModel (SQLAlchemy + Pydantic) over SQLite |
| AI | OpenAI-compatible HTTP API (local or cloud); native Anthropic Messages API |
| Packaging | Source run via `run.py`; PyInstaller-aware path resolution |

The only hard third-party dependencies are `PySide6`, `sqlmodel`, and `certifi`
(plus `pyobjc-framework-Cocoa` on macOS). See `requirements.txt`.

By scale: ~190 Python modules and ~64k lines under `storyplanner/` and `plugins/`,
covered by ~185 test files under `tests/`.

---

## Startup sequence

The entry point is `run.py`, which calls `storyplanner.app.create_app()`:

```
run.py  →  storyplanner.app.create_app()  →  (QApplication, MainWindow)
```

`create_app()` (`storyplanner/app.py`) performs, in order:

1. **Branding** — sets the application name/display name to *Logosforge*
   (`_set_macos_app_name` patches `CFBundleName` on macOS) and loads the window
   icon from `assets/`.
2. **Theme** — reads the saved palette name from settings and applies the global
   Qt stylesheet (`storyplanner/ui/theme.py`).
3. **Database** — opens `storyplanner.db` (SQLite) in the working directory via
   `Database(DB_PATH)`. Schema is created and migrated on open (see below).
4. **Project bootstrap** — loads the first project, or creates a default
   *"My Story"* project if the database is empty.
5. **Plugins** — discovers external plugins, sets the app context (db + project),
   and loads the enabled ones (`storyplanner/plugin_manager.py`).
6. **Main window** — constructs `MainWindow(db, project.id)`.
7. **Session restore** — if a `last_project_path` (a saved `.json` project file)
   is remembered, it is quietly re-loaded.
8. **Initial view** — `show_initial_section()` always lands the user on the
   **Projects** view, regardless of session state.

On macOS a one-shot timer closes any stray blank `NSWindow` Python may spawn
before Qt takes over.

---

## Module map

The codebase is organized by responsibility rather than strict layers, but it
falls naturally into the following groups.

### Domain & persistence
| Module | Role |
|--------|------|
| `storyplanner/models/` | SQLModel table definitions (`models.py`) and PSYKE detail schemas (`psyke_details.py`). |
| `storyplanner/db/database.py` | The `Database` facade — a single ~3,000-line class wrapping every query. All data access goes through it. |
| `storyplanner/export.py`, `import_data.py` | Project serialization to/from JSON and craft formats (DOCX, PDF, Fountain, FDX, HTML, Markdown, CSV). |
| `storyplanner/autosave.py`, `cloud_storage.py`, `version_manager.py`, `recent_projects.py` | Project-file lifecycle: debounced atomic saves, cloud-safe locking, snapshots, MRU list. |
| `storyplanner/project_compat.py`, `project_lifecycle.py`, `project_events.py` | Engine/format compatibility shims, per-project cache clearing, and the in-process event bus. |

### Narrative reasoning
| Module | Role |
|--------|------|
| `storyplanner/narrative_engines/` | The five **Narrative Engines** — frozen-dataclass profiles describing *how* a story is reasoned about. See [narrative-engines.md](narrative-engines.md). |
| `storyplanner/writing_formats.py` | The five **Writing Formats** — block/typography profiles describing *how* the manuscript renders and exports. See [writing-formats.md](writing-formats.md). |
| `storyplanner/controlling_idea.py` | McKee-style thematic spine. |
| `storyplanner/quantum_outliner/` | The **QUANTUM Outliner** — branch generation, scoring, collapse. See [quantum-outliner.md](quantum-outliner.md). |

### Story Bible (PSYKE)
`storyplanner/temporal_psyke.py`, `psyke_visual.py`, `psyke_series.py`,
`psyke_theatre.py`, `psyke_search.py`, `psyke_suggestions.py`, `psyke_intents.py`,
`psyke_intent_llm.py`, `psyke_commands.py`, `psyke_command_registry.py`,
`psyke_command_validator.py`, `psyke_system_commands.py` — the knowledge base and
its natural-language console. See [psyke.md](psyke.md).

### AI assistant
`storyplanner/assistant.py` (provider transport), `context_builder.py` (the
layered prompt pipeline), `orchestration.py`, `adaptive_mode.py`,
`mode_suggestions.py`, `counterpart.py`, `chat_memory.py`, `chat_context.py`,
`memory_manager.py`, `memory_context.py`, `story_memory.py`, `irrational.py`,
`connector_registry.py`, `connector_executor.py`, `connector_actions.py`,
`providers.py`. See [ai-assistant.md](ai-assistant.md).

### Craft analysis (deterministic)
`storyplanner/style_analysis.py`, `voice_consistency.py`, `voice_learner.py`,
`grammar_checker.py`, `paragraph_energy.py`, `dialogue_attribution.py`,
`pacing_insights.py`, `character_balance.py`, `story_health.py`,
`structural_intelligence.py`, `narrative_dashboard.py`, `analytics.py`,
`auto_link.py`, `context_assistant.py`. See [writing-analysis.md](writing-analysis.md).

### Graph
`storyplanner/graph_analysis.py`, `graph_flow.py`, `graph_gravity.py`,
`graph_meaning.py`, `graph_suggestions.py` and the large
`storyplanner/ui/focus_graph_view.py`. See [graph.md](graph.md).

### Engine-specific structure tools
`storyplanner/stages.py` (narrative versioning/branching),
`outline_templates.py`, `outline_actions.py`,
`graphic_novel_plot.py` / `graphic_novel_review.py` / `graphic_novel_manuscript.py` / `graphic_novel_ai_export.py`,
`stage_script_plot.py` / `stage_script_review.py`,
`series_plot.py` / `series_review.py`. See [structure-and-plot.md](structure-and-plot.md).

### UI
`storyplanner/ui/` — ~55 PySide6 views and dialogs. `main_window.py` is the shell
(sidebar navigation, menu bar, view registry); `writing_core_view.py` is the
manuscript editor. See [user-guide.md](user-guide.md).

### Plugins
`storyplanner/plugin_base.py`, `plugin_manager.py`, `plugin_executor.py`,
`plugin_registry.py`, the in-app analysis plugins under `storyplanner/plugins/`,
and the external plugin folder `plugins/`. See [plugins.md](plugins.md).

---

## Design patterns

Several patterns recur throughout the codebase and are worth knowing before
reading any single module.

### The `Database` facade
Every view, engine, and analyzer receives a `Database` instance and a
`project_id`. The `Database` class opens a short-lived SQLAlchemy session per
call, so it is effectively stateless and safe to call from background threads.
There is no ORM object graph leaking across the app — methods return SQLModel
rows or plain dicts.

### Frozen-dataclass profiles
Both **Narrative Engines** and **Writing Formats** are immutable
`@dataclass(frozen=True)` singletons held in module-level registries
(`narrative_engines.ALL_ENGINES`, `writing_formats.ALL_FORMATS`). They carry no
behavior beyond formatting helpers, which makes the two axes —
*reasoning* vs *rendering* — independently composable.

### JSON-in-column flexible schema
Rich, type-specific data is stored as JSON text inside a single column rather
than spread across many tables: `Project.settings_json`, `PsykeEntry.details_json`
(with nested `["visual"]`, `["theatre"]`, `["series"]` sections),
`Scene`-level metadata, `QuantumStateRecord.state_json`,
`Stage.metadata_json`, and `ChatMessage.metadata_json`. This lets the schema
evolve without migrations for most features.

### Schema creation & non-destructive migration
On open, `Database` calls `SQLModel.metadata.create_all()` (new tables appear
automatically) and then a hand-written `_migrate()` step that `ALTER TABLE`s in
any new columns on pre-existing databases. Older project files therefore gain new
engine fields and tables without data loss and without a migration framework.

### Event bus
`storyplanner/project_events.py` exposes a process-global `ProjectEventBus`
(`QObject`) with granular signals — `scene_changed`, `psyke_changed`,
`notes_changed`, `plot_changed`, `outline_changed`, `project_loaded`,
`project_created`, `assistant_action_completed`, and a catch-all
`project_data_changed`. Views subscribe and refresh in place instead of polling.
Writes (including AI connector actions) emit the appropriate signal so the whole
UI stays consistent.

### Propose-then-confirm AI
The AI never silently mutates the project. Generative output is shown for the
writer to **Accept / Insert / Discard**, and structured write actions flow through
the **Connector** (`connector_executor.py`), which is gated by settings, validated
against a parameter schema, restricted to a non-destructive allow-list, and
applied only on an explicit click. The same principle governs Auto-Link, the
Context Assistant, and Quantum collapse.

### Deterministic core, optional LLM refinement
The craft analyzers (style, voice, energy, grammar, structural intelligence,
dashboard) are pure, deterministic, and run with **no network calls**. Several can
*optionally* blend in an LLM score on a background thread, but they always produce
a useful result offline. The whole app degrades gracefully when no AI provider is
configured.

### Background threads for AI
All LLM requests run on `QThread` workers (e.g. `_AssistantWorker`, `_ChatWorker`,
`StyleRefineWorker`, `EnergyRefineWorker`) and deliver results back to the UI via
signals, so the interface never blocks on the network.

---

## Configuration & data locations

| Location | Contents |
|----------|----------|
| `./storyplanner.db` | The working SQLite database (created in the launch directory). |
| `~/.storyplanner/settings.json` | App settings — theme, AI provider, panel toggles, connector flags, ignored suggestions. |
| `~/.storyplanner/versions/<project_id>/` | Timestamped JSON version snapshots (max 50 retained). |
| `~/.storyplanner/recent_projects.json` | Most-recently-used project files. |
| `~/.storyplanner/quantum/archive_<pid>.json` | Archived (collapsed) Quantum wavefunctions. |
| `*.json` | Portable project files (export/save) — full project serialized as JSON. |
| `*.json.logosforge.lock` | Cloud-safety lock sidecar written next to an open project file. |
| `*_conflict_<device>_<ts>.json` | Conflict copies written when an external change is detected. |

See [configuration.md](configuration.md) for the full settings reference and
[data-model.md](data-model.md) for the project-file format and cloud safety model.

---

## Two orthogonal axes: Engine vs Format

The single most important architectural idea in Logosforge is the deliberate
separation of two concerns that other tools conflate:

- A **Narrative Engine** encodes *how the story is reasoned about* — structural
  vocabulary (chapter/scene vs page/panel vs episode), what the Plot/Timeline/Graph
  default to, assistant priorities, PSYKE context rules, and review checks.
- A **Writing Format** encodes *how the manuscript renders and exports* — the block
  element types (action, dialogue, caption, SFX…) and their typography.

The two layers never reference each other's internals. A Screenplay engine can be
paired with a treatment-style rendering; a Novel engine can drive an outline view.
Each project stores both `narrative_engine` and `default_writing_format`, with a
legacy `format_mode` field resolved for backward compatibility by
`project_compat.py`. This orthogonality is what lets one app serve novelists,
screenwriters, playwrights, comics writers, and showrunners without forking the
codebase.
