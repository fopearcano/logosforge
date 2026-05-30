# Export & Import

Logosforge keeps your working data in a local SQLite database, and lets you move
whole projects in and out as **JSON** plus export finished manuscripts to a range
of craft formats. Export is **format-aware**: the manuscript exporters dispatch on
the project's format into one of four renderers — prose, screenplay, stage script,
or graphic novel — so a screenplay exports with sluglines and dialogue blocks, a
graphic novel as a panel script, a stage script in playwriting layout, and so on.

> Source: `storyplanner/export.py` and `storyplanner/import_data.py`. The export
> menu is wired in `ui/main_window.py`.

---

## Project save / open (JSON)

A project is **saved** by serializing it to a JSON file and **opened** by importing
that file. The on-disk project format is therefore plain, human-readable JSON.

- `export.export_json(db, project_id)` serializes the full project document
  (`_gather_project_data`) with these top-level keys:
  - `project` — `title`, `description`, and all three format fields:
    `format_mode` (legacy), `narrative_engine`, `default_writing_format`;
  - `characters`, `places` — name + description;
  - `notes` — title, content, tags, pinned, plus `psyke_links` / `scene_links`
    stored **by name/title** (so they round-trip);
  - `scenes` — full scene records including planning fields and the
    screenplay/stage metadata and per-scene character states;
  - `psyke_entries` — name, type, aliases, notes, `is_global`, structured
    `details`, `related_entries`, `typed_relations`, and `progressions`;
  - `outline` — the recursive node tree (title / description / children);
  - `continuity` — extracted continuity items;
  - `quantum_state` — included only when present.
- `import_data.import_json(db, data)` validates the document
  (`validate_import_data`) and recreates the project, re-resolving the name/title
  links.

In the UI, **Save / Save As / Open** use the `JSON (*.json)` filter and append
`.json` automatically. The last opened project path is remembered and re-loaded on
the next launch. (The working SQLite store, `storyplanner.db`, is a separate
implementation detail; JSON is the portable, version-controllable project file.)

See [data-model.md](data-model.md) for how saves are made cloud-safe (atomic
writes, lock sidecars, conflict copies) and versioned (snapshots).

---

## Manuscript export formats

From **Export**, the manuscript can be written to:

| Format | Filter | Entry point |
|--------|--------|-------------|
| PDF | `PDF … (*.pdf)` | `export_pdf` |
| Microsoft Word | `DOCX … (*.docx)` | `export_docx_manuscript` |
| Fountain (screenplay) | `Fountain (*.fountain)` | `export_fountain` |
| Final Draft | `Final Draft (*.fdx)` | `export_fdx` |
| HTML | `HTML (*.html)` | `export_html` |
| Markdown | `Markdown (*.md)` | `export_markdown` |
| CSV (scenes) | `CSV – Scenes (*.csv)` | `export_csv_scenes` |
| JSON (full project) | `JSON (*.json)` | `export_json` |

### How the format is chosen

The DOCX, PDF, HTML, and plain-text exporters resolve the project's format with
`_get_fmt()` (the project's `format_mode`) and route to one of **four manuscript
renderers**:

| Project format | Renderer | Notes |
|----------------|----------|-------|
| novel (prose) | novel | Chapter headings, italic scene titles, prose body. |
| screenplay | screenplay | Sluglines (`INT. PLACE — TITLE`), action, character/dialogue blocks. |
| **series** | **screenplay** | Series **reuses the screenplay renderer**. |
| stage_script | stage script | Act/scene headings, centred character names, dialogue, stage directions. |
| graphic_novel | graphic novel | Page / panel / description / caption layout. |

The screenplay, series, stage-script, and graphic-novel formats are treated as
**script formats** (`_is_script_format`), which selects a **monospace** typeface;
prose uses a serif one:

| Output | Prose font | Script font |
|--------|-----------|-------------|
| DOCX | Times New Roman | Courier New |
| PDF | Times-Roman | Courier |
| HTML | `Times New Roman, Georgia, serif` | `Courier New, Courier, monospace` |

### Per-format detail

- **JSON** — the full project document described above (`export_json`).
- **Markdown** — `export_markdown` writes a complete project dump: title and
  description, then Characters, Places, Notes, and Scenes (each scene with its
  metadata, character states, and content body). `export_outline_markdown` writes
  an outline-only variant, scenes grouped by chapter, without the prose body.
- **CSV** — `export_csv_scenes` emits one row per scene with the columns
  `order_index, title, summary, synopsis, goal, conflict, outcome, beat, tags, act,
  chapter, plotline, characters, places`.
- **Fountain** — `export_fountain` produces standard Fountain screenplay markup
  with a title page, for any screenwriting tool that reads `.fountain`.
- **Final Draft (FDX)** — `export_fdx` produces Final Draft XML
  (`<FinalDraft DocumentType="Script">…`).
- **DOCX / PDF / HTML** — `export_docx_manuscript`, `export_pdf`, and `export_html`
  each render through the four format-specific renderers above
  (`_docx_*` / `_pdf_*` / `_html_*`), so typography and block structure match the
  form.

Two plain-text helpers also exist and are used internally / by tests:
`export_manuscript` (force the prose renderer), `export_screenplay` (force the
screenplay renderer), and `export_formatted_text` (use the project's own format).

---

## Graphic Novel image-prompt export

Graphic Novel projects can export **text-to-image generation prompts** from their
page/panel data — for use in tools like ComfyUI or other Stable-Diffusion
front-ends.

> Source: `storyplanner/graphic_novel_ai_export.py`.

For each panel, `build_gn_panel_prompt_package()` assembles a structured packet:
a composed positive prompt (description + action + shot + camera + character
visuals + location + tone + motifs + style), a negative prompt, the characters /
locations / objects involved (matched against **PSYKE Visual Memory** for
silhouettes, colour identity, costume state, designs, continuity), visual motifs,
style notes (from the project's GN style profile: art style, linework, palette,
rendering, aspect ratio), continuity notes, framing metadata, and **warnings**
about missing visual data. Packets export as JSON (`package_to_json`) or a
human-readable Markdown sheet (`package_to_markdown`), per panel or per page.

Actual image generation is out of scope — `comfyui_available()` returns false and
`send_to_comfyui()` is a stub reserved for a future connector. The assistant can
answer "create an image prompt for this panel/page" and "what visual data is
missing before generating?" using these hooks.

---

## Engine review reports

Alongside file export, each engine exposes deterministic **review reports** you can
pull into Chat as Markdown (see [writing-formats.md](writing-formats.md) for the
mapping). For example `/gn check|page|panel|rhythm|page-turn|motifs|continuity`
(`graphic_novel_review.py`) and `/series check|arcs|continuity|cliffhanger|payoff`
(`series_review.py`) produce grouped, grouped-by-theme findings; stage-script
checks live in `stage_script_review.py`. The Graphic Novel engine can also generate
an editable manuscript scaffold from its pages/panels
(`graphic_novel_manuscript.generate_draft`).
