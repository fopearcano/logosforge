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
- **Graphic Novel — Manuscript & Pages share one body:** the Pages section now
  edits the same scene body as the Manuscript (`Scene.content` → Pages → Panels:
  visual / caption / dialogue / SFX / notes), with collapsible panel cards. Edits
  round-trip between the two; Pages/Panels are script structure, not image
  generation.

**Verification:** the final global multi-mode integrity audit (Alpha Release Gate)
returned **A**. Focused gate `tests/test_alpha_release_gate.py` = **35 passed**;
the broad certification sweep = **1527 passed, 0 failures**
(see `docs/ALPHA_TEST_COMMANDS.md`).

**Still deferred / out of scope:** ComfyUI / image generation, Canvas Plot
(hidden), production scheduling, writers-room / showrunner automation, and a real
separate Season/Episode storage hierarchy. Persistent serialized-story relation
links are reported but not yet persisted. See `docs/KNOWN_LIMITATIONS_ALPHA.md`,
`docs/ALPHA_RC_STATUS.md`, and `docs/ALPHA_RC_CHECKLIST.md`.

> ⚠️ **This is Alpha software, not a final production release.** Back up your work.

Thanks for testing Logosforge. Please report what breaks.
