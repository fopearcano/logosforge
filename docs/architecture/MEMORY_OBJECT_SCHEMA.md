# Memory Object Schema

> Phase 1 — canonical schema **direction**. No tables or migrations are
> created by this document.

## Canonical memory object

A memory object is a single curated, scoped, versioned fact/decision/rule.

| Field | Meaning |
|-------|---------|
| `id` | Stable unique id. |
| `scope` | `user` · `project` · `workspace` · `assistant` · `device`. |
| `type` | see the type enum below. |
| `content` | The memory's text/body (structured payload may live in a sub-object). |
| `source_event` | Id of the originating event-log entry (provenance). |
| `project_id` | Owning project (required when `scope = project`). |
| `user_id` | Owning user (required when `scope = user`). |
| `workspace_id` | Owning workspace (required when `scope = workspace`). |
| `confidence` | 0.0–1.0 writer confidence. |
| `status` | `active` · `proposed` · `speculative` · `deprecated` · `superseded` · `contradicted`. |
| `created_at` / `updated_at` | Timestamps. |
| `supersedes` | Id this object replaces (if any). |
| `contradicted_by` | Id(s) that contradict this object (if any). |
| `tags` | Free-form labels. |
| `entities` | Linked entities (character/scene/repo/decision ids). |
| `visibility` | Who may see it (private / project / workspace / shared). |
| `sync_state` | `local_only` · `pending_sync` · `synced` · `conflict`. |
| `version` | Monotonic version for sync/audit. |

### `type` enum

`preference` · `project_decision` · `correction` · `procedural_rule` ·
`session_summary` · `character_fact` · `continuity_fact` ·
`architecture_decision` · `repo_decision` · `workflow_rule` ·
`assistant_rule` · `mistake_correction` · `deferred_feature` ·
`limitation` · `model_preference` · `provider_config_note` ·
`release_blocker_rule` · `speculative_idea` · `other`.

## Three storage layers

1. **Event Log** — raw interactions, edits, decisions, assistant sessions.
   Append-only provenance. Not used directly as fact.
2. **Curated Memory Objects** — structured facts/decisions/preferences/rules
   **extracted** from events (the table above).
3. **Vector / Semantic Index** — searchable embeddings built from curated
   memory and **selected** project content (not the whole transcript).

## Writer invariants

- The assistant must **not** save everything automatically as fact.
- **Speculative ideas** are stored with `status = speculative`, never as
  `active` fact.
- **Old decisions** are marked `superseded` (with `supersedes`/`version`),
  **not** deleted silently.
- **Contradictions** are detected and surfaced/reconciled before an object
  becomes `active`; the loser is marked `contradicted` / `superseded` with
  `contradicted_by` set.
- **Secrets, raw audio paths, and transient debug logs are never stored**
  as memory objects (also enforced by the writer policy in
  `ASSISTANT_MEMORY_SPEC.md`).

## Scope-defaulting (cross-ref)

`project_decision`/`character_fact`/`continuity_fact` → `project` scope by
default; `preference`/`model_preference` → `user`; `assistant_rule`/
`workflow_rule`/`mistake_correction`/`architecture_decision`/`repo_decision`/
`release_blocker_rule` → `assistant`; device-only operational notes →
`device`. See `ASSISTANT_MEMORY_SPEC.md` §memory writer policy.
