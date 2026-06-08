# Alpha RC — Manual Smoke Test

> **Status: PENDING MANUAL RETEST — template prepared.**
> This document is a retest *template*. The manual UI checklist has **not** been
> run yet; every manual item below is `PENDING MANUAL RETEST` / `NOT TESTED`.
> The automated focused suites (§ Automated pre-verification) **are** green, but
> automated tests are **not** a substitute for manual UI verification. Do not
> read this as "the smoke test passed."

- **Branch:** `claude/setup-storyplanner-app-5cVxF`
- **Template prepared:** 2026-06-08
- **Manual retest date / tester:** _pending manual entry_
- **App version:** `0.9.0-alpha` (`storyplanner/__init__.py`)

## Retest context

The Alpha RC was previously "ready", but manual testing surfaced four serious
blockers, all addressed by post-RC blocker fixes:

1. **Writing-mode switching after creation could misinterpret bodies** → mode is
   now **locked** once a project has meaningful content
   (`writing_modes.can_change_writing_mode` / `change_writing_mode`; commit
   `5ce9d86`).
2. **PDF export required a missing `reportlab`** → `requirements.txt` now lists
   `reportlab` + `python-docx`; PDF/DOCX still degrade gracefully when absent.
3. **Graphic Novel Manuscript and Pages/Panels needed one coherent body** → both
   now edit the same `Scene.content` via `graphic_novel_blocks` (commit `3ac8115`).
4. **Series needed the corrected hierarchy** → real
   **Season → Episode → Act → Chapter → Scene** with `Scene.episode_id` +
   `series_structure.py` + rebuilt Navigator (commit `f9dc1a2`).

This retest confirms those fixes in the running app and decides whether the Alpha
RC can proceed to **tag / release**.

## How to run

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 run.py
```

Optional export formats: `pip install reportlab python-docx` (PDF / DOCX). See
`RELEASE_NOTES_ALPHA.md` and `docs/AI_SETUP.md`.

## Automated pre-verification (completed)

Focused suites run before manual retest (supporting evidence only — **not** the
manual UI check). Command form:
`QT_QPA_PLATFORM=offscreen python -m pytest <file> -q -p no:cacheprovider`

| Suite | Result |
|-------|--------|
| `tests/test_alpha_release_gate.py` | **35 passed** |
| `tests/test_post_fix_regression_gate.py` | **20 passed** |
| `tests/test_pages_fullscreen_safe.py` (Pages fullscreen-safe dialogs) | **16 passed** |
| `tests/test_gn_pages_manuscript_sync.py` (GN shared body) | **30 passed** |
| `tests/test_series_hierarchy.py` (Series hierarchy) | **70 passed** |
| `tests/test_series_navigator.py` (Navigator + deps) | **26 passed** |
| `tests/test_writing_mode_lock.py` (mode lock) | **22 passed** |
| `tests/test_export_safety.py` (export privacy) | **4 passed** |
| **Total** | **223 passed, 0 failed** |

> Environment note: PDF/DOCX export tests fail only where `reportlab` /
> `python-docx` are not installed (pre-existing, graceful-degradation behavior),
> not a code regression. Full certification was **not** run (out of scope here).

## Manual retest checklist

Legend — **Result:** `PASS` / `FAIL` / `PARTIAL` / `NOT TESTED` / `BLOCKED`
(all start `PENDING MANUAL RETEST`). **Auto:** `✓` = an automated test exercises
this behavior as supporting evidence (the manual UI check is still required).

### Core launch / project

| # | Item | Result | Auto |
|---|------|--------|------|
| 1 | Launch app | PENDING MANUAL RETEST | |
| 2 | Create new project | PENDING MANUAL RETEST | ✓ |
| 3 | Create Act → Chapter → Scene | PENDING MANUAL RETEST | ✓ |
| 4 | Save project | PENDING MANUAL RETEST | |
| 5 | Reopen project | PENDING MANUAL RETEST | ✓ |
| 6 | Data persists | PENDING MANUAL RETEST | ✓ |

### Writing-mode lock

| # | Item | Result | Auto |
|---|------|--------|------|
| 7 | Empty new project can change writing mode | PENDING MANUAL RETEST | ✓ |
| 8 | After meaningful content, selector disabled/blocked | PENDING MANUAL RETEST | ✓ |
| 9 | Blocked mode change shows clear warning | PENDING MANUAL RETEST | ✓ |
| 10 | Blocked mode change does not mutate body | PENDING MANUAL RETEST | ✓ |
| 11 | Blocked mode change does not mark dirty unnecessarily | PENDING MANUAL RETEST | |
| 12 | Novel body cannot switch to Screenplay | PENDING MANUAL RETEST | ✓ |
| 13 | Screenplay body cannot switch to Novel | PENDING MANUAL RETEST | ✓ |
| 14 | Graphic Novel cannot switch to another mode | PENDING MANUAL RETEST | ✓ |
| 15 | Stage Script cannot switch to another mode | PENDING MANUAL RETEST | ✓ |
| 16 | Series cannot switch to another mode | PENDING MANUAL RETEST | ✓ |

### Novel

| # | Item | Result | Auto |
|---|------|--------|------|
| 17 | Novel Manuscript opens prose editor | PENDING MANUAL RETEST | |
| 18 | Novel body saves / reloads correctly | PENDING MANUAL RETEST | ✓ |

### Screenplay

| # | Item | Result | Auto |
|---|------|--------|------|
| 19 | Screenplay Manuscript opens block editor | PENDING MANUAL RETEST | |
| 20 | Screenplay block body saves / reloads | PENDING MANUAL RETEST | ✓ |
| 21 | Fountain export works (if tested) | PENDING MANUAL RETEST | ✓ |

### Graphic Novel

| # | Item | Result | Auto |
|---|------|--------|------|
| 22 | Manuscript opens Page/Panel structured editor | PENDING MANUAL RETEST | |
| 23 | Pages section shows the same Pages/Panels as Manuscript | PENDING MANUAL RETEST | ✓ |
| 24 | Editing Manuscript updates Pages/Panels | PENDING MANUAL RETEST | ✓ |
| 25 | Editing Pages/Panels updates Manuscript | PENDING MANUAL RETEST | ✓ |
| 26 | Add Page updates both views | PENDING MANUAL RETEST | ✓ |
| 27 | Add Panel updates both views | PENDING MANUAL RETEST | ✓ |
| 28 | Delete Panel updates both (after confirm) | PENDING MANUAL RETEST | ✓ |
| 29 | Reorder Panel updates both | PENDING MANUAL RETEST | ✓ |
| 30 | Panels collapsible/hideable, layout usable | PENDING MANUAL RETEST | ✓ |
| 31 | Export uses shared Pages/Panels body | PENDING MANUAL RETEST | ✓ |
| 32 | No image-generation / ComfyUI fields appear | PENDING MANUAL RETEST | ✓ |

### Fullscreen window-management — Pages Create New (post-RC blocker fix)

> Headless tests can verify the dialog is window-modal, correctly parented, and
> that create opens **no** dialog and makes **no** minimize/hide call
> (`tests/test_pages_fullscreen_safe.py`, 16 passed). True fullscreen
> Space behavior on macOS **must be confirmed manually** — run these **in
> fullscreen**:

| # | Item | Result | Auto |
|---|------|--------|------|
| F1 | Enter macOS **fullscreen**, open a Graphic Novel project | PENDING MANUAL RETEST | |
| F2 | Open the **Pages** section | PENDING MANUAL RETEST | |
| F3 | Click **+ Page** — app does **not** minimize/disappear | PENDING MANUAL RETEST | partial |
| F4 | No rapid window flicker; main window stays visible & focused | PENDING MANUAL RETEST | partial |
| F5 | A Page is created in place (or cancel does nothing) | PENDING MANUAL RETEST | ✓ |
| F6 | Click **+ Panel** — same: no minimize, no flicker | PENDING MANUAL RETEST | partial |
| F7 | Delete Page/Panel confirmation appears as a **sheet** (window-modal), not a separate window; cancel leaves data unchanged | PENDING MANUAL RETEST | ✓ |

### Stage Script

| # | Item | Result | Auto |
|---|------|--------|------|
| 33 | Stage Script Manuscript opens stage block editor | PENDING MANUAL RETEST | |
| 34 | Stage blocks save / reload correctly | PENDING MANUAL RETEST | ✓ |

### Series

| # | Item | Result | Auto |
|---|------|--------|------|
| 35 | Series Navigator under Plan, Series mode only | PENDING MANUAL RETEST | ✓ |
| 36 | Navigator absent in Novel/Screenplay/GN/Stage | PENDING MANUAL RETEST | ✓ |
| 37 | Create Season | PENDING MANUAL RETEST | ✓ |
| 38 | Create Episode inside Season | PENDING MANUAL RETEST | ✓ |
| 39 | Create Act inside Episode | PENDING MANUAL RETEST | ✓ |
| 40 | Create Chapter inside Act | PENDING MANUAL RETEST | ✓ |
| 41 | Create Scene inside Chapter | PENDING MANUAL RETEST | ✓ |
| 42 | Rename Season | PENDING MANUAL RETEST | ✓ |
| 43 | Rename Episode | PENDING MANUAL RETEST | ✓ |
| 44 | Move Season (implemented) | PENDING MANUAL RETEST | ✓ |
| 45 | Move Episode within Season (implemented) | PENDING MANUAL RETEST | ✓ |
| 46 | Open Episode Outline (Navigator subtree) | PENDING MANUAL RETEST | |
| 47 | Episode Outline shows Act→Chapter→Scene (no Season/Episode confusion) | PENDING MANUAL RETEST | ✓ |
| 48 | Clicking Scene opens universal Manuscript | PENDING MANUAL RETEST | ✓ |
| 49 | Manuscript path shows full Series path — **deferred (Phase 1)**; path exists at data layer (`scene_series_path`), title-bar wiring deferred | PENDING MANUAL RETEST | |
| 50 | Moving Episode does not lose Scene body | PENDING MANUAL RETEST | ✓ |
| 51 | Series export traverses Season→Episode→Act→Chapter→Scene | PENDING MANUAL RETEST | ✓ |
| 52 | A/B/C Plots show from Episode data or clear empty state | PENDING MANUAL RETEST | ✓ |
| 53 | No old Act=Season / Chapter=Episode confusion (legacy adapter documented) | PENDING MANUAL RETEST | ✓ |

### Timeline

| # | Item | Result | Auto |
|---|------|--------|------|
| 54 | Timeline opens | PENDING MANUAL RETEST | |
| 55 | Timeline lanes independent from Outline / Series Seasons | PENDING MANUAL RETEST | ✓ |
| 56 | Timeline does not auto-create fake lanes from Seasons/Episodes | PENDING MANUAL RETEST | ✓ |
| 57 | Timeline links show correct path (if tested) | PENDING MANUAL RETEST | ✓ |

### Notes / PSYKE

| # | Item | Result | Auto |
|---|------|--------|------|
| 58 | Notes are project-bound | PENDING MANUAL RETEST | ✓ |
| 59 | PSYKE is project-bound | PENDING MANUAL RETEST | ✓ |
| 60 | Switching projects clears old Notes/PSYKE context | PENDING MANUAL RETEST | ✓ |

### Exports / dependencies

| # | Item | Result | Auto |
|---|------|--------|------|
| 61 | `requirements.txt` includes `reportlab` | PENDING MANUAL RETEST | ✓ |
| 62 | `requirements.txt` includes `python-docx` | PENDING MANUAL RETEST | ✓ |
| 63 | Markdown export works | PENDING MANUAL RETEST | ✓ |
| 64 | TXT export works (if tested) | PENDING MANUAL RETEST | ✓ |
| 65 | Fountain export works for Screenplay (if tested) | PENDING MANUAL RETEST | ✓ |
| 66 | JSON export works (if tested) | PENDING MANUAL RETEST | ✓ |
| 67 | PDF works if `reportlab` installed, else graceful message | PENDING MANUAL RETEST | ✓ |
| 68 | DOCX works if `python-docx` installed, else graceful message | PENDING MANUAL RETEST | ✓ |
| 69 | Exports contain no API keys / provider settings | PENDING MANUAL RETEST | ✓ |

### Project isolation

| # | Item | Result | Auto |
|---|------|--------|------|
| 70 | Create Project A with content | PENDING MANUAL RETEST | ✓ |
| 71 | Create Project B with different content | PENDING MANUAL RETEST | ✓ |
| 72 | Switch A → B: no A data visible | PENDING MANUAL RETEST | ✓ |
| 73 | Switch B → A: A data returns | PENDING MANUAL RETEST | ✓ |
| 74 | New Project C starts clean | PENDING MANUAL RETEST | ✓ |

### Dirty / save / close

| # | Item | Result | Auto |
|---|------|--------|------|
| 75 | Editing body marks project dirty | PENDING MANUAL RETEST | |
| 76 | Editing Outline marks project dirty | PENDING MANUAL RETEST | |
| 77 | Editing Timeline/Notes marks dirty if changed | PENDING MANUAL RETEST | |
| 78 | Preview-only actions do not mutate body | PENDING MANUAL RETEST | ✓ |
| 79 | Closing dirty project asks to save | PENDING MANUAL RETEST | |
| 80 | Closing clean project does not ask unnecessarily | PENDING MANUAL RETEST | |
| 81 | Save works | PENDING MANUAL RETEST | |
| 82 | Save As works | PENDING MANUAL RETEST | |
| 83 | Open works | PENDING MANUAL RETEST | |
| 84 | Refresh project list works | PENDING MANUAL RETEST | |

### UI / scope

| # | Item | Result | Auto |
|---|------|--------|------|
| 85 | Logos dropdown is readable | PENDING MANUAL RETEST | |
| 86 | Assistant theme updates live after Appearance change | PENDING MANUAL RETEST | |
| 87 | No unwanted Navigator panel returns | PENDING MANUAL RETEST | |
| 88 | Canvas Plot remains hidden / deferred | PENDING MANUAL RETEST | ✓ |
| 89 | No ComfyUI / image-generation actions appear | PENDING MANUAL RETEST | ✓ |
| 90 | No production scheduling / writers-room automation appears | PENDING MANUAL RETEST | ✓ |

## Release blocker criteria

A **release blocker** if any of these FAIL: app cannot launch · project creation
broken · save/open broken · project isolation broken · Manuscript unusable ·
writing-mode lock broken after meaningful content · mode switching corrupts body ·
Graphic Novel Manuscript/Pages mismatch remains · Series cannot create/navigate
Season → Episode → Act → Chapter → Scene · dirty close-save prompt broken · data
loss · export leaks API/provider secrets.

**Non-blocking** (acceptable for Alpha): optional PDF/DOCX dependency absent but
graceful message works · minor UI spacing · dashboard refresh requires manual
refresh · A/B/C explicit assignment deferred if empty state is clear · Series
legacy migration not automatic but old data remains safe · panel undocking
deferred if collapsible layout works.

## Blocker list

_None recorded — pending manual retest._

## Non-blocking issue list (known, pre-documented)

These are already documented in `docs/KNOWN_LIMITATIONS_ALPHA.md` and are
**non-blocking**; confirm during retest:

- Global Outline / Manuscript / Timeline stay episode-agnostic; the Series
  Navigator is the canonical Season/Episode surface (Phase-1 boundary).
- Manuscript title bar does not yet display the full Series path (data layer
  provides it; wiring deferred) — item 49.
- Move-Episode-across-Seasons and internal Act/Chapter reordering deferred
  (Scene reorder + move-scene-between-Episodes supported).
- PDF/DOCX require optional libs; degrade gracefully when absent.
- Dashboards refresh on open / manual button (no live recompute).
- ComfyUI is a disabled stub; the image-*prompt* text export is a legacy GN
  surface — no image generation runs.

## Decision

**PENDING MANUAL RETEST.** Automated focused suites are green (223 passed), but
the manual UI checklist above has not been executed. **Do not tag** the Alpha RC
until the manual checklist is completed and this decision is updated to one of:

- ✅ **Ready to tag** — all blocker-criteria items PASS; only documented
  non-blocking issues remain.
- ⚠️ **Retest required** — partial/blocked items need re-running.
- ⛔ **Not ready to tag** — one or more release blockers FAIL.
