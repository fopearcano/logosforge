# Logosforge Documentation

**Logosforge** is a narrative operating system for structured writing — a PySide6
desktop app with a SQLite backend that unifies **writing, structure, and AI** in
one place. It serves novelists, screenwriters, playwrights, comics writers, and
showrunners through five interchangeable narrative engines, a deep Story Bible
(PSYKE), a branch-exploring Quantum Outliner, and a context-aware AI assistant that
never edits your story without confirmation.

This is the complete documentation set. New here? Start with
**[Getting Started](getting-started.md)**.

---

## Getting started

| Doc | What's inside |
|-----|---------------|
| [Getting Started](getting-started.md) | Install, run, connect an AI provider, create your first project. |
| [User Guide](user-guide.md) | The full UI tour — window layout, every navigation section, menus, command palette, and the manuscript editor. |

## Core concepts

| Doc | What's inside |
|-----|---------------|
| [Architecture](architecture.md) | How the app is built — tech stack, startup, module map, design patterns, the engine-vs-format split. |
| [Narrative Engines](narrative-engines.md) | The five engines (Novel, Screenplay, Graphic Novel, Stage Script, Series) and how they shape every view. |
| [Writing Formats](writing-formats.md) | The manuscript block grammars and typography — the rendering axis, orthogonal to engines. |

## Story Bible & AI

| Doc | What's inside |
|-----|---------------|
| [PSYKE — The Story Bible](psyke.md) | Entries, relations, progressions, temporal state, engine-specific memory, and the PSYKE console. |
| [AI Assistant](ai-assistant.md) | Providers, the layered context pipeline, assistant/counterpart/inline modes, chat, memory, adaptive mode, and the safe Connector. |
| [QUANTUM Outliner](quantum-outliner.md) | Branch generation, the five-factor scoring model, goals & Pareto, collapse, and the quantum timeline. |

## Structure, plotting & analysis

| Doc | What's inside |
|-----|---------------|
| [Structure & Plotting Tools](structure-and-plot.md) | Controlling Idea, Outline, Story Grid, Multi-Plot, Timeline, engine Plot grids, Stages (versioning/branching), scenes. |
| [The Narrative Graph](graph.md) | Nodes/edges, engine-specific lenses, Story Gravity, meaning/flow, and graph-driven suggestions. |
| [Writing-Quality Analysis](writing-analysis.md) | Style, voice, grammar, paragraph energy, pacing, balance, health, and the unified editor underlines. |
| [Structural Intelligence](structural_intelligence.md) | Seven PSYKE-driven structural detectors. |
| [Narrative Dashboard](narrative_dashboard.md) | The four-panel visual story-intelligence dashboard. |
| [Context Assistant](context_assistant.md) | Proactive, rate-limited writing hints. |
| [Auto-Link](auto_link.md) | Suggest-only manuscript ↔ PSYKE linking. |
| [IRRATIONAL Mode](irrational_mode.md) | The opt-in PSYKE rule-disruption / surreal-provocation engine. |
| [Writing Methods (RAG)](Writing-Methods_RAG.md) | The editable story-structure knowledge base the Quantum Outliner retrieves from. |

## Data, export & configuration

| Doc | What's inside |
|-----|---------------|
| [Data Model & Persistence](data-model.md) | The SQLite schema, project files, autosave, cloud safety, versioning, and the event bus. |
| [Export & Import](export-import.md) | JSON project files and manuscript export (PDF, DOCX, Fountain, FDX, HTML, Markdown, CSV), plus GN image-prompt export. |
| [Configuration & Settings](configuration.md) | Every setting key, AI providers, the Connector, themes, and project settings. |

## Extending

| Doc | What's inside |
|-----|---------------|
| [Plugin Development Guide](plugins.md) | Both plugin types (external menu plugins and internal analysis plugins), the architecture, and the bundled plugins (Go McKee, Idea di Controllo, PSYKE Outline Templates). |

---

## Two axes worth understanding first

Almost everything in Logosforge follows from one idea: **reasoning** and
**rendering** are separate, composable axes.

- A **[Narrative Engine](narrative-engines.md)** decides *how the story is reasoned
  about* — its structural units, what Plot/Timeline/Graph default to, the
  assistant's priorities, and the review checks.
- A **[Writing Format](writing-formats.md)** decides *how the manuscript renders and
  exports* — block element types and typography.

Pick them per project; pair them freely. That orthogonality is why one app can be a
serious tool for a novel, a screenplay, a graphic novel, a stage play, and a series
without compromise.
