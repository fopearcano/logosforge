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
| `tests/test_pages_alpha_fallback.py` (standalone Pages deferred) | **15 passed** |
| `tests/test_gn_embedded_navigator.py` (Manuscript Page/Panel Navigator) | **33 passed** |
| `tests/test_gn_outline.py` (GN Outline Pages/Panels) | **38 passed** |
| `tests/test_gn_outline_integrity_gate.py` (GN Outline integrity gate) | **13 passed** |
| `tests/test_voice_mvp.py` (local voice-to-script MVP) | **35 passed** |
| `tests/test_voice_lan.py` (backend modes + LAN Whisper server) | **43 passed** |
| `tests/test_voice_lan_server.py` (LAN companion server + client integration) | **19 passed** |
| `tests/test_gn_pages_manuscript_sync.py` (GN shared body) | **30 passed** |
| `tests/test_series_hierarchy.py` (Series hierarchy) | **70 passed** |
| `tests/test_series_navigator.py` (Navigator + deps) | **26 passed** |
| `tests/test_writing_mode_lock.py` (mode lock) | **22 passed** |
| `tests/test_export_safety.py` (export privacy) | **4 passed** |
| **Total** | **419 passed, 0 failed** |

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

### Fullscreen window-management — Graphic Novel Outline + Manuscript Page/Panel editor

> The standalone **Pages** sidebar section is **disabled for Alpha** (it was
> fullscreen-hostile). Graphic Novel Page/Panel management lives in the **Outline**
> (Scenes tab `Act → Chapter → Scene → Page → Panel` + a chapter-level Pages
> cross-reference tab) **and** the **Manuscript** (embedded Scene → Page → Panel
> editor), both over the shared `Scene.content` body (child-widget-only; no separate
> route, no top-level window). Headless tests cover both surfaces + route safety
> (`tests/test_gn_outline.py`, `tests/test_gn_embedded_navigator.py`,
> `tests/test_pages_alpha_fallback.py`, `tests/test_pages_fullscreen_safe.py`).
> **Confirm the fullscreen behavior manually** — especially that opening the GN
> Outline/Manuscript does not minimize the app:

| # | Item | Result | Auto |
|---|------|--------|------|
| F1 | Enter macOS **fullscreen**, open a Graphic Novel project | PENDING MANUAL RETEST | |
| F2 | The standalone **Pages** sidebar item is **not shown** (disabled) | PENDING MANUAL RETEST | ✓ |
| F3 | Click **Outline** — the GN Page/Panel Outline appears; app does **not** minimize/flicker | PENDING MANUAL RETEST | partial |
| F4 | Outline **Scenes** tab shows `Act → Chapter → Scene → Page → Panel`; **Pages** tab groups panels by chapter page | PENDING MANUAL RETEST | ✓ |
| F5 | Add Scene / Page / Panel in the Outline; edit Visual / Caption / Dialogue / SFX / Notes | PENDING MANUAL RETEST | ✓ |
| F6 | Open the **Manuscript** — the same Pages/Panels appear (mirrored); app stays fullscreen | PENDING MANUAL RETEST | ✓ |
| F7 | Export Graphic Novel text / Markdown (shared body; shows Panel → Page and Panel → Scene) | PENDING MANUAL RETEST | ✓ |

### Local voice-to-script (MVP) — OFF by default

> Local-first dictation; **no cloud, no audio upload**. Requires optional local
> backends (`faster-whisper`, `sounddevice`) + a local model path. Headless tests
> cover the logic + panel (`tests/test_voice_mvp.py`, 28 passed). Confirm with a real
> microphone manually:

| # | Item | Result | Auto |
|---|------|--------|------|
| V1 | App starts normally with voice off; no voice panel shown | PENDING MANUAL RETEST | ✓ |
| V2 | Enable `enable_voice_mode`; without backend/model the panel shows a non-blocking setup message (no crash) | PENDING MANUAL RETEST | ✓ |
| V3 | Configure local Whisper model path + install `faster-whisper`/`sounddevice` | PENDING MANUAL RETEST | |
| V4 | View → Voice Dictation (Ctrl/Cmd+Shift+V); Start; speak a short sentence; Stop | PENDING MANUAL RETEST | |
| V5 | Transcript appears in the preview | PENDING MANUAL RETEST | ✓ |
| V6 | Click in the editor, then Commit — text inserts at the cursor | PENDING MANUAL RETEST | ✓ |
| V7 | Clear removes the preview | PENDING MANUAL RETEST | ✓ |
| V8 | No crash when the microphone is unavailable / permission denied | PENDING MANUAL RETEST | ✓ |
| V9 | App does not freeze while transcribing; closing while recording stops safely | PENDING MANUAL RETEST | partial |
| V10 | No audio leaves the device (local-first) | PENDING MANUAL RETEST | ✓ |
| V11 | Save/reopen the project — committed dictation text persists | PENDING MANUAL RETEST | ✓ |
| V12 | Stop during Processing — no hang; status returns to off | PENDING MANUAL RETEST | ✓ |
| V13 | Switch project while recording — session stops; transcript is NOT committed into the other project | PENDING MANUAL RETEST | ✓ |
| V14 | Open the voice panel in macOS fullscreen — app does not minimize (embedded strip, no floating window) | PENDING MANUAL RETEST | partial |
| L1 | Backend selector shows Disabled / Local PC / Local LAN Server / Mock; default Disabled | PENDING MANUAL RETEST | ✓ |
| L2 | Start a Whisper server on another LAN machine (`docs/LOCAL_LAN_WHISPER.md`) | PENDING MANUAL RETEST | |
| L3 | Select **Local LAN Server**; enter the private LAN URL (e.g. `http://192.168.x.x:8765`) | PENDING MANUAL RETEST | ✓ |
| L4 | **Check LAN server** reports reachable | PENDING MANUAL RETEST | ✓ |
| L5 | Start → speak → Stop: segment goes to the LAN server; transcript appears in preview | PENDING MANUAL RETEST | ✓ |
| L6 | Commit inserts the LAN transcript at the cursor | PENDING MANUAL RETEST | ✓ |
| L7 | Turn the LAN server off → unreachable warning, no crash | PENDING MANUAL RETEST | ✓ |
| L8 | Enter a public URL (e.g. `https://example.com`) → blocked with the local-address warning | PENDING MANUAL RETEST | ✓ |
| L9 | No audio leaves the device except to the configured private LAN server | PENDING MANUAL RETEST | ✓ |
| L10 | Enable `--auth-token` on the server: missing token rejected (401), correct token accepted | PENDING MANUAL RETEST | ✓ |

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

**PENDING MANUAL RETEST.** Automated focused suites are green (419 passed), but
the manual UI checklist above has not been executed. **Do not tag** the Alpha RC
until the manual checklist is completed and this decision is updated to one of:

- ✅ **Ready to tag** — all blocker-criteria items PASS; only documented
  non-blocking issues remain.
- ⚠️ **Retest required** — partial/blocked items need re-running.
- ⛔ **Not ready to tag** — one or more release blockers FAIL.
