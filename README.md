<p align="center">
  <img src="assets/icon.png" alt="Logosforge" width="128" height="128">
</p>

<h1 align="center">Logosforge</h1>

<p align="center"><strong>A narrative operating system for structured writing.</strong></p>

<p align="center">Plan, write, and evolve your story with AI — without losing control.</p>

---

## What it is

Logosforge unifies **writing, structure, and AI** in one place. Editors let you write but not structure; planners organize but don't help you write; AI tools generate text but ignore narrative intent. Logosforge does all three together — a PySide6 desktop app with a SQLite backend, built for novelists, screenwriters, and narrative designers who want deep structural awareness alongside their prose.

## Narrative Engines

Pick a **Narrative Engine** per project — it shapes how every section (Outline, Plot, Timeline, Graph, Assistant) reasons about your story:

- **Novel** — Parts / Chapters / Scenes
- **Screenplay** — Acts / Sequences / Scenes / Beats
- **Stage Script** — Acts / Scenes / Beats / Entrances·Exits / Cues
- **Graphic Novel** — Issues / Chapters / Pages / Panels (page canvas, panel editor, visual-motif graph, image-prompt export)
- **Series** — Seasons / Episodes / A·B·C plots / Arcs

A separate **Writing Format** controls how the manuscript renders/exports (Prose, Screenplay, Stage Script, Graphic Novel Script, …).

## Highlights

- **Manuscript** — distraction-free editor, focus mode, format-aware blocks, DOCX/text export.
- **Structure** — Outline (AI-generated, engine-aware, template-driven), Story Grid, Multi-Plot, Timeline, act/beat analysis.
- **PSYKE Story Bible** — characters, places, objects, themes, lore, relations, temporal progressions, and engine-specific memory (e.g. Graphic Novel visual identity).
- **AI Assistant** — engine-aware critique, inline editing, COUNTERPART mode, adaptive modes, a layered context pipeline, and safe propose-then-confirm actions (e.g. generate a structured outline).
- **Graph** — focused, filterable views of motifs, characters, causality, and continuity.
- **Local or cloud AI** — any OpenAI-compatible endpoint (LM Studio, Ollama, OpenAI, …).

## Install & Run

**Requirements:** Python 3.10+ and pip.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 run.py
```

**Windows (PowerShell):**

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

**Run the tests:**

```bash
python -m pytest tests/
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| UI | PySide6 (Qt 6) |
| Data | SQLModel + SQLite |
| AI | OpenAI-compatible API (local or cloud) |
| Architecture | MVC with layered context engines |
