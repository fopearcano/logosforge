# Memory Privacy & Governance

> **Phase 7 — governance specification. No code is changed by this document.**
> It states the privacy and governance rules the memory system and the future
> Memory Review UI must uphold. Most are **already enforced** in code today
> (`MemoryWriterPolicy`, `MemoryCandidateReviewService`, `AssistantContextBuilder`,
> the disabled sync/GitHub services); this doc makes them the explicit contract.

Principle: **the model generates; LogosForge remembers.** Memory is the user's,
held by LogosForge — never by a model provider — and the user is always in
control of what becomes durable.

---

## Governance rules

1. **No raw chat spam as durable fact.** Only explicitly *marked* spans become
   candidates; everything else is discarded. (`candidates.py` marker heuristic.)
2. **No raw audio storage.** Dexter works on transcripts; raw audio is never a
   memory object. (`MemoryWriterPolicy` forbidden patterns.)
3. **No API keys** stored or shown. (Forbidden-content guard + redaction.)
4. **No provider secrets** stored or shown.
5. **No private logs by default** — raw event logs are not durable memory and
   are shown only via a redacted source preview, opt-in.
6. **User approval for durable memory** — nothing becomes `active` without an
   explicit `review.approve(...)`.
7. **Scope clarity before approval** — a candidate's scope (and required
   `project_id`/`user_id`/`workspace_id`) must be unambiguous; ambiguous-scope
   candidates carry a warning and cannot be silently misfiled.
8. **Project facts stay project-scoped** (`scope=project`).
9. **Assistant rules stay assistant-scoped** (`scope=assistant`).
10. **User preferences stay user-scoped** (`scope=user`).
11. **Workspace memories require a permission model** (future) before sharing.
12. **Contradictions must be visible** — surfaced, never hidden or auto-resolved.
13. **Superseded memories must not silently disappear** — retained, linked, and
    auditable (`supersedes`, `memory_relations`, `status=superseded`).
14. **Rejected candidates remain auditable** if policy allows (status →
    `rejected`; source event kept).
15. **GitHub export is explicit, preview-first, and optional** — never
    automatic. (`GITHUB_EXPORT_STRATEGY.md`.)
16. **Cloud sync respects user/account/workspace permissions** (future);
    disabled until accounts exist. (`SYNC_STRATEGY.md`.)
17. **Memory export supports redaction** — secrets / raw-audio / unrelated
    project data are stripped before any export or display.
18. **The user can always inspect what the assistant remembers** — Memory
    Review provides full visibility into active + candidate + archived memory,
    per scope.

## The two-memory-systems boundary (hard rule)

Project Memory (the *story* — characters, continuity, plot, codex) and
Assistant Meta-Memory (how *Jordan* works — rules, corrections, workflow) are
**distinct systems** and must never be mixed in storage, retrieval, the prompt,
the UI, or any export. This is enforced today by `MemoryWriterPolicy.validate_scope`
and by the separate `ContextBundle` sections.

## Sensitive-content handling

- The writer policy rejects obvious secrets (`sk-…`, `api_key:`…), raw-audio
  paths (`*.wav/.mp3/…`), and transient debug (`traceback`, `stack trace`)
  **before** any write.
- The Review UI shows a **sensitive-content warning** state and blocks approval
  until the user acknowledges, for anything that *looks* sensitive.
- All display/export passes content through redaction (`[redacted]`), so a
  secret that ever slipped in is never surfaced.

## Auditability

- `version`, `created_at`, `updated_at`, the event log, and `memory_relations`
  provide an append-only history. Edits require a reason; supersede/reject keep
  the prior object. **No destructive delete** exists in the MVP store contract.

## Data-residency posture

- **Local-first**: by default memory lives only on the user's device
  (`~/.storyplanner/logosforge_memory.sqlite3`, git-ignored), created only when
  a store is explicitly instantiated.
- **Cloud** (future/pro) is opt-in and permissioned; **GitHub** (optional) is a
  preview-first manual mirror. Model providers are **never** a memory store.

---

**Reaffirmed:** the model generates; LogosForge remembers and retrieves;
providers are replaceable backends, not memory; the user controls durable
memory; Jordan is memory-grounded, not conscious. **No implementation here.**


## Direction Correction — Memory Review is optional & exception-based

> **This section supersedes any earlier wording implying every memory must be
> approved in this UI.**

The **default** memory experience is the automatic, policy-governed pipeline
(`MEMORY_ARCHITECTURE.md` → *Direction Correction*): safe, high-confidence,
durable memory **auto-saves as active**; only uncertain / sensitive /
contradictory / scope-ambiguous memory is flagged. **Memory Review is therefore
an optional audit / control / exception-resolution layer — not a mandatory gate
for every memory.**

The default Memory Review queue shows only: `review_required` · `proposed` ·
sensitive-flagged · contradictions · low-confidence · scope-ambiguous (and
`speculative` / recently auto-saved memory only when the user enables those
views). Ordinary safe auto-saved memory is **not** forced into review; it is
visible in an audit/active view. All other guarantees stand: explicit action for
any change; Project ↔ Assistant separation; secrets/raw-audio redacted; GitHub
preview-first/optional; cloud sync future/pro; no provider calls; auto-active
memory remains auditable, reversible, and supersedable.
