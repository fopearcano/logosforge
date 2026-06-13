# Model Gateway Spec

> Phase 1 — provider-abstraction **direction**. The Alpha already seeds this
> in `storyplanner/providers.py` (`ProviderCapabilities`,
> `PROVIDER_CAPABILITIES`, `build_active_provider`) and `assistant.py`
> (`chat_completion` with OpenAI/Anthropic API formats). This document
> describes where that abstraction goes; it implements nothing new.

## Principle

**Model providers generate / reason. They do not own LogosForge memory.**
The gateway is a thin, swappable adapter layer between the Assistant Engine
and any backend. Swapping providers must never lose memory.

## Supported providers

LM Studio · Ollama · vLLM · OpenAI · Anthropic · OpenRouter · future
providers. *(vLLM is not yet in the Alpha's `PROVIDER_CAPABILITIES`; it is a
planned addition — see contradictions in the after-work report.)*

## Gateway responsibilities

1. Normalize provider **requests**.
2. Normalize provider **responses**.
3. Handle **streaming**.
4. Handle **tool-call** compatibility.
5. Handle **structured output** (JSON schema) compatibility.
6. Handle **context-window / capability** metadata.
7. Handle **local vs cloud privacy** differences.
8. **Report provider capabilities** to the Assistant Engine.
9. **Never become the memory store.**

## Provider capability descriptor

(Generalizes today's `ProviderCapabilities`.)

| Field | Meaning |
|-------|---------|
| `provider_id` | Stable id (e.g. `lm_studio`, `ollama`, `vllm`, `openai`, `anthropic`, `openrouter`). |
| `provider_type` | `local` · `self_hosted` · `cloud`. |
| `base_url` | Endpoint. |
| `auth_mode` | `none` · `api_key` · `custom_header`. |
| `models` | Available/known models. |
| `context_window` | Max tokens. |
| `supports_streaming` | bool. |
| `supports_tools` | bool. |
| `supports_json_schema` | bool. |
| `supports_embeddings` | bool. |
| `supports_vision` | bool. |
| `supports_audio` | bool. |
| `privacy_mode` | e.g. `local_only` · `cloud`. |
| `latency_class` | rough latency tier. |
| `cost_class` | rough cost tier. |
| `offline_capable` | bool. |

## Provider notes (memory always belongs to LogosForge)

- **LM Studio** — local/self-hosted; exposes a local OpenAI-compatible API
  (Alpha default `http://localhost:1234/v1`, no key). Memory → LogosForge.
- **Ollama** — local/self-hosted; local API (`:11434/v1`). Memory → LogosForge.
- **vLLM** — self-hosted inference server. Memory → LogosForge.
- **OpenAI** — cloud. Memory → LogosForge.
- **Anthropic** — cloud (distinct API format; already handled in
  `assistant.py`). Memory → LogosForge.
- **OpenRouter** — cloud routing/marketplace. Memory → LogosForge.

## Boundary

The gateway returns generated text/structured output + capability metadata
to the Assistant Engine. It must not read, write, retrieve, or persist
memory objects. All memory operations go through the assistant tools
(`ASSISTANT_TOOLS_SPEC.md`) against the Memory Store.


## Phase 2 — implemented interface locations

Interfaces/stubs only (no DB, no cloud sync, no GitHub commits, no vector runtime, no external provider calls, no UI wiring, no automatic durable writes). New isolated packages:

- `storyplanner/memory_arch/` — `schema.py` (MemoryObject, EventLogEntry, enums), `store.py` (`MemoryStore` ABC + `InMemoryMemoryStore`), `policy.py` (`MemoryWriterPolicy`), `retrieval.py`, `contradictions.py`, `sync.py` (disabled), `github_export.py` (disabled).
- `storyplanner/assistant_arch/` — `model_gateway.py` (`ProviderCapability`/`ModelRequest`/`ModelResponse`/`ModelProvider`/`ModelGateway` + `DummyModelProvider`), `context_builder.py` (`AssistantContextBuilder`, `ContextBundle`, `MemoryCandidateExtractor`), `orchestration.py` (`AssistantOrchestrator`), `tools.py` (`AssistantTools`).

Tests: `tests/test_memory_architecture_stubs.py` (21). The Alpha assistant (`assistant.py`, Billy/Logos/Dexter) and `providers.py` are unchanged.

**Note:** the Phase-2 `ProviderCapability` in `assistant_arch/model_gateway.py` is the forward-looking abstraction; the live Alpha still uses `storyplanner/providers.py`. vLLM remains documented but not yet added to the live `PROVIDER_CAPABILITIES`.
