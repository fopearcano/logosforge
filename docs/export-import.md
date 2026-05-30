# Export & Import

Logosforge keeps your working data in a local SQLite database, and lets you move
whole projects in and out as **JSON** plus export finished manuscripts to a range
of craft formats. Export is **engine-aware**: a screenplay exports with sluglines
and dialogue blocks, a graphic novel as a panel script, a stage script in
playwriting layout, and so on.

> Source: `storyplanner/export.py` and `storyplanner/import_data.py`. The export
> menu is wired in `ui/main_window.py`.

---

## Project save / open (JSON)

A project is **saved** by serializing it to a JSON file and **opened** by importing
that file. The on-disk project format is therefore plain, human-readable JSON.

- `export.export_json(db, project_id)` produces the full project document —
  project metadata, characters, places, notes, scenes, PSYKE entries (with
  relations and progressions), outline, continuity, and quantum state.
- `import_data.import_json(db, data)` validates the document
  (`validate_import_data`) and recreates the project, resolving links by name/title.

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

The PDF, DOCX, and HTML exporters each have per-engine renderers (novel /
screenplay / stage script / graphic novel) so the typography and block structure
match the form. Additional helpers exist for outline-only Markdown
(`export_outline_markdown`) and plain formatted text (`export_formatted_text`,
`export_manuscript`).

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
