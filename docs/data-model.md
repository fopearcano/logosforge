# Data Model & Persistence

Logosforge stores everything in a local **SQLite** database through **SQLModel**
(SQLAlchemy + Pydantic). Each project is a self-contained set of rows keyed by
`project_id`; portable project files are JSON serializations of that data. There is
no server and no account.

> Source: `storyplanner/models/models.py` (tables), `storyplanner/db/database.py`
> (the `Database` facade), and the persistence helpers `autosave.py`,
> `cloud_storage.py`, `version_manager.py`, `recent_projects.py`,
> `project_events.py`, `project_lifecycle.py`, `project_compat.py`.

---

## Storage at a glance

| What | Where |
|------|-------|
| Working database | `./storyplanner.db` (SQLite, created in the launch directory) |
| Portable project file | A `*.json` file you Save / Open |
| App settings | `~/.storyplanner/settings.json` |
| User preferences | `~/.storyplanner/preferences.json` |
| Version snapshots | `~/.storyplanner/versions/<project_id>/*.json` (max 50) |
| Recent projects | `~/.storyplanner/recent_projects.json` |
| Quantum archive | `~/.storyplanner/quantum/archive_<project_id>.json` |
| Lock sidecar | `<project>.json.logosforge.lock` |
| Conflict copy | `<project>_conflict_<device>_<timestamp>.json` |

---

## The `Database` facade

`Database` (in `db/database.py`) is a single class wrapping every query. It is
constructed with a path (`Database("storyplanner.db")`) or with no path for an
in-memory database (used by the test suite). On open it:

1. creates any missing tables via `SQLModel.metadata.create_all()`, then
2. runs `_migrate()`, a hand-written step that `ALTER TABLE`s in new columns on
   pre-existing databases (e.g. the screenplay/stage Scene fields, the typed
   `PsykeRelation.relation_type`, `Project.narrative_engine`,
   `GraphicNovelPage.issue_id`).

The result is **non-destructive migration**: older project files gain new tables
and columns without a migration framework and without data loss. Each method opens
a short-lived session, so the facade is effectively stateless and safe to call from
background threads. Methods are grouped by domain — projects, characters/voice,
places, notes, scenes, PSYKE (entries/relations/progressions/visual-theatre-series
memory), outline, stages/snapshots/branches, graphic-novel (issues/sequences/pages/
panels/continuity), stage-script (entrances/cues/business), series (seasons/
episodes/arcs/plotlines), chat, quantum state, decision log, search/links, and
story memory.

---

## The schema

All tables are project-scoped via `project_id` (directly or through a parent row).

### Core
- **Project** — `title`, `description`, `format_mode` (legacy), `narrative_engine`,
  `default_writing_format`, `settings_json`, timestamps.
- **Character**, **Place** — name, description (+ character colour).
- **Note** (+ **NotePsykeLink**, **NoteSceneLink**) — title, content, tags, pinned,
  many-to-many links to PSYKE entries and scenes.
- **Scene** — the richest table: title, summary, synopsis, goal, conflict, outcome,
  beat, tags, act, chapter, plotline, colour, content, sort order — plus optional,
  default-safe **screenplay** fields (slugline, location, INT/EXT, time of day,
  duration, visual objective, dramatic turn, blocking/subtext notes, setup/payoff
  links, montage group, cinematic pacing, continuity) and PSYKE cinematic
  extensions (visible/hidden conflict, emotional turn, who-knows-what, physical
  action, visual symbolism), and **stage-script** fields (stage location, set
  description, scene objective, entrance/exit & prop & cue notes, offstage events,
  audience visibility, performance duration).
- **SceneCharacterLink**, **ScenePlaceLink**, **SceneCharacterState** — scene
  membership and per-scene character state.

### PSYKE
- **PsykeEntry** — `name`, `entry_type`, `aliases`, `notes`, `details_json`,
  `is_global`. (`details_json` also holds nested `["visual"]` / `["theatre"]` /
  `["series"]` engine-memory sections.)
- **PsykeRelation** — bidirectional, with an optional typed `relation_type`.
- **PsykeProgression** — a state-change note anchored to a scene.

See [psyke.md](psyke.md).

### Structure, voice, memory, chat, quantum
- **OutlineNode** — hierarchical outline tree (`parent_id`, `sort_order`).
- **VoiceProfile** — per-character tone / sentence length / vocabulary / quirks /
  punctuation / dialogue markers.
- **StoryMemoryEntry** — extracted continuity facts (`memory_type`, `target`,
  `value`).
- **ChatMessage**, **ChatSummary** — project chat and its rolling summary.
- **QuantumStateRecord** — one row per project holding serialized quantum state.

### Stages (versioning / branching)
- **Stage** (scope `project`/`act`/`chapter`/`scene`/`psyke`/`outline`; status
  `active`/`archived`/`canonical`/`alternate`), **StageSnapshot** (captured data),
  **StageBranch** (an explicit branch edge). See
  [structure-and-plot.md](structure-and-plot.md#stages--narrative-versioning--branching).

### Engine-specific tables
- **Graphic Novel** — `GraphicNovelIssue` → `GraphicNovelSequence` /
  `GraphicNovelPage` → `GraphicNovelPanel`, plus `GraphicNovelContinuityItem` and
  `GraphicNovelContinuityAppearance`.
- **Stage Script** — `StageEntranceExit`, `StageCue`, `StageBusiness` (props
  reference a PSYKE *object* entry rather than duplicating them).
- **Series** — `Season` → `Episode` → `EpisodePlotline`, and `SeriesArc` (arcs reuse
  PSYKE entries by id).

These tables are all default-safe: projects in other engines simply leave them
empty, and they are created non-destructively on open.

---

## Project files, autosave & cloud safety

A portable project file is the JSON document produced by `export_json` /
consumed by `import_json` (see [export-import.md](export-import.md)).

**Autosave** (`autosave.py`) debounces edits and writes the project file
**atomically** — to a sibling temp file, fsync, then `os.replace()` — so a crash or
a cloud sync mid-write can never leave a partial file.

**Cloud safety** (`cloud_storage.py`) treats Dropbox, Google Drive, iCloud,
OneDrive, and NAS folders as ordinary paths (no OAuth, no provider APIs):

- a **lock sidecar** `<project>.json.logosforge.lock` records device, user, app
  version, PID, and timestamp, so opening the same file on another device warns
  "may already be open"; stale locks (dead PID, or older than 24 h) are ignored;
- a **file fingerprint** (mtime + size) detects external changes; when one is
  found, the pending content is written to a **conflict copy**
  `<project>_conflict_<device>_<timestamp>.json` instead of overwriting;
- `detect_cloud_folders()` / `classify_path()` power the optional cloud-folder
  picker.

**Versioning** (`version_manager.py`) keeps timestamped JSON **snapshots** under
`~/.storyplanner/versions/<project_id>/` (auto every few minutes when dirty, or on
demand), retaining the most recent 50. Restoring a version first takes a safety
snapshot, then imports the chosen one. The **Version History** dialog browses and
restores them.

---

## Events & lifecycle

`project_events.py` is a process-global `ProjectEventBus` (`QObject`) with granular
signals — `scene_changed`, `psyke_changed`, `notes_changed`, `plot_changed`,
`outline_changed`, `project_loaded`, `project_created`,
`assistant_action_completed`, and the catch-all `project_data_changed`. Views
subscribe and refresh in place; writes (including Connector actions) emit the
appropriate signal. `project_lifecycle.py` clears per-project caches (quantum
state, paragraph energy, look-ahead) when you switch projects, and
`project_compat.py` resolves a project's engine and writing format, migrating the
legacy `format_mode` field on the fly (see [narrative-engines.md](narrative-engines.md)
and [writing-formats.md](writing-formats.md)).
