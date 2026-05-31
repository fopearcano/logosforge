# Export

StoryPlanner exports project data in several formats (`storyplanner/export.py`).
Project metadata (JSON/Markdown/data export) always includes the canonical
`writing_mode` (see docs/WritingModes.md).

## Screenplay export (Phases 10A–10F)

For screenplay projects the exporters are screenplay-aware: scene bodies are
parsed into blocks (`screenplay_blocks`) so character cues / transitions / scene
headings are uppercased and parentheticals normalized — **text-preserving**.

### Targets

| Function | Output |
|---|---|
| `export_screenplay` | screenplay plain text (slug + classified body) with a `Writing Mode` header |
| `export_screenplay_fountain` / `export_screenplay_fountain_result` | **canonical** `.fountain` (Phase 10G) via `screenplay_fountain.serialize_screenplay_to_fountain` — title page, forced elements, grouped dialogue, option-gated notes; result carries `.fountain` filename + warnings |
| `export_fountain` | screenplay projects now delegate to the canonical serializer; other modes keep the legacy multi-mode Fountain text path |
| `export_fountain_validation_json` | Fountain validation report (schema_version / writing_mode / exported_at / filename) |
| `export_screenplay_preview_html` | conservative screenplay **preview HTML** (not page-accurate) |
| `export_screenplay_export_validation_json` | export-readiness report (`schema_version`, `writing_mode`, `exported_at`) |
| `export_screenplay_diagnostics_json` / `export_screenplay_graph_json` / `export_story_links_json` / `export_setup_payoff_report_json` / `export_subtext_report_json` | structured screenplay reports |
| `export_pdf` / `export_fdx` | **basic** existing exporters — *not* page-accurate / production drafts |

### Title page metadata

Stored in project settings (`screenplay_title_page`; no schema change) via
`screenplay_render.get_title_page` / `set_title_page`. Fields: `title, credit,
author, source, draft_date, contact, notes`. Falls back to the project title.
Included at the top of Fountain export when `include_title_page` is on.

### Export preferences

`screenplay_render.get_export_prefs` / `set_export_prefs` (project settings,
conservative defaults): `show_notes_in_export` (default **off** — production
export hides notes), `uppercase_scene_headings`, `uppercase_character_cues`,
`include_title_page`, `include_diagnostics_report`, `export_target`
(`fountain` / `plain_text` / `preview_html`), `approximate_page_estimate`.

### Render model

`screenplay_render.build_render_document` produces a serializable
`ScreenplayRenderDocument` (blocks with style + `export_text`, title page,
**approximate** page/minute estimate, warnings) — the foundation for future
PDF/FDX. Read-only, no LLM.

### Export readiness validation

`screenplay_export_validation.validate_screenplay_export` returns a deterministic
report separating **blocking errors** (empty screenplay, unsupported target)
from **warnings** (missing title/headings, orphan dialogue/parentheticals) and
**suggestions** (note inclusion). It blocks export only when truly unsafe. Logos
surfaces this via `Validate Screenplay Export` / `Generate Export Readiness
Report` / `Check Production Polish` (deterministic, no LLM). The Assistant gets a
capped `[Screenplay Export Readiness]` block.

## Approximate vs professional

Page/minute counts are **approximate** (~1 page/minute, ~55 lines/page) and
labelled as such — never professional page-accurate pagination.

## Fountain vs Markdown (Phase 10G)

**Fountain (`.fountain`) is the canonical screenplay interchange format** — it is
screenplay-specific markup, *not* generic Markdown. The generic `export_markdown`
remains for documents/outline/notes and is a **separate serializer**; screenplay
export never uses it. `screenplay_fountain` also provides a Fountain **parser**
(`parse_fountain_to_screenplay_blocks`) and roundtrip (blocks → `.fountain` →
blocks preserves standard elements + title page); the parser is exposed as a
service (import UI is deferred to 10H).

## Deferred to Phase 10H

- True page-accurate PDF pagination + production-grade FDX.
- Title-page / export-preferences **editor UI** (storage + service API exist;
  Qt widgets deferred).
- Fountain **import UI** (parser round-trip exists for notes/elements; project
  import UI is deferred).
- Locked production pages, revision colors, production drafts (out of scope).

## Limitations

Screenplay block types are derived from flat scene text (not persisted), so
export classification is heuristic; a hand-typed novelistic block may export as
action. Novel and other-mode exports are unchanged.
