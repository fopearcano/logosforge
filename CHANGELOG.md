# Changelog

All notable changes to Logosforge. This project uses semantic-ish versioning;
dates are release-readiness milestones, not packaged builds.

## [0.9.0-alpha] — post-RC corrections & additions — 2026-06-10

Blocker fixes and structural corrections found by manual Alpha testing, plus a
feature-flagged local voice foundation. Verified by the **final combined Alpha
retest gate** (see `docs/ALPHA_RC_STATUS.md`).

### Structural corrections

- **Series — real hierarchy.** The Alpha shortcut (Act = Season, Chapter =
  Episode) is replaced by **Series → Season → Episode → Act → Chapter → Scene**:
  `Season`/`Episode` are stored rows, each Series scene links via a new nullable
  `Scene.episode_id` (NULL elsewhere — other modes unaffected), and the
  Act→Chapter→Scene outline is episode-scoped. The Series Navigator is the
  structural editor (full CRUD + non-destructive, confirmed legacy migration).
  The global Outline/Manuscript/Timeline stay episode-agnostic (documented
  Phase-1 boundary).
- **Graphic Novel — Pages/Panels in the Outline + Manuscript.** The standalone
  left-panel **Pages** route proved fullscreen-hostile (clicking it minimized
  the app in macOS fullscreen) and is **disabled for Alpha** (hidden; inert
  route). Page/Panel management lives in two mirrored surfaces over the shared
  `Scene.content` body: the **GN Outline** (Scenes tab `Act → Chapter → Scene →
  Page → Panel` + a chapter-level Pages cross-reference; full editing,
  assign-panel-to-page) and the **Manuscript**. Model: Chapter owns Pages,
  Scene owns Panels, Panel assigned to a Page, a Scene can span Pages.
- **Graphic Novel — Manuscript is a comics script editor, not an outliner.**
  The GN Manuscript initially shipped as a tree + selected-item detail editor
  (an outliner shape). It is now a true **comics script editor**: the selected
  scene's whole script renders inline as PAGE blocks containing Panel cards
  with all five fields (**Visual / Caption / Dialogue / SFX / Notes**) always
  visible and editable in place (commit on focus-out, focus preserved across
  the app-wide refresh that follows each save), per-page **+ Panel** / **Delete
  Page**, per-panel move/delete (confirmed via fullscreen-safe dialogs), an
  empty-state ladder (Create Scene → Add Page → Add Panel → script), and a flat
  scene dropdown. Structure stays in the GN Outline (double-click opens the
  scene in the Manuscript); both still mirror over the same `Scene.content`
  body. Suite: `tests/test_gn_manuscript_script_editor.py` (66 passed, replaces
  `test_gn_embedded_navigator.py`).
- **Graphic Novel — Manuscript upgraded to a Superscript-style script editor.**
  The per-field card layout still read as a form, so the writing surface is
  now true script blocks: PAGE headings + **one large free-typing block per
  panel** in which the writer types labeled sections (`Visual:` / `Caption:` /
  `Dialogue:` / `SFX:` / `Notes:` — labels optional, unlabeled text is the
  Visual, speaker lines like `NAME: …` stay content; blocks auto-grow so the
  scene scrolls as one document). Blocks parse back into the canonical
  five-field model on commit via `graphic_novel_blocks.parse_panel_text`;
  the body parser/serializer now **preserves line breaks inside fields**
  end-to-end (marker-looking lines are folded, never dropped, so structure
  cannot drift); pages/panels stay auto-numbered; the Outline's Panel
  double-click now **deep-links to the panel's script block**. Empty-state
  copy per spec ("No Graphic Novel scene yet." → "+ Create Scene", scene path
  + "Start the comics script for this scene." → "+ Add Page"). Same shared
  body, mirroring, fullscreen safety and export; no image-generation anything.
  Suite rewritten: 56 tests.
- **Writing-mode lock.** Mode is chosen at creation and **locks once a project
  has meaningful content** (body text, planning data, Timeline/Notes/PSYKE,
  user structure, Season/Episode rows); blocked changes mutate nothing.
  Conversion wizard deferred.

### Fixes / packaging

- **Voice Dictation is a floating window that actually toggles.** The voice
  surface was an embedded bottom strip that, with the feature flag off, could
  be shown but **never hidden again**; it was also too small to review
  transcripts. It is now a **floating, modeless, resizable** Voice Dictation
  window (`VoiceDictationWindow`) parented to the main window — one instance,
  toggled show↔hide from the menu / Ctrl+Shift+V; the Hide button, title-bar
  close and Esc all hide it with the transcript preview preserved; hiding
  while recording stops the session safely; never auto-shown, never
  auto-recording, commit stays manual (auto-commit off by default), no
  parentless top-level windows (the Pages-bug rules). Backends unchanged.
- **General Preferences scrolls on small screens.** The Preferences dialog
  put everything (including Close) in one fixed column, so tall content
  pushed the bottom controls off-screen. Settings content now lives in a
  vertical scroll area with a **sticky Close row outside it**, and the dialog
  clamps its height to ~85% of the available screen. Persistence and
  validation unchanged.

- `requirements.txt` lists the optional export libs (`reportlab`,
  `python-docx`); PDF/DOCX degrade gracefully when absent.
- Fullscreen-safe dialog helper (`ui/safe_dialogs.py`): window-modal,
  top-level-parented confirmations (macOS sheets) used by the GN surfaces.

### Added (feature-flagged, off by default)

- **Voice Phase 5 — Billy Voice Bridge (voice → Billy proposal → confirmed
  apply).** Selected transcript segments can be sent to **Billy** (the
  Assistant chat agent) as a question or editing instruction. Billy receives
  **text only** — transcript + a minimal safe context (project title,
  writing mode, selection snippet, selected GN panel fields; never audio,
  never API keys/provider settings, never other-project data) — via the
  app's existing provider configuration (no provider ⇒ all Billy actions
  disabled with "Billy is not configured. Voice-to-Billy actions are
  unavailable."). Fixed operation allowlist: Ask (chat-only), Rewrite
  selected text, Continue from cursor, Summarize to Note, PSYKE draft
  (user-chosen type, default Other), GN Panel-field update (selected panel,
  chosen field, replace with diff; Outline/Manuscript mirror), Outline item
  still listed disabled. Every proposal is preview-first with explicit
  Apply (routed through the existing Intent/Commit routers → live
  re-validation + shared Undo) and Cancel (zero mutation); stale proposals
  block with regenerate messages; project switch invalidates them.
  Dangerous spoken "commands" ("delete the project", "run this command",
  "send to ComfyUI", …) never execute and never reach the provider —
  chat-only: "I can't perform that action from voice in Alpha." Transcript
  history tracks sent_to_billy / proposal id / applied-cancelled (no
  secrets, no audio). `storyplanner/voice/billy_bridge.py` +
  `tests/test_voice_billy_bridge.py` (35 passed).
- **Voice Phase 4 — Voice Intent Router (preview-first confirmed text
  operations).** An explicit **Dictation / Intent** mode selector in the
  voice panel (Dictation stays the default; Intent is opt-in — command mode
  is never inferred). In Intent mode a transcript is an *instruction* from a
  fixed allowlist: rule-based cleanup (whitespace/capitalization/spoken
  punctuation; no AI, never fabricates; transcript-only apply), insert
  cleaned transcript via the chosen commit target, **AI rewrite of the
  editor selection** and **AI summarize-to-Note** (existing provider
  settings only — `build_active_provider` + the shared chat completion;
  text-only, audio never sent; disabled with "AI text operation unavailable.
  Configure an AI provider or use rule-based cleanup." when unconfigured),
  PSYKE draft entry (user-chosen type, default Other) and Graphic Novel
  Panel-field send (chosen field; Outline/Manuscript mirror). Every intent
  builds a before/after (+ diff) or entity preview and applies ONLY on
  explicit confirm; Cancel mutates nothing; apply re-validates project id,
  target existence and the expected before-text ("Target changed since
  preview. Regenerate preview before applying."); applied intents emit the
  Phase 3 operation records so Undo-last-commit covers them. No shell or
  system commands, no voice-command execution, no auto-apply.
  `storyplanner/voice/intent_router.py` + `tests/test_voice_intents.py`
  (37 passed).
- **Voice Phase 3 — transcript history, correction, undo, retry.** A local,
  session-only history of dictated segments in the voice panel: edit before
  commit (original kept + restorable; empty segments never commit), select
  and commit multiple segments together (visible order, edited text, through
  the Commit Router only), merge adjacent / split at the cursor, retry
  transcription on the segment's locally-held audio (in-memory only, never
  on disk, dropped on discard/clear), discard / clear uncommitted, and a
  single-level **Undo last voice commit** that is target-scoped and refuses
  to touch anything else (editor document-revision guard; GN field previous
  value; created Note/PSYKE deleted only if unchanged; otherwise disabled
  with the reason). Per-segment project capture freezes history on project
  switch and blocks cross-project commits. Nothing persists across restarts;
  no telemetry; no cloud. `storyplanner/voice/history.py` + undo layer in
  `commit_router.py`; `tests/test_voice_history.py` (37 passed).
- **Voice Phase 2 — mode-aware commit targets (Voice Commit Router).** After
  reviewing the transcript the user picks an explicit *Send to* target:
  cursor insert; **New Note**; **PSYKE draft entry** (type chosen by the
  user — Character/Place/Object/Lore/Theme/**Other** (default), never
  auto-classified); **Screenplay** Action / Dialogue and **Stage** Direction /
  Dialogue (character picked manually from existing characters — never
  guessed); **Graphic Novel** Panel → Visual/Caption/Dialogue/SFX/Notes for
  the selected Panel (appends; disabled with "Select a Panel first."
  otherwise). Listing/preview never mutates; commits re-validate the live
  target and are blocked if the project changed since transcription; the
  project is marked dirty only after a successful commit; transcript
  segments carry explicit-commit metadata (no audio stored). Deferred with
  visible reasons: Outline / Series-episode draft items and
  Append-to-Manuscript. `storyplanner/voice/commit_router.py` +
  `tests/test_voice_commit_router.py` (41 passed).

- **Local voice-to-script MVP** (`enable_voice_mode`; backend mode defaults to
  *Disabled*): local mic capture, buffered silence-segmented dictation,
  transcript preview, **manual plain-text commit** at the editor cursor.
  Backends: **Local PC** (faster-whisper, optional/lazy, local model path, no
  auto-downloads) and **Local LAN Server** (segments go only to a Whisper
  server on the trusted LAN — private/loopback URLs enforced, public/ngrok/
  tunnel URLs blocked, redirects refused). No cloud speech, no OpenAI Realtime,
  no voice commands, no auto-classification.
- **LAN Whisper companion** (`scripts/local_whisper_server.py`): optional,
  manually-started stdlib server (faster-whisper; `/health`,
  `/v1/audio/transcriptions`, `/inference`); binds 127.0.0.1 by default, LAN
  bind is explicit with a warning; optional Bearer token (never logged).
  External whisper.cpp servers documented (`docs/LOCAL_LAN_WHISPER.md`).

## [0.9.0-alpha] — Alpha Release Candidate (multi-mode) — 2026-06-08

Release-candidate milestone for the five-mode writing system on the **universal
Manuscript**. **Feature-frozen**; this milestone focused on completing the
writing modes, then auditing and stabilizing the whole system. **No new product
features and no production-code changes were made during RC packaging.**

### Major additions (writing modes on the universal Manuscript)

- **Screenplay** (Phases 1–10), **Graphic Novel** (Phases 1–8), **Stage Script**
  (Phases 1–8), and **Series** (Phases 1–8), each adding — over a Scene's flat
  body — a typed block adapter, a planning pipeline (preview → confirmed apply),
  deterministic intelligence checks, Counterpart/Reflection, controlled rewrite
  (preview/diff/confirmed apply), cross-unit continuity, and a Review Dashboard.
- **Series** interprets the canonical Act → Chapter → Scene as Season/Arc →
  Episode → Scene (display only); plans are settings-backed (no Season/Episode
  storage hierarchy).
- All mode AI surfaces are **mode-gated** and **propose-then-confirm**; no silent
  overwrites; deterministic checks never call the provider.

### Stabilization / audits

- Per-mode integrity audits (Screenplay, Graphic Novel, Stage Script, Series) and
  a final **global multi-mode integrity audit / Alpha Release Gate** — all
  classification **A**. See `docs/ALPHA_RELEASE_GATE_AUDIT.md` and the per-mode
  `docs/*_MODE_INTEGRITY_AUDIT.md`.
- Fixed two stale `test_logos_integration.py` cases that referenced the removed
  `_action_buttons` toolbar API (test-harness only; the toolbar is the
  `_action_combo` dropdown) — the suite is now fully green.

### Tests

- Focused gate `tests/test_alpha_release_gate.py` — **35 passed**.
- Broad certification sweep — **1527 passed, 0 failures** (see
  `docs/ALPHA_TEST_COMMANDS.md`).

### Known non-blocking limitations

- Mode checks are conservative/rule-based (no NLP); dashboards refresh on open +
  manual button; persistent serialized-story relation links are reported but not
  yet persisted; optional DOCX/PDF export degrades gracefully when libs are
  absent. ComfyUI/image generation, Canvas Plot, production scheduling,
  writers-room/showrunner automation, and a real Season/Episode storage hierarchy
  remain **deferred**. See `docs/KNOWN_LIMITATIONS_ALPHA.md`.

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
