# Changelog

All notable changes to Logosforge. This project uses semantic-ish versioning;
dates are release-readiness milestones, not packaged builds.

## [0.9.0-alpha] — Private Alpha

First closed alpha: a local-first narrative operating system for structured
writing. **Feature-frozen**; this milestone focused on stability, data safety,
UI hardening, and documentation. Back up your work — see
`docs/BackupRestore.md`.

### Major implemented systems

- **Writing Modes** — Novel / Screenplay / Graphic Novel / Stage Script / Series
  as a single project-level source of truth that every section and the AI adapt
  to.
- **Manuscript** — continuous scene editor with focus mode, format-aware blocks,
  font/size/grammar controls, and debounced atomic autosave.
- **Structure** — Outline (AI-generated, confirmed), Multi-Plot, Timeline,
  Story Grid, act/beat/tag analysis.
- **PSYKE** story bible — characters/places/objects/lore/themes with relations,
  progressions and a fast console search.
- **AI Assistant** — engine-aware critique, inline editing, Counterpart mode,
  Quantum outliner, capped/toggleable context, language-aware responses, and
  safe propose-then-confirm actions.
- **Logos** — an inline contextual AI layer (left-panel ON/OFF toggle) with
  diagnostics, narrative health, proactive suggestions and a strategy router.
- **Intelligence services** — Project Intelligence + Decision Radar, Narrative
  Knowledge Graph, Semantic Continuity, Guided Workflows, Adaptive Rewrite
  Sandbox, Controlled Apply, Revision Intelligence (services + Logos/Assistant
  surfaces; dedicated UI deferred to beta).
- **Connector** — local app-control bridge (write actions off by default).
- **Export / Import** — Markdown, TXT, Fountain (screenplay), FDX, HTML, JSON,
  CSV, plus optional PDF/DOCX; story-elements / PSYKE / full-project exports;
  non-destructive import.
- **Autosave / Versioning / Backup-Restore** — atomic project writes, automatic
  + manual per-project snapshots, pre-restore safety snapshot.
- **HTTP API** — a FastAPI DTO layer over the core (desktop/localhost in alpha).

### Alpha stabilization (closing steps)

- **Project lifecycle** — writing-mode-dependent sidebar nav (Graphic-Novel
  Pages) now recomputes on project switch; no stale section state.
- **Refresh propagation** — section views that lacked a `refresh()` (Projects,
  Acts/Beats/Tags) now update in place; no recursion on `project_data_changed`.
- **Writing Modes** — Assistant mode strip re-points (and drops stale override)
  on project switch; mode read fresh everywhere.
- **Editor stability** — refresh flushes pending keystrokes and restores focus +
  cursor; no grey-out / lost typing on Assistant/Logos apply.
- **UI hardening** — removed Qt-unsupported QSS properties (no "Unknown property"
  warnings); raised the Outline-confirm modal minimum; 13-inch responsiveness
  verified (Assistant auto-hide, fitting dialogs).
- **AI provider** — single `build_active_provider` resolver; persisted settings;
  configurable local-aware timeouts with readable errors; Anthropic switch no
  longer flashes a stray window; custom model names allowed; **API keys never
  logged or exported**.
- **Export** — manuscript export now reports failures as readable dialogs
  (incl. a hint when `reportlab`/`python-docx` is missing).
- **Versioning/backup** — surfaced snapshot-load errors; verified per-project
  isolation and non-destructive restore.
- **Version constant** — `storyplanner.__version__ = "0.9.0-alpha"`.

### Documentation

Added the Alpha doc set: README alpha note, User Guide, AI Setup,
Troubleshooting, Alpha Scope/Freeze, Known Limitations, Test Plan, Data Safety,
Backup & Restore, Autosave & Versioning, Export/Interchange (Export Matrix),
Release Checklist, Final Report, and a grouped `docs/index.md`.

### Known limitations

- PDF/DOCX export needs optional libraries; FDX/HTML and the API LAN/remote modes
  are experimental.
- Plot/Timeline are scene-derived; grammar is rule-based.
- Knowledge-Graph / Continuity / Decision-Radar / Workflow services have no UI
  panel yet.
- Single-user, local-only (no cloud sync/collaboration); restore creates a new
  project; API keys are stored in plaintext in the local settings file (never
  exported). See `docs/KNOWN_LIMITATIONS_ALPHA.md`.

### Tests

~6008 tests (Qt offscreen). Safety-critical subset verified green
(214 passed / 0 skipped). The final-gate full run was 6005 passed / 2 failed /
1 skipped; one failure was a UI-hardening regression (Outline-confirm dialog
minimum) now **fixed**, the other is a full-suite-ordering flake that passes in
isolation. See `docs/ALPHA_FINAL_REPORT.md`.
