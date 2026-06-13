# LogosForge Memory Architecture

> **Phase 1 — architecture direction only.** No database tables, migrations,
> vector search, provider clients, sync, GitHub automation, or UI are
> implemented by this document. It defines the direction the LogosForge
> core (this repo) and its future frontends/services must follow.

## Core principle

> **The model generates. LogosForge remembers, retrieves, structures,
> updates, and syncs.**

Model providers are **replaceable generation/reasoning backends**. They are
**not** the memory system. The memory system is implemented inside
LogosForge and is owned by the Python core (`fopearcano/storyplanner`).

1. **Model providers are not the memory system.** LM Studio, Ollama, vLLM,
   OpenAI, Anthropic, OpenRouter and any future provider produce tokens;
   they do not own, persist, or retrieve LogosForge memory.
2. **Memory is implemented inside LogosForge.** It is the core's
   responsibility, exposed through the API layer that frontends consume.
3. **LogosForge is model-agnostic.** The selected backend can change at any
   time without losing a single memory object.
4. **The assistant works with local or cloud models** through one gateway.
5. **Memory is externalized and persistent** — it lives in LogosForge
   stores, never inside model weights.
6. **Memory is structured, scoped, versioned, and sync-capable** (see
   `MEMORY_OBJECT_SCHEMA.md`).
7. **Memory is not raw chat spam.** Durable memory is curated, not a
   transcript dump (see the memory writer policy in `ASSISTANT_MEMORY_SPEC.md`).
8. **GitHub is optional**, never the default backend for every user (see
   `GITHUB_EXPORT_STRATEGY.md`).

## Ownership boundary (per `CLAUDE.md`)

This repo (the Python core) owns: the **Memory Store**, the **Assistant
Engine / orchestration**, the **Model Gateway**, and the **API surface**
that exposes them. It does **not** own React/Electron UI, web hosting/auth,
or cloud deployment — those are future scaffolds in other repos
(`logosforge-desktop`, cloud/infra repos) that consume this core's API.
Cloud sync and GitHub export below describe **direction**; the durable
contracts (schema, tools, gateway) are what this repo implements.

## Component hierarchy

```
LogosForge App
├─ Editor / Whiteboard / Outline / Codex (PSYKE)        [UI: this repo's
│                                                          Qt app today;
│                                                          React later]
├─ Project Database                                      [core, this repo]
├─ Assistant Engine                                      [core, this repo]
│   ├─ prompt builder
│   ├─ context selector
│   ├─ memory retriever
│   ├─ memory writer
│   ├─ contradiction checker
│   ├─ model router
│   └─ tool caller
├─ Memory Store                                          [core + future svc]
│   ├─ local structured DB        (active working memory)
│   ├─ local vector index         (semantic retrieval)
│   ├─ cloud sync layer           (future / pro)
│   └─ optional GitHub export     (opt-in power-user)
└─ Model Providers                                       [replaceable backends]
    ├─ LM Studio · Ollama · vLLM   (local / self-hosted)
    ├─ OpenAI · Anthropic · OpenRouter (cloud)
    └─ future providers
```

## Memory tier hierarchy

| Tier | Role |
|------|------|
| **Local memory** | Active working memory. Fast, offline, local-first UX. SQLite (desktop) / Postgres (server) in MVP. |
| **Cloud account memory** | Sync, multi-device continuation, shared project memory. Canonical shared state for an account/workspace. *(future / pro)* |
| **GitHub** | Optional power-user archive / export / versioning layer. Not the default backend for any user. |
| **Model providers** | Replaceable reasoning/generation engines. Hold no durable LogosForge memory. |

## Roadmap (summary; full phases in §Implementation direction below and `ASSISTANT_ORCHESTRATION_LAYER.md`)

- **Early MVP:** local-first memory (SQLite/Postgres); simple structured
  memory tables; optional vector store (pgvector / Chroma / Qdrant); local
  models via LM Studio/Ollama; cloud models via the model gateway; memory
  candidate extraction + retrieval **placeholders**; no destructive memory
  writes; no GitHub auto-commit.
- **SaaS / Pro:** user accounts; cloud sync; project/workspace memory;
  permissions; shared memory; cloud embeddings/index; optional GitHub export.
- **Team / Studio:** workspace memory; role-based permissions; shared
  project assistant; project-level assistant history; versioned memory;
  audit/history.

## Implementation direction (Claude Code)

Do **not** implement the full system at once. Build in phases:

1. **Phase 1 — Architecture docs only** (this set under `docs/architecture/`).
2. **Phase 2 — Minimal interfaces/stubs:** model-provider abstraction,
   memory-object schema, local memory-store interface, assistant
   context-builder interface, retrieval placeholder, candidate-extraction
   placeholder. No destructive writes; no GitHub auto-commit.
3. **Phase 3 — Local MVP:** SQLite/Postgres-backed local memory; event log;
   curated memory table; manual approve/reject of candidates; basic
   semantic index if safe.
4. **Phase 4 — Cloud sync:** account/project/workspace memory; conflict
   resolution; permissions; cloud index.
5. **Phase 5 — Optional GitHub export:** markdown export; architecture
   decision log; assistant memory snapshot; **manual push/commit only**.

## How the current Alpha relates to this direction

The Alpha already seeds parts of this architecture (see the cited modules
in each spec): `storyplanner/providers.py` (`ProviderCapabilities` — the
Model Gateway seed), `assistant.py` / `assistant_context_policy.py` /
`context_assistant.py` / `memory_context.py` / `memory_manager.py` /
`story_memory.py` / `chat_memory.py` (Assistant Engine + context seeds),
and the project database + PSYKE (Project Memory). These are partial and
project-context-oriented; the scoped, versioned, sync-capable memory system
described here is future work layered over them — **not** a rewrite of the
Alpha.

See: `ASSISTANT_MEMORY_SPEC.md`, `MEMORY_OBJECT_SCHEMA.md`,
`ASSISTANT_TOOLS_SPEC.md`, `MODEL_GATEWAY_SPEC.md`,
`ASSISTANT_ORCHESTRATION_LAYER.md`, `SYNC_STRATEGY.md`,
`GITHUB_EXPORT_STRATEGY.md`, `JORDAN_EXTERNALIZED_SELF_MODEL.md`.
