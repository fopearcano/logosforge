"""Shared helpers for AI outline generation in the UI.

Both the (orphaned) OutlineView and the live PlanView need to run an
outline-generation request off the UI thread and to resolve the configured
provider.  This module centralises that so the behaviour stays identical.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal


class OutlineGenWorker(QThread):
    """Runs an outline-generation LLM request off the UI thread."""

    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, messages, provider) -> None:
        super().__init__()
        self._messages = messages
        self._provider = provider

    def run(self) -> None:
        try:
            from storyplanner.assistant import chat_completion
            text, _from_cache = chat_completion(
                self._messages, provider=self._provider,
            )
            self.completed.emit(text)
        except Exception as e:  # pragma: no cover - network/provider errors
            self.failed.emit(str(e))


def build_provider():
    """Resolve the configured AI provider, or None if none is set."""
    from storyplanner.providers import ProviderConfig
    from storyplanner.settings import get_manager

    mgr = get_manager()
    name = str(mgr.get("ai_provider") or "")
    base_url = str(mgr.get("ai_base_url") or "")
    if not (name or base_url):
        return None
    return ProviderConfig(
        name=name or "LM Studio",
        base_url=base_url or "http://localhost:1234/v1",
        model=str(mgr.get("ai_model") or ""),
        api_key=str(mgr.get("ai_api_key") or ""),
    )


def outline_messages(prompt: str) -> list[dict]:
    """Standard system+user message pair for an outline generation prompt."""
    return [
        {"role": "system",
         "content": "You are a story-structure assistant. Produce a clean, "
                    "structured outline only — no prose."},
        {"role": "user", "content": prompt},
    ]
