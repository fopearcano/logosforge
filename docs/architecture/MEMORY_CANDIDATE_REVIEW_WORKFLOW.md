# Memory Candidate Review — Workflow

> **Phase 7 — specification only. No code is changed by this document.**
> It describes the end-to-end review workflow and the status state-machine that
> the future Memory Review UI (`MEMORY_REVIEW_UI_SPEC.md`) drives. Every step
> maps to the already-implemented backend (`memory_arch.candidates`,
> `memory_arch.review`, `memory_arch.store`).

Principle: **the model generates; LogosForge remembers.** Curated memory is
*extracted from events*, proposed for review, and only becomes durable/active
on **explicit user approval**. Raw chat is never auto-saved as fact.

---

## Status state-machine

```
                 (extract + classify, marked spans only)
   interaction ───────────────────────────────────────────▶ proposed
   event                                                   │  speculative
                                                           │
        ┌──────────────── review (explicit, human) ────────┘
        │
        ├─ approve ───────────────▶ active ──┐
        │                                     │ supersede(old,new,reason)
        ├─ reject(reason) ────────▶ rejected  ▼
        ├─ mark_speculative ──────▶ speculative   old ─▶ superseded  (kept, linked)
        ├─ mark_contradicted ─────▶ contradicted
        └─ edit(patch,reason) ────▶ (same status; content/scope revised)

   active ──(later)── deprecate / supersede / mark_contradicted ──▶ archived
```

Backed by `MemoryStatus` = `active · proposed · speculative · rejected ·
deprecated · superseded · contradicted`. **No status transition deletes the
object or its source event** — history is preserved (`version`, event log,
`memory_relations`).

Context-eligibility (enforced today by `AssistantContextBuilder`): only
`active` memory feeds normal assistant context. `proposed`/`speculative` appear
only with `include_proposed`/`review_mode`; archived statuses only in
`diagnostic` mode (labelled). Rejected/superseded/contradicted never pollute
normal context.

---

## Flow A — Candidate creation (no UI; already implemented)

1. User interacts with the assistant or edits the project.
2. An event is logged (`store.add_event`) **or** passed straight into the
   processor.
3. `candidates.process_event_for_memory_candidates(store, event)` extracts
   **only marked spans** (ordered marker heuristic) and classifies type/scope/
   confidence.
4. `MemoryWriterPolicy` validates: drops secrets/raw-audio/debug; enforces scope
   + required ids (Project↔Assistant separation); skip-with-warning when an id
   is missing.
5. Candidate is stored as **`proposed`** (or **`speculative`** for speculative
   ideas) — **never active**.
6. Candidate appears in **Memory Review → Review queue**.
7. Candidate is **not** used in normal assistant context yet.

## Flow B — Approval

1. User opens Memory Review.
2. User filters by scope / project / type / status.
3. User inspects the candidate card (content, source preview, badges,
   contradictions).
4. User **approves** (optionally **edits then approves**) →
   `review.approve(id)` (after any `review.edit(id, patch, reason)`).
5. Candidate → `active`; `version` bumped; `updated_at` set.
6. The context builder may retrieve it in **future** assistant calls (it is now
   eligible for normal context).

## Flow C — Rejection

1. User **rejects** → `review.reject(id, reason)` (reason required).
2. Status → `rejected` (or `deprecated` per policy).
3. The **source event remains** available for audit.
4. Rejected candidate is **excluded from normal context** and moved to the
   Archive view.

## Flow D — Supersession

1. A candidate conflicts with an older active memory (surfaced by
   `review.contradictions_for` / `tools.find_contradictions`).
2. The UI shows the contradiction side-by-side.
3. User **approves the new + supersedes the old** →
   `review.supersede(old_id, new_id, reason)`.
4. Old memory → `superseded`, retained and linked (`supersedes`,
   `memory_relations`) — **never silently deleted**; visible in history.
5. The context builder **excludes superseded memory by default**.

## Flow E — Diagnostic review

1. User enables **diagnostic mode** (`assistant_memory_context_diagnostics_enabled`
   today; a future UI toggle).
2. The UI may show `proposed` / `speculative` / `deprecated` / `superseded` /
   `contradicted` items.
3. All non-active items are **clearly labelled** with their status.
4. Diagnostic mode is **read-only** and **must not** cause accidental context
   pollution — viewing archived/candidate items never makes them eligible for
   normal assistant context.

---

## Contradiction handling (detail)

`memory_arch.contradictions` provides a deterministic, local heuristic
(keyword-overlap + opposing polarity; no LLM, no embeddings). It only
**surfaces** conflicts. Resolution is always an explicit human choice in Flow D
/ the contradiction-review action: keep both · approve new + supersede old ·
reject new · mark both needing-review · edit candidate · mark old deprecated.

## Invariants the workflow must preserve

- No candidate becomes `active` without explicit approval.
- No durable write happens during context build/retrieval (read-only).
- Project Memory and Assistant Meta-Memory never mix.
- Secrets / raw audio / raw audio paths are never stored or shown.
- Superseded/rejected/contradicted memory stays auditable, never deleted.
- Cloud sync and GitHub export remain disabled/opt-in/preview-first.

---

**Reaffirmed:** the model generates; LogosForge remembers, retrieves,
structures, updates; approval is always explicit; Jordan is memory-grounded,
not conscious. **No implementation in this document.**
