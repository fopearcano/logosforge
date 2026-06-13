# Jordan — Externalized Self-Model

> Phase 1 — direction only. Defines the assistant's externalized self-model.
> Implements nothing and renames nothing in code.

## Naming reconciliation (read first)

This document uses **"Jordan"** as the architecture-level name for the
unified, memory-grounded assistant identity. The **current Alpha code does
not contain "Jordan"** — its assistant surfaces are:

- **Billy** — the AI chat/assistant agent (`voice/billy_bridge.py`, etc.).
- **Logos** — the inline/contextual AI layer (`storyplanner/logos/…`).
- **Dexter** — the local voice writing room (`voice/…`, Dexter's Room).

Treat **Jordan as the externalized-self-model concept** these surfaces
should share. **Do not rename Billy/Logos/Dexter in code** as part of this
architecture work (see the contradiction note in the after-work report and
`§15` cross-doc rules). Any future unification of the name is a separate,
explicit decision.

## Jordan is

- **memory-grounded** — behavior comes from LogosForge memory, not weights.
- **project-aware** — sees the active project's Project Memory.
- **historically consistent** — remembers collaboration history via memory.
- **model-agnostic** — works with any selected backend (`MODEL_GATEWAY_SPEC.md`).
- **externally orchestrated** by LogosForge (`ASSISTANT_ORCHESTRATION_LAYER.md`).
- capable of remembering collaboration history **through LogosForge memory**.

## Jordan is NOT

- conscious.
- self-aware in a human sense.
- permanently learning inside model weights.
- tied to one model provider.
- identical to LM Studio / Ollama / OpenAI / Anthropic / OpenRouter.

## Jordan has

- an identity / role file.
- assistant rules.
- known limitations.
- remembered collaboration history.
- remembered mistakes / corrections.
- user-specific preferences.
- project-specific context.
- tool access (`ASSISTANT_TOOLS_SPEC.md`).
- provider-independent memory.

## "Externalized self-model" defined

A **structured set of memory objects and rules** (stored in LogosForge, not
in model weights) that helps the assistant behave consistently across
sessions, devices, projects, and model providers. It is retrieved via
`retrieve_assistant_rules(context)` and lives at `assistant` scope.

It includes:

- assistant identity
- operating rules
- user collaboration preferences
- known mistakes
- corrections
- current architecture decisions
- project workflow norms
- tool usage policies
- release / prompting policies

Because it is externalized, swapping the model backend changes *how text is
generated* but never *who the assistant is* or *what it remembers*.
