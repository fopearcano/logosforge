# User Guide

A tour of the Logosforge interface: the window layout, every navigation section,
the menus, the command palette, and the manuscript editor.

> Source: `storyplanner/ui/main_window.py` (shell and navigation) and
> `ui/writing_core_view.py` (editor).

---

## Window layout

The window has three regions:

- **Sidebar** (left) — navigation, grouped into sections; collapses to icons.
- **Content area** (centre) — the active view.
- **Assistant panel** (right) — the AI panel, toggleable (**Ctrl+\\**).

At the bottom of the sidebar are the appearance (theme) buttons and **Import**,
**Export**, and **Settings**.

---

## Navigation sections

The sidebar lists these destinations (top-level items and three collapsible
groups). All adapt to the project's [narrative engine](narrative-engines.md).

| Section | What it is |
|---------|-----------|
| **Projects** | Browse, open, and create projects. The app always opens here. |
| **Dashboard** | Project overview — stats, recent activity, current focus, surfaced narrative engine and writing format. |
| **Notes** | Free-form project notes, pinnable and linkable to scenes/PSYKE. |
| **Manuscript** | The continuous, format-aware writing editor (see below). |
| **Plan ▸ Outline** | The hierarchical outline tree (templates + AI generation). |
| **Plan ▸ Scenes** | Scene list + editor with planning fields and inline assistant. |
| **Plan ▸ Timeline** | Engine-aware timeline (chapters / screen time / reading flow / performance order / episodes). |
| **Plan ▸ Plot** | Multi-Plot — Grid / Timeline / Arc / Character views with shared filters. |
| **Structure ▸ Structure** | Scenes organized by beat in story order. |
| **Structure ▸ Acts** | Act distribution and breakdown. |
| **Structure ▸ Beats** | Beat counts and positions. |
| **Structure ▸ Arcs** | Character-arc view. |
| **Tags** | Tag frequency and usage. |
| **Graph** | The narrative graph and its lenses (see [graph.md](graph.md)). |
| **Analytics ▸ Health** | Story-health signals. |
| **Analytics ▸ Balance** | Character / arc balance. |
| **Analytics ▸ Pacing** | Scene-level pacing insights. |
| **Analytics ▸ Narrative** | The visual [Narrative Dashboard](narrative_dashboard.md). |
| **Adapt** | Adaptive-mode suggestions (Structure / Balance / Refinement). |
| **PSYKE** | The [Story Bible](psyke.md) editor. |
| **Stages** | [Narrative versioning & branching](structure-and-plot.md#stages--narrative-versioning--branching). |
| **Plugins** | Enable/disable and inspect [plugins](plugins.md). |
| **Assistant** | The [AI Assistant](ai-assistant.md) panel. |
| **Chat** | The persistent project [chat](ai-assistant.md#chat). |

Graphic Novel projects additionally expose the **Pages** canvas/editor for laying
out pages and panels.

The sidebar collapses to icons (**Ctrl+B**), and each group's expanded state is
remembered between sessions.

---

## Menus

| Menu | Highlights |
|------|-----------|
| **File** | New / Open / Save / Save As project, Move project to folder, Project Settings, Import, Export, Create Snapshot, Version History, Recent Projects, Exit. |
| **Edit** | Undo/Redo, Cut/Copy/Paste, Preferences (**Ctrl+,**), Grammar Check toggle, Grammar Language (Auto / English / Italian / Spanish / French / German). |
| **View** | Toggle Sidebar (**Ctrl+B**), Toggle Assistant Panel (**Ctrl+\\**), Focus Mode (**Ctrl+Shift+F**), Appearance (Dark / Light Green / Light Warm). |
| **Navigate** | Dashboard **Ctrl+1**, Manuscript **Ctrl+3**, Timeline **Ctrl+4**, Notes **Ctrl+5**, PSYKE **Ctrl+6**. |
| **AI** | Rewrite, Expand, Dialogue, Open Assistant. |
| **Plugins** | Plugin-contributed actions + Manage Plugins. |
| **Help** | About, Documentation. |

---

## The command palette

In the manuscript editor, type **`/`** at the start of a line to open the command
palette (`ui/command_palette.py`): a searchable popup of quick actions — New Scene,
New Chapter, Insert PSYKE Entry, the AI actions (Rewrite, Expand, Dialogue, Suggest
Beats), Style Improve, Voice Rewrite, and Focus Mode. Arrow keys navigate, Enter
runs, Escape closes.

---

## The manuscript editor

The **Manuscript** view (`ui/writing_core_view.py`) is a single continuous,
distraction-light editor where scenes flow inline in a centred column.

- **Format-aware blocks** — the toolbar's element combo (and **Ctrl+1…6**, or
  **Tab / Shift+Tab**) switches between the active [writing format](writing-formats.md)'s
  block types — e.g. scene heading / action / character / dialogue / parenthetical /
  transition for screenplay, or page / panel / description / caption / SFX for a
  graphic novel. Margins, caps, and spacing follow the format.
- **Focus mode** (**Ctrl+Shift+F**) — fades everything but the current line/
  paragraph, shows a word-count focus bar, and offers an optional typewriter
  (centre-cursor) mode.
- **Typography** — a font/size/colour picker and smart typography (curly quotes,
  em dashes, ellipses); a floating toolbar on selection for bold/italic/heading/
  blockquote plus the inline AI actions.
- **Live feedback** — PSYKE highlighting and hover previews; grammar, style, and
  voice underlines; the paragraph **energy gutter** in the left margin; and the
  [Auto-Link](auto_link.md) and [Context Assistant](context_assistant.md)
  suggestion banners. All of these are non-intrusive and never edit your text. See
  [writing-analysis.md](writing-analysis.md).
- **Autosave** — edits save on a short debounce, atomically; a status label shows
  the save state. See [data-model.md](data-model.md).
- **Inline AI** — select text for the floating edit bar (Rewrite / Expand /
  Dialogue → Replace / Insert / Cancel), or use the inline assistant panel for
  preset/custom actions and Suggest Beats. See [ai-assistant.md](ai-assistant.md).

---

## Themes & appearance

Three palettes ship — **Dark**, **Light (Green)**, **Light (Warm)** — selectable
from Settings, the View menu, or the sidebar. Your choice persists across sessions.
See [configuration.md](configuration.md).
