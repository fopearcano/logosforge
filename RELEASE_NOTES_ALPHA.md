# Logosforge — Private Alpha (0.9.0-alpha)

A local-first **narrative operating system** that unifies writing, structure and
AI in one desktop app. This is an early **private alpha** — feature-frozen and
focused on stability. Expect rough edges, and **back up your work**.

## What you can do

- Write in a distraction-free **Manuscript** editor across five **Writing Modes**
  (Novel, Screenplay, Graphic Novel, Stage Script, Series).
- Plan with **Outline / Plot / Timeline / Graph** and a **PSYKE** story bible
  (characters, places, objects, lore, themes, relations).
- Get AI help from the **Assistant** (chat, critique, inline edits, Counterpart,
  Quantum outliner) and the inline **Logos** layer — always **propose-then-
  confirm**, never silent edits.
- **Export** to Markdown, TXT, Fountain, FDX, HTML, JSON, CSV (and PDF/DOCX with
  optional libraries).

## Install & run

Python **3.10+**:

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 run.py
```

Optional, only for those formats: `pip install reportlab` (PDF),
`pip install python-docx` (DOCX). See `docs/USER_GUIDE_ALPHA.md`.

## ⚠️ Backup warning

This is alpha software. Your work lives in a local database with autosave and
version snapshots, but **please back up**: use **File → Export → Full Project
(JSON)** regularly and keep copies. Restore loads a snapshot as a *new* project
(it never overwrites your current one). See `docs/BackupRestore.md`.

## AI setup (optional)

The editor works without AI. For AI features, open **Assistant → Settings** and
pick a provider:

- **Local:** LM Studio (`http://localhost:1234/v1`) or Ollama
  (`http://localhost:11434/v1`) — no key.
- **Cloud:** OpenAI / Anthropic / OpenRouter — paste your API key.

Set the model (custom names allowed) and a **timeout** (local models are slow —
the default is 300s). Keys are never written to your project files or exports.
Step-by-step: `docs/AI_SETUP.md`. Stuck? `docs/TROUBLESHOOTING.md`.

## Known limitations

- **PDF/DOCX** need optional libraries; **FDX/HTML** and the **API LAN/remote**
  modes are experimental.
- **Knowledge Graph, Semantic Continuity, Decision Radar, Guided Workflows** ship
  as services surfaced through Logos/Assistant — **no dedicated UI panel yet**.
- Plot/Timeline are derived from scene fields; grammar is basic.
- Single-user, **local-only** (no cloud sync or collaboration).

Full list: `docs/KNOWN_LIMITATIONS_ALPHA.md`.

## Recommended first test workflow

1. **New Project** → choose a **Writing Mode** (try Novel).
2. Write a couple of **scenes** in the Manuscript.
3. Add a **PSYKE** character; search it in the bottom console.
4. Generate an **Outline** via the Assistant (review and confirm it).
5. Configure a **provider** and ask the Assistant a question; toggle **Logos** ON
   for inline suggestions, then OFF.
6. **Export** the manuscript (Markdown or Fountain) and a **Full Project** backup.
7. **Close and reopen** the app; **reload** the project and confirm everything is
   intact.

## Alpha Release Candidate — multi-mode gate (2026-06-08)

This RC completes and stabilizes the five **Writing Modes** on the single
**universal Manuscript** (the editor adapts by `writing_mode`; canonical structure
stays Project → Act → Chapter → Scene):

- **Screenplay** (blocks + Fountain foundation), **Graphic Novel** (Page/Panel
  script), **Stage Script** (stage blocks), and **Series** (teleplay blocks;
  Act↦Season/Arc and Chapter↦Episode are display labels only) each add a planning
  pipeline, deterministic intelligence checks, Counterpart/Reflection, a controlled
  rewrite (preview → diff → confirmed apply), cross-unit continuity, and a Review
  Dashboard. **Novel** prose is unchanged (primary unit = Chapter).
- Every mutating AI action is **propose-then-confirm** (preview + Controlled
  Apply); deterministic checks never call a provider; actions are **mode-gated**.
- **Series Navigator** (left **Plan** group, Series-only): a read-only tree over
  Season/Arc → Episode → Scene with A/B/C buckets from the Episode Beat Plan; it
  navigates to Outline/Manuscript and never mutates data.
- **Export dependencies:** `requirements.txt` now lists `reportlab` (PDF) and
  `python-docx` (DOCX); a normal install supports every export format, with the
  same graceful fallback if a library is missing.
- **Graphic Novel — Pages/Panels in the Outline + Manuscript (standalone Pages
  disabled):** the separate left-panel **Pages** route was fullscreen-hostile, so it
  is **disabled for Alpha** (hidden; inert route). Graphic Novel Page/Panel management
  now lives in **two mirrored surfaces** over the shared scene body (`Scene.content`):
  the **Outline** becomes the GN Page/Panel navigator — a **Scenes** view
  (`Act → Chapter → Scene → Page → Panel`) and a chapter-level **Pages** cross-reference
  view (panels grouped across a chapter's scenes by page number) with a selected-Panel
  editor (**Visual / Caption / Dialogue / SFX / Notes**), add/move/delete, and
  assign-panel-to-page — and the **Manuscript** is the **comics script editor**
  (Superscript-style): the scene flows as a script document — PAGE headings,
  then one large free-typing script block per panel with labeled sections
  (**Visual / Caption / Dialogue / SFX / Notes**; labels optional, unlabeled
  text is the Visual). Blocks parse back into the structured model on commit;
  line breaks are preserved; numbers stay auto-numbered; Outline Panel
  double-click deep-links to the script block. Not a tree, not a form.
  Model: Chapter owns Pages, Scene owns Panels, Panel assigned to a Page, Scene can
  span Pages. Pages/Panels are script structure, not image generation; this is the
  future anchor point for visual-production integrations. Both surfaces are embedded
  child widgets (no separate route, no top-level window), addressing the earlier macOS
  fullscreen minimize. See `docs/KNOWN_LIMITATIONS_ALPHA.md`.
- **Local voice-to-script (MVP, off by default):** an opt-in, **local-first**
  dictation foundation (`enable_voice_mode`; backend mode defaults to Disabled) —
  buffered microphone capture, simple pause detection, transcript preview, and
  **manual plain-text commit** at the editor cursor. Two backends: **Local PC**
  (`faster-whisper` + `sounddevice`, optional installs; local model path required,
  **no automatic downloads**) and **Local LAN Server** (capture stays local;
  finalized segments go only to a Whisper server you configured on the **trusted
  local network** — private/loopback addresses enforced, public URLs / ngrok /
  tunnels **blocked**, redirects refused; an opt-in companion server script ships
  at `scripts/local_whisper_server.py`). **No cloud speech API, no OpenAI
  Realtime; audio never leaves the device/trusted LAN.** No voice commands, no
  automatic dialogue/action classification (deferred hooks exist). View → Voice
  Dictation (Ctrl/Cmd+Shift+V) toggles a **floating, modeless, resizable**
  dictation window (parented to the main window; one instance; Hide/close/Esc
  hide it with the transcript preview preserved; hiding while recording stops
  the session safely; commit stays manual, auto-commit off by default). See
  `docs/VOICE_MVP.md` + `docs/LOCAL_LAN_WHISPER.md`.
- **General Preferences usable on small screens:** the Preferences dialog now
  scrolls its content vertically (sticky Close row outside the scroll area, so
  the bottom controls are always reachable) and clamps its height to ~85% of
  the available screen.

**Final Alpha RC integration gate (2026-06-10): PASSED** — authoritative
sweep 1527 + voice stack 392 + GN/Series/export 392 = **2311 passed, 0
failed**; no blockers, no production changes; manual smoke test (V1–V49)
remains before tagging. See `docs/ALPHA_RC_STATUS.md`.

**Verification:** the final global multi-mode integrity audit (Alpha Release Gate)
returned **A**. Focused gate `tests/test_alpha_release_gate.py` = **35 passed**;
the broad certification sweep = **1527 passed, 0 failures**
(see `docs/ALPHA_TEST_COMMANDS.md`).

**Still deferred / out of scope:** ComfyUI / image generation, Canvas Plot
(hidden), production scheduling, writers-room / showrunner automation, and a
Season/Episode-aware *global* Outline (the new hierarchy lives in the Series
Navigator — see below). Persistent serialized-story relation links are reported
but not yet persisted. See `docs/KNOWN_LIMITATIONS_ALPHA.md`,
`docs/ALPHA_RC_STATUS.md`, and `docs/ALPHA_RC_CHECKLIST.md`.

## Series — real Season → Episode → Act → Chapter → Scene hierarchy (Phase 1)

The Series Alpha shortcut (Act = Season, Chapter = Episode) is replaced by a real
hierarchy: **Season** and **Episode** are now **stored rows**, each Series scene
links to its Episode (`Scene.episode_id`, a nullable column — `NULL` everywhere
else, so nothing changes for Novel / Screenplay / Graphic Novel / Stage Script),
and the Act → Chapter → Scene outline is **episode-scoped**.

- **Series Navigator is now the structural editor** (Series-only, left **Plan**
  group): create / rename / delete / move Seasons, Episodes, internal
  Acts/Chapters and Scenes; move a scene between Episodes; per-episode A/B/C
  buckets; an "Unassigned Scenes" bucket so no body is hidden. Deleting a
  Season/Episode **unlinks** its scenes (it never deletes a body).
- **Legacy Series projects keep working** and offer a one-click, **confirmed,
  non-destructive Convert to Season/Episode** (old Act → Season title, old Chapter
  → Episode title; bodies, labels and order untouched).
- **Phase-1 boundary:** the *global* Outline / Manuscript / Timeline stay
  episode-agnostic (canonical flat Act → Chapter → Scene); the Navigator is the
  canonical Season/Episode surface. Export adds a Series Markdown outline
  (structure + bodies only — never settings or API keys).
- **Verification:** `tests/test_series_hierarchy.py` = **70 passed**; the legacy
  `tests/test_series_navigator.py` stays green (**26 passed**); broad cross-mode +
  gate sweep clean. See `docs/SERIES_ARCHITECTURE_CORRECTION_REPORT.md` §10.

> ⚠️ **This is Alpha software, not a final production release.** Back up your work.

Thanks for testing Logosforge. Please report what breaks.
