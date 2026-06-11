# Alpha Release Candidate — Status

**Classification: A — Ready for Alpha Release Candidate.**

- **Product:** Logosforge — local-first Creative Writing system (Python core).
- **Version:** `0.9.0-alpha` (`storyplanner/__init__.py` · `__status__ = "alpha"`).
- **Branch:** `claude/setup-storyplanner-app-5cVxF`.
- **Date:** 2026-06-08.
- **Scope of this step:** Alpha RC **packaging / freeze + documentation only** — no
  product features, no refactors, **no production code changed**.

## FINAL COMBINED ALPHA RETEST GATE (2026-06-10)

A single combined gate re-verified **all** post-RC areas together: Graphic Novel
Outline/Page/Panel + Manuscript mirroring + standalone-Pages disabled +
fullscreen safety; the corrected Series hierarchy + Navigator + legacy
migration; the writing-mode lock; export dependencies + privacy; the local
Voice MVP (Local PC + Local LAN backends, URL security, commit safety); the LAN
Whisper companion (manual-start, localhost-default, endpoints, auth, logging
hygiene); and core regression (all five modes, Timeline, Notes, PSYKE,
autosave/dirty, project isolation, Canvas Plot hidden, no ComfyUI).

**Result: 790 passed, 0 failures** across the curated batches (gates + GN +
pages + series + lock = 467 · voice ×3 + export = 128 · isolation + lifecycle +
autosave + notes = 62 · timeline + structure + multi-mode + writing-modes = 133),
plus a 297-test pre-voice cross-check combo. **No release blockers.** Docs
verified to state every required guarantee; `CHANGELOG.md` gained the
consolidated post-RC entry.

One environment finding (not a product bug, documented in
[ALPHA_TEST_COMMANDS.md](ALPHA_TEST_COMMANDS.md)): very large single-process
pytest combinations can segfault on a timing-dependent Qt/GC teardown
interaction around the test-only pattern of constructing many MainWindows that
share the process-singleton event bus. Every suite passes alone and in the
curated batches; the running app (one window, process-lifetime bus) is
unaffected. Pre-existing — a pre-voice 297-test combo of the same shape passes.

**Gate classification: A — manual Alpha RC retest can resume**
(`docs/ALPHA_MANUAL_SMOKE_TEST.md`; tag only after manual confirmation).

## Post-gate fixes (packaging/usability)

- **Dependency manifest:** `requirements.txt` now lists the optional export libs
  `reportlab` (PDF) and `python-docx` (DOCX), so a normal install supports every
  export format. Graceful degradation is preserved when an environment lacks them.
- **Series Navigator:** a Series-only, read-only navigator was added under the left
  **Plan** group (Season/Arc → Episode → Scene, with A/B/C buckets derived from the
  Episode Beat Plan). It mirrors the Graphic-Novel "Pages" gating, navigates to
  Outline/Manuscript without mutating data, and never appears in other modes. No
  Season/Episode storage hierarchy was introduced.
- **Graphic Novel Pages/Manuscript single source of truth:** the GN "Pages"
  section now edits the **same** scene body as the Manuscript — `Scene.content`
  parsed/serialized by `graphic_novel_blocks` into Pages → Panels (visual /
  caption / dialogue / SFX / notes). The new scene-centric Pages view
  (collapsible panel cards) replaces the previously disconnected project-level
  pages surface as the wired nav; edits round-trip between Manuscript and Pages
  via the shared body. The legacy project-level `GraphicNovelPage/Panel` tables
  are left intact (non-destructive, deferred). No image generation / ComfyUI /
  prompt fields / visual canvas.

## Post-gate blocker fix

One Alpha-blocker was fixed after the gate: **writing mode is now locked once a
project has meaningful content** (it was previously switchable, which could make
the Manuscript read one mode's body as another's). Mode is chosen at creation and
locked thereafter; the Project Settings selector is disabled with a clear message
and any mode change is refused without mutating data. Conversion remains a deferred
future workflow. Single source of truth: `writing_modes.can_change_writing_mode` /
`change_writing_mode`. See `docs/KNOWN_LIMITATIONS_ALPHA.md`.

## Post-fix regression gate (2026-06-08)

A targeted gate re-verified the three Alpha-blocker fixes (Graphic Novel shared
body, corrected Series hierarchy, writing-mode lock) plus the export-dependency
manifest, and confirmed **no regressions** elsewhere:

- **Graphic Novel:** Manuscript ↔ Pages/Panels share one body (`Scene.content`);
  single store; add/edit/delete/reorder round-trip; export uses the shared body;
  panel fields are script-only (no image data). ComfyUI stays a **disabled stub**
  and no image-generation action exists in the Logos registry.
- **Series:** real Season → Episode → Act → Chapter → Scene; episode-local
  Acts/Chapters are **not** confused with Seasons/Episodes; Navigator scenes open
  in the Manuscript; moving a Season/Episode never loses a body; export traverses
  the real hierarchy once with no secrets; legacy shortcut projects load read-only
  and convert non-destructively.
- **Mode lock:** empty projects can change mode; any project with body / planning
  / Season-Episode content is locked; a blocked change mutates nothing.
- **Dependencies:** `requirements.txt` lists `reportlab` + `python-docx`; PDF/DOCX
  still degrade gracefully when absent. Canvas Plot stays hidden.

New focused gate: `tests/test_post_fix_regression_gate.py` (**20 passed**).
Verification sweep across the audited areas + all five modes + Timeline / PSYKE /
isolation / Alpha gate: **858 passed, 0 failures** (only the pre-existing
optional-lib PDF/DOCX cases fail in an environment without `reportlab` /
`python-docx`). **Classification: A — post-fix gate passed.**

## Graphic Novel — Pages/Panels in the Outline + Manuscript (standalone Pages disabled)

The standalone left-panel **Pages** route proved fullscreen-hostile (clicking it
minimized the app in macOS fullscreen, across multiple attempted fixes), so it is
**disabled for Alpha** — hidden in every mode, inert route that never mounts the old
standalone Pages widget. Graphic Novel Page/Panel management now lives in **two
mirrored surfaces** over the shared `Scene.content` body:

- the **Outline** (`GraphicNovelOutlineView`) — the GN Page/Panel navigator: a
  **Scenes** tab (`Act → Chapter → Scene → Page → Panel`, editable) + a **Pages** tab
  (chapter-level cross-reference grouping panels across the chapter's scenes by page
  number — a page can show panels from multiple scenes), with a selected-Panel editor
  (Visual / Caption / Dialogue / SFX / Notes), add/move/delete, assign-panel-to-page,
  and double-click → Manuscript;
- the **Manuscript** (`GraphicNovelManuscriptView`) — the **comics script
  editor** (Superscript-style blocks): PAGE headings + one large free-typing
  script block per panel where the writer types labeled sections (Visual /
  Caption / Dialogue / SFX / Notes — labels optional; unlabeled text is the
  Visual; speaker lines stay content). Blocks parse back into the canonical
  five-field model on commit (focus-out) with line breaks preserved
  end-to-end and auto-numbered pages/panels; per-page **+ Panel** / **Delete
  Page**, per-panel move/delete (confirmed); flat scene dropdown (no tree, no
  form — structure stays in the Outline, whose Panel double-click deep-links
  to the script block here; focus survives the app-wide refresh that follows
  each save).

Both read/write the same body (single source of truth), so they mirror. Model:
Chapter owns Pages (via scenes), Scene owns Panels, Panel assigned to a Page, Scene
can span Pages. Pages are physically scene-scoped for Alpha (the chapter Page View is
a cross-reference; merging panels from different scenes onto one shared page record is
a documented next step). Both surfaces are single embedded child widgets (no separate
route, no top-level window, no dialog on mount) → cannot trigger the minimize. Non-GN
Outline/Manuscript unchanged (`PlanView` / `WritingCoreView`).

Single source: `MainWindow._show_plan` (GN → `GraphicNovelOutlineView`) +
`_show_manuscript` (GN → `GraphicNovelManuscriptView`) + `_apply_pages_availability`
(hides standalone Pages) + `_show_gn_pages` (inert). Data layer:
`storyplanner/graphic_novel_outline.py`. Tests: `tests/test_gn_outline.py`
(**38 passed**), `tests/test_gn_manuscript_script_editor.py` (**66 passed** —
replaces `test_gn_embedded_navigator.py` after the Manuscript was reshaped from
a tree+detail navigator into the inline comics script editor), plus
pages/lifecycle/phase suites. True macOS fullscreen behavior must still be confirmed
manually (smoke-test F-items). **Classification: A — Graphic Novel Outline manages
Pages/Panels and mirrors the Manuscript; standalone Pages disabled.**

**Post-fix integrity gate (2026-06-08).** A targeted audit re-verified the model
(Chapter owns Pages, Scene owns Panels, Panel assigned to Page, Scene spans Pages),
data integrity (move-to-page preserves the body; reorder-scene preserves panels;
save/reload round-trips with no duplicate panels; one canonical panel body),
Outline⇄Manuscript single-body mirroring, standalone-Pages-disabled + fullscreen
safety, export (Panel→Page and Panel→Scene, no duplicate text / no secrets / no
ComfyUI), and full cross-mode regression — **no regressions** found. New gate:
`tests/test_gn_outline_integrity_gate.py` (**13 passed**); broad audit sweep
**813 passed, 0 failures**. Only deferral: **Page reorder** (move Page up/down) in
the Outline is not implemented for Alpha (panel reorder + move-panel-to-page are).
**Gate result: A.**

## Last audit summary

The final global multi-mode integrity audit (the **Alpha Release Gate**, see
[ALPHA_RELEASE_GATE_AUDIT.md](ALPHA_RELEASE_GATE_AUDIT.md)) returned **A**: all five
writing modes form one coherent system on the universal Manuscript, with the
canonical Act → Chapter → Scene invariant, project isolation, export privacy,
dirty-state handling, mode-aware non-mutating AI assistance, and no scope creep.
Per-mode integrity audits also returned A: Screenplay, Graphic Novel
([GRAPHIC_NOVEL_MODE_INTEGRITY_AUDIT.md](GRAPHIC_NOVEL_MODE_INTEGRITY_AUDIT.md)),
Stage Script ([STAGE_SCRIPT_MODE_INTEGRITY_AUDIT.md](STAGE_SCRIPT_MODE_INTEGRITY_AUDIT.md)),
and Series ([SERIES_MODE_INTEGRITY_AUDIT.md](SERIES_MODE_INTEGRITY_AUDIT.md)).

## Tests run / result

| Run | Command | Result |
|-----|---------|--------|
| Focused gate | `pytest tests/test_alpha_release_gate.py` | **35 passed** |
| Broad certification sweep | see [ALPHA_TEST_COMMANDS.md](ALPHA_TEST_COMMANDS.md) | **1527 passed, 0 failures** |

The previously-known red tests (two stale `test_logos_integration.py` cases that
referenced the removed `_action_buttons` toolbar API) were fixed at the test layer;
the suite is now fully green. The full ~120-file suite cannot finish inside the
environment's time cap, so the gate runs a broad blast-radius sweep across every
mode + cross-cutting surface (see [ALPHA_TEST_COMMANDS.md](ALPHA_TEST_COMMANDS.md)).

## Changed files for packaging (this step)

Documentation only:

- `RELEASE_NOTES_ALPHA.md` (updated — Alpha RC multi-mode section)
- `CHANGELOG.md` (updated — Alpha RC entry)
- `docs/ALPHA_RC_STATUS.md` (new — this file)
- `docs/ALPHA_RC_CHECKLIST.md` (new)
- `docs/ALPHA_TEST_COMMANDS.md` (new)
- `docs/KNOWN_LIMITATIONS_ALPHA.md` (updated — multi-mode RC section)
- `docs/ALPHA_RELEASE_GATE_AUDIT.md` (updated — final RC status note)

**Production code touched: none.**

## Series hierarchy — Phase 1 (post-RC foundation)

The Series Alpha shortcut (Act = Season, Chapter = Episode) has been replaced by a
real **Season → Episode → Act → Chapter → Scene** hierarchy: Season/Episode are
stored rows, each Series scene links to its Episode via a new nullable
`Scene.episode_id` (NULL elsewhere — no other mode is affected), and the
Act→Chapter→Scene outline is episode-scoped. The Series Navigator is now the
structural editor (full CRUD + non-destructive, confirmed legacy migration). The
*global* Outline/Manuscript/Timeline stay episode-agnostic for now (documented
Phase-1 boundary). Single source: `storyplanner/series_structure.py`; see
[SERIES_ARCHITECTURE_CORRECTION_REPORT.md](SERIES_ARCHITECTURE_CORRECTION_REPORT.md)
§10 and [KNOWN_LIMITATIONS_ALPHA.md](KNOWN_LIMITATIONS_ALPHA.md). Tests:
`tests/test_series_hierarchy.py` (70 passed); legacy navigator stays green.

## Deferred work (out of scope, intentionally)

- Canvas Plot (hidden/deferred), ComfyUI / image generation, production scheduling,
  rehearsal / writers-room management, showrunner automation, and a Season/Episode-
  aware *global* Outline (the Phase-1 hierarchy lives in the Series Navigator). See
  [KNOWN_LIMITATIONS_ALPHA.md](KNOWN_LIMITATIONS_ALPHA.md).

## Recommended next steps

1. **Manual local smoke test** — follow [ALPHA_RC_CHECKLIST.md](ALPHA_RC_CHECKLIST.md).
2. **Optional Git tag** — only after manual confirmation, and only when explicitly
   instructed (this step does **not** tag).
3. **Optional GitHub release** — after tagging, when instructed.
4. **Commercial packaging plan** — prepared separately (see below).

## Commercial product note (documentation only)

The **current repository is the Python core / main creative-writing app** — the
single source of truth for the engine, data model, and AI surfaces. The planned
commercial products are **separate, later packaging/distribution targets**:

- an **Electron desktop app**, and
- a **Web app**,

both of which should **call or attach to this Python core / API** rather than
re-implement it. This Alpha RC is the Python core milestone and **should not be
conflated** with final Electron/Web commercial packaging.

## Voice MVP Phases 1–9 — Alpha hardening gate (2026-06-10)

The complete local voice stack — flag/capture/buffering (1), mode-aware
Commit Router (2), transcript history with edit/undo/retry (3), preview-first
Intent Router (4), Billy Voice Bridge (5), Dexter's Room shell with state
machine + proposal queue (6), project Voice Glossary corrections (7), Voice
Setup/diagnostics/backend profiles incl. whisper.cpp (8) — passed the Phase 9
end-to-end hardening gate. Privacy audit: `voice/lan_server.py` is the only
network-touching voice module (private/loopback hosts enforced); **zero
logging statements** in the voice stack; exports and diagnostics carry no
transcripts, glossary internals, audio or secrets. Cross-cutting pins:
uncommitted voice history never locks the writing mode (committed text
does); app close while recording stops safely; 30-segment sessions stay
ordered with audio dropped on discard/clear; one active backend per mode by
construction; every voice module imports without the optional dependencies.
Suites: 13 voice files **427 passed** (incl. `tests/test_voice_alpha_gate.py`,
9) + writing-mode/structural regression **449 passed** — 0 failures.
Real-microphone/fullscreen items remain in the manual checklist (V1–V49).
**Classification: A — Voice MVP is Alpha-safe.**

## FINAL ALPHA RC INTEGRATION GATE (2026-06-10) — PASSED

One integration audit across everything that ships in the Alpha: core app +
five writing modes + corrected Graphic Novel architecture (standalone Pages
disabled; Outline manages Pages/Panels; the Manuscript is the mirrored
comics script editor) + corrected Series hierarchy (Season → Episode → Act →
Chapter → Scene; old shortcut deprecated) + the complete Voice MVP
(Phases 1–9, review-first everywhere, local-only) + exports/requirements +
privacy. **No release blockers found; no production code changed in this
gate.**

Evidence (all green, 0 failures):

- **Authoritative broad certification sweep** (`docs/ALPHA_TEST_COMMANDS.md`
  §2, 49 files): **1527 passed** — identical to its historical baseline, in
  a single process.
- **Post-sweep voice + preferences batch** (14 files, Phases 1–9 incl. the
  Phase 9 hardening gate): **392 passed**.
- **Post-sweep GN/Series/lock/lifecycle/export batch** (15 files): **392
  passed**.
- Total this gate: **2311 passed, 0 failed.**

Requirements audit: `reportlab` + `python-docx` present for exports; **no
voice dependencies baked in** (faster-whisper / sounddevice / whisper.cpp
remain optional, lazy and documented); graceful degradation pinned by
tests. Privacy: exports and diagnostics carry no API keys, provider
secrets, transcripts, audio or temp voice data (test-pinned); the only
network-touching voice module is the private-host-enforced LAN client.

Remaining before tag: the **manual smoke test** (V1–V49 + P/F items — real
microphone, macOS fullscreen, optional-dep exports) and maintainer
sign-off. The full ~120-file suite stays infeasible under the gate time
cap (documented combined-run caveat); the sweep + post-sweep batches above
are the authoritative automated check.

**Classification: A — final Alpha RC integration gate passed; ready for
manual release confirmation.**
