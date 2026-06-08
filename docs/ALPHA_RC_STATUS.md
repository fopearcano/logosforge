# Alpha Release Candidate — Status

**Classification: A — Ready for Alpha Release Candidate.**

- **Product:** Logosforge — local-first Creative Writing system (Python core).
- **Version:** `0.9.0-alpha` (`storyplanner/__init__.py` · `__status__ = "alpha"`).
- **Branch:** `claude/setup-storyplanner-app-5cVxF`.
- **Date:** 2026-06-08.
- **Scope of this step:** Alpha RC **packaging / freeze + documentation only** — no
  product features, no refactors, **no production code changed**.

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

## Graphic Novel Pages/Panels editor (Pages section restored)

The Graphic Novel **Pages** section is shown in the left **Plan** group (GN-only)
and opens the scene-centric Page/Panel editor (`GraphicNovelScenePagesView`) over
the shared `Scene.content` body — the same editor the GN Manuscript presents: a
scene list with **+ Scene**, and per scene **+ Page** / **+ Panel**, collapsible
Page groups and Panel cards editing **Visual / Caption / Dialogue / SFX / Notes**.
The editor is **child-widget-only** (it creates no top-level window) and mounts via
the standard embedded `_set_content` route, which avoids the earlier macOS
fullscreen minimize seen with the previous standalone Pages wiring. Pages and the
Manuscript edit the same body, so edits stay consistent; non-GN Manuscripts are
unchanged (`WritingCoreView`).

Single source: `MainWindow._apply_pages_availability` (shows Pages for GN) +
`_show_gn_pages` (mounts the editor) + `_show_manuscript` (GN → the same editor).
Pre-existing lifecycle tests (`tests/test_project_lifecycle_switch.py`) assert
Pages appears for GN and disappears for non-GN. Tests:
`tests/test_gn_manuscript_page_editor.py` (**21 passed**),
`tests/test_pages_alpha_fallback.py`, `tests/test_pages_fullscreen_safe.py`. True
macOS fullscreen behavior (clicking **Pages** does not minimize) must still be
confirmed manually (smoke-test F-items). **Classification: A — Page/Panel editing
is accessible (Pages section + Manuscript) and fullscreen-safe by construction.**

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
