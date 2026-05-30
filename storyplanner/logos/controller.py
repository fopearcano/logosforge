"""LogosController — runs a Logos action for a given context.

The controller is a *thin adapter* over the existing Assistant backend. It:

* builds context strings with the shared ``context_builder`` (read-only),
* assembles messages with the shared ``assistant.build_messages``,
* resolves the provider with the shared ``outline_ai.build_provider`` and runs
  the shared ``assistant.chat_completion``.

It never instantiates a provider/client, never reads or writes provider
settings directly, never opens a second chat backend, and never mutates the
database. The provider resolver and chat function are injectable so callers (and
tests) can supply fakes — proving Logos rides on the single shared backend.
"""

from __future__ import annotations

from collections.abc import Callable

from storyplanner.logos import actions as logos_actions
from storyplanner.logos.context import LogosContext
from storyplanner.logos.prompt_builder import build_logos_messages
from storyplanner.logos.result import LogosResult


def _default_provider_resolver():
    from storyplanner.ui.outline_ai import build_provider
    return build_provider()


def _default_chat_fn(messages, provider):
    from storyplanner.assistant import chat_completion
    text, _cached = chat_completion(messages, provider=provider)
    return text


class LogosController:
    """Resolve + run Logos actions against the shared Assistant backend."""

    def __init__(
        self,
        db,
        *,
        provider_resolver: Callable[[], object] | None = None,
        chat_fn: Callable[[list, object], str] | None = None,
    ) -> None:
        self._db = db
        # Shared-backend hooks (injectable for tests; defaults reuse the one
        # real provider/chat system — Logos owns no provider config of its own).
        self._provider_resolver = provider_resolver or _default_provider_resolver
        self._chat_fn = chat_fn or _default_chat_fn

    # -- Introspection -------------------------------------------------------

    def available_actions(self, section_name: str) -> list[logos_actions.LogosAction]:
        return logos_actions.list_actions_for_section(section_name)

    # -- Execution -----------------------------------------------------------

    def run(self, context: LogosContext, action_name: str) -> LogosResult:
        action = logos_actions.get_action(action_name)
        if action is None:
            return LogosResult.failure(action_name, f"Unknown Logos action: {action_name}")
        if action.destructive:
            # Phase 0 is non-destructive — destructive actions are not runnable.
            return LogosResult.failure(
                action_name, "Destructive actions are not available in this phase.",
            )
        if context.section_name and not action.applies_to(context.section_name):
            return LogosResult.failure(
                action_name,
                f"'{action.label}' is not available in the {context.section_name} section.",
            )
        if action.needs_selection and not context.has_selection():
            return LogosResult.failure(
                action_name, "Select some text first, then run this action.",
            )

        try:
            messages = build_logos_messages(self._db, context, action)
        except Exception as exc:  # context build must never crash the UI
            return LogosResult.failure(action_name, f"Could not build context: {exc}")

        provider = None
        try:
            provider = self._provider_resolver()
        except Exception:
            provider = None

        if provider is None:
            # Offline / unconfigured: return a safe diagnostic preview rather
            # than failing — Phase 0 stays useful and testable without network.
            return LogosResult(
                ok=True,
                action=action_name,
                title=action.label,
                message=(
                    "No AI provider is configured, so Logos is showing a local "
                    "preview only. Configure a provider in the Assistant "
                    "settings to get a full response."
                ),
                suggestions=self._local_preview(action, context),
                proposed_operations=[],  # Phase 0: never auto-apply
            )

        try:
            reply = self._chat_fn(messages, provider)
        except Exception as exc:
            return LogosResult.failure(action_name, f"Assistant request failed: {exc}")

        reply = reply or ""
        # Phase 2: derive the *available* (preview-only) operations. They carry
        # suggested payloads; nothing is applied until the user confirms.
        try:
            from storyplanner.logos.operations import build_proposed_operations
            proposed = build_proposed_operations(self._db, context, action, reply)
        except Exception:
            proposed = []

        return LogosResult(
            ok=True,
            action=action_name,
            title=action.label,
            message=reply,
            suggestions=_parse_suggestions(reply),
            proposed_operations=proposed,
        )

    # -- Internals -----------------------------------------------------------

    def _local_preview(self, action, ctx: LogosContext) -> list[str]:
        bits = [f"Action: {action.label}", f"Section: {ctx.section_name or '—'}"]
        if ctx.current_scene_id is not None:
            bits.append(f"Scene id: {ctx.current_scene_id}")
        if ctx.has_selection():
            bits.append(f"Selection length: {len(ctx.selected_text.strip())} chars")
        return bits


def _parse_suggestions(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s[:2] in ("- ", "* ", "• "):
            out.append(s[2:].strip())
        elif s.startswith("•"):
            out.append(s[1:].strip())
    return [s for s in out if s]
