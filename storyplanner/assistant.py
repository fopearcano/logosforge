"""Writing assistant — HTTP client, prompt construction, and response cache."""

from __future__ import annotations

import hashlib
import json
import socket
import ssl
import time
import urllib.error
import urllib.request
from collections import OrderedDict

from storyplanner.providers import ProviderConfig, get_api_format, resolve_api_key

DEFAULT_BASE_URL = "http://localhost:1234/v1"

_LOCAL_PROVIDERS = {"LM Studio", "Ollama"}
_DEFAULT_TIMEOUT_LOCAL = 300
_DEFAULT_TIMEOUT_CLOUD = 120


def default_timeout_for_provider(provider_name: str) -> int:
    if provider_name in _LOCAL_PROVIDERS:
        return _DEFAULT_TIMEOUT_LOCAL
    return _DEFAULT_TIMEOUT_CLOUD


def get_configured_timeout(provider_name: str = "") -> int:
    from storyplanner.settings import get_manager
    val = get_manager().get("assistant_api_timeout")
    if isinstance(val, (int, float)) and val > 0:
        return int(val)
    return default_timeout_for_provider(provider_name)


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, socket.timeout):
        return True
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        return isinstance(reason, (socket.timeout, OSError))
    if isinstance(exc, ConnectionError):
        return True
    if isinstance(exc, OSError) and not isinstance(exc, urllib.error.HTTPError):
        return True
    return False


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()

_CACHE_MAX_SIZE = 128
_CACHE_TTL_SECONDS = 300

_cache: OrderedDict[str, tuple[float, str]] = OrderedDict()

PRESET_ACTIONS = {
    "Rewrite": (
        "Rewrite the following scene, improving clarity, flow, and prose "
        "quality while preserving the original meaning and tone."
    ),
    "Expand": (
        "Expand this scene with more detail, sensory description, and "
        "emotional depth. Keep the existing structure but flesh it out."
    ),
    "Summarize": (
        "Write a concise summary of this scene in 2-3 sentences, "
        "capturing the key events and emotional beats."
    ),
    "Dialogue": (
        "Rewrite the dialogue in this scene to be more natural, concise, "
        "and character-appropriate. Remove filler and sharpen subtext."
    ),
    "Tension": (
        "Rewrite this scene to increase tension and stakes. Heighten "
        "conflict, add urgency, sharpen obstacles, and raise the "
        "emotional pressure on the characters."
    ),
    "Pacing": (
        "Analyze and rewrite this scene to improve its pacing. Speed up "
        "slow sections, add beats where needed, and improve the rhythm "
        "of action and reflection."
    ),
    "Next Beat": (
        "Based on this scene and its context, suggest 3-5 possible next "
        "beats or events that could follow naturally in the story."
    ),
    "Alternatives": (
        "Suggest 3 alternative approaches for this scene. For each, "
        "describe the key change and how it would affect the story."
    ),
}


DEFAULT_SYSTEM_PROMPT = (
    "You are a skilled writing assistant helping a fiction author. "
    "You have access to the current scene and story context. "
    "Provide clear, creative, and actionable writing assistance. "
    "Respond directly with your writing or suggestions — "
    "no meta-commentary about being an AI."
)


# Names of the languages the trigram detector can report (back-compat
# export; the full registry lives in storyplanner.languages).
_LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
}

# The active project's USER-SELECTED writing language ("" = none chosen —
# keep the legacy detect-from-text behavior). The app shell sets this on
# project open/switch, so every AI surface (assistant, Logos, inline edits,
# rewrite tools, Billy voice proposals) preserves the project language by
# default without per-call wiring. Explicit response_language always wins.
_ACTIVE_PROJECT_LANGUAGE: dict[str, str] = {"code": ""}


def set_active_project_language(code) -> None:
    if not code:
        _ACTIVE_PROJECT_LANGUAGE["code"] = ""
        return
    from storyplanner.languages import normalize_language
    normalized = normalize_language(code)
    _ACTIVE_PROJECT_LANGUAGE["code"] = "" if normalized == "auto" else normalized


def get_active_project_language() -> str:
    return _ACTIVE_PROJECT_LANGUAGE["code"]


def _detect_response_language(messages: list[dict]) -> str:
    from storyplanner.grammar_checker import detect_language

    for msg in messages:
        if msg["role"] == "user":
            text = msg["content"]
            if len(text) >= 30:
                return detect_language(text)
            break
    return "en"


def _inject_language_instruction(
    messages: list[dict], language: str,
) -> list[dict]:
    """Append the preserve-the-writing-language instruction to the system
    message. English returns the messages unchanged (the prompts' base
    assumption); the wording never asks for translation and adds RTL / CJK
    notes where relevant (see languages.ai_language_instruction)."""
    if language == "en":
        return messages
    from storyplanner.languages import ai_language_instruction
    instruction = ai_language_instruction(language)
    if not instruction:
        return messages
    result = []
    for msg in messages:
        if msg["role"] == "system":
            result.append({
                "role": "system",
                "content": msg["content"] + instruction,
            })
        else:
            result.append(msg)
    return result


def build_messages(
    action_prompt: str,
    scene_context: str,
    outline_context: str = "",
    story_memory_context: str = "",
    psyke_context: str = "",
    notes_context: str = "",
    graph_context: str = "",
    mode_context: str = "",
    user_note: str = "",
    structural_context: str = "",
    irrational_context: str = "",
    controlling_idea_context: str = "",
    system_prompt: str = "",
) -> list[dict]:
    system = system_prompt or DEFAULT_SYSTEM_PROMPT

    user_parts: list[str] = []
    if mode_context:
        user_parts.append(mode_context)
        user_parts.append("")
    if irrational_context:
        user_parts.append(irrational_context)
        user_parts.append("")
    if story_memory_context:
        user_parts.append(story_memory_context)
        user_parts.append("")
    if controlling_idea_context:
        user_parts.append(controlling_idea_context)
        user_parts.append("")
    if psyke_context:
        user_parts.append(psyke_context)
        user_parts.append("")
    if notes_context:
        user_parts.append(notes_context)
        user_parts.append("")
    if graph_context:
        user_parts.append(graph_context)
        user_parts.append("")
    if structural_context:
        user_parts.append(structural_context)
        user_parts.append("")
    if outline_context:
        user_parts.append(outline_context)
        user_parts.append("")
    user_parts.append(scene_context)
    user_parts.append("")
    user_parts.append(action_prompt)
    if user_note:
        user_parts.append("")
        user_parts.append(f"Additional notes: {user_note}")

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


def _cache_key(messages: list[dict], provider: ProviderConfig) -> str:
    raw = json.dumps(messages, sort_keys=True) + provider.base_url + provider.model
    return hashlib.sha256(raw.encode()).hexdigest()


def _cache_get(key: str) -> str | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, value = entry
    if time.monotonic() - ts > _CACHE_TTL_SECONDS:
        _cache.pop(key, None)
        return None
    _cache.move_to_end(key)
    return value


def _cache_put(key: str, value: str) -> None:
    _cache[key] = (time.monotonic(), value)
    _cache.move_to_end(key)
    while len(_cache) > _CACHE_MAX_SIZE:
        _cache.popitem(last=False)


def _openai_completion(
    messages: list[dict],
    provider: ProviderConfig,
    api_key: str,
    timeout: int,
) -> str:
    url = f"{provider.base_url.rstrip('/')}/chat/completions"

    body: dict = {
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2048,
        "stream": False,
    }
    if provider.model:
        body["model"] = provider.model

    payload = json.dumps(body).encode("utf-8")

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    headers.update(provider.extra_headers)

    req = urllib.request.Request(
        url, data=payload, headers=headers, method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)
    if "choices" not in data:
        err = data.get("error")
        if err:
            msg = err.get("message") if isinstance(err, dict) else str(err)
            raise RuntimeError(f"{provider.name} error: {msg}")
        raise RuntimeError(
            f"{provider.name} returned no 'choices'. "
            f"Check that a model is loaded and the base URL ends with /v1.\n"
            f"Response: {raw[:400]}"
        )
    return data["choices"][0]["message"]["content"]


def _anthropic_completion(
    messages: list[dict],
    provider: ProviderConfig,
    api_key: str,
    timeout: int,
) -> str:
    url = f"{provider.base_url.rstrip('/')}/v1/messages"

    system_text = ""
    api_messages = []
    for msg in messages:
        if msg["role"] == "system":
            system_text = msg["content"]
        else:
            api_messages.append({"role": msg["role"], "content": msg["content"]})

    if not api_messages:
        api_messages = [{"role": "user", "content": "Hello"}]

    body: dict = {
        "model": provider.model or "claude-sonnet-4-20250514",
        "max_tokens": 2048,
        "messages": api_messages,
    }
    if system_text:
        body["system"] = system_text

    payload = json.dumps(body).encode("utf-8")

    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    headers.update(provider.extra_headers)

    req = urllib.request.Request(
        url, data=payload, headers=headers, method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data["content"][0]["text"]


def chat_completion(
    messages: list[dict],
    provider: ProviderConfig | None = None,
    base_url: str = "",
    model: str = "",
    timeout: int = 0,
    use_cache: bool = True,
    response_language: str = "",
) -> tuple[str, bool]:
    if provider is None:
        provider = ProviderConfig(
            name="LM Studio",
            base_url=base_url or DEFAULT_BASE_URL,
            model=model,
        )

    if timeout <= 0:
        timeout = get_configured_timeout(provider.name)

    # Response-language priority: explicit caller choice → the project's
    # user-selected writing language → legacy detect-from-text.
    lang = (response_language or get_active_project_language()
            or _detect_response_language(messages))
    messages = _inject_language_instruction(messages, lang)

    key: str | None = None
    if use_cache:
        key = _cache_key(messages, provider)
        cached = _cache_get(key)
        if cached is not None:
            return cached, True

    api_key = resolve_api_key(provider)
    api_format = get_api_format(provider)

    last_err: BaseException | None = None
    for attempt in range(2):
        try:
            if api_format == "anthropic":
                result = _anthropic_completion(messages, provider, api_key, timeout)
            else:
                result = _openai_completion(messages, provider, api_key, timeout)

            if key is not None:
                _cache_put(key, result)
            return result, False
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:400]
            except Exception:
                pass
            raise RuntimeError(
                f"{provider.name} returned HTTP {e.code}: {e.reason}\n{body}"
            ) from e
        except (urllib.error.URLError, ConnectionError, OSError, socket.timeout) as e:
            last_err = e
            if attempt == 0 and _is_transient(e):
                time.sleep(1)
                continue
            break
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise RuntimeError(
                f"Unexpected response from {provider.name}:\n{e}"
            ) from e

    if last_err is not None:
        if isinstance(last_err, (socket.timeout,)) or (
            isinstance(last_err, urllib.error.URLError)
            and isinstance(getattr(last_err, "reason", None), socket.timeout)
        ):
            raise ConnectionError(
                f"{provider.name} timed out after {timeout}s.\n\n"
                f"The model did not respond within the configured timeout. "
                f"You can increase it in Assistant Settings.\n\n"
                f"Provider: {provider.name}\n"
                f"Base URL: {provider.base_url}\n"
                f"Timeout: {timeout}s"
            ) from last_err
        if isinstance(last_err, urllib.error.URLError):
            raise ConnectionError(
                f"Cannot reach {provider.name} at {provider.base_url}.\n\n"
                f"Details: {last_err}\n"
                f"Timeout: {timeout}s"
            ) from last_err
        raise ConnectionError(
            f"Connection to {provider.name} failed.\n\n"
            f"Details: {last_err}\n"
            f"Timeout: {timeout}s"
        ) from last_err
    raise RuntimeError("Unexpected error in chat_completion")


def test_connection(provider: ProviderConfig) -> tuple[bool, str]:
    try:
        chat_completion(
            [{"role": "user", "content": "Say OK"}],
            provider=provider,
            timeout=15,
            use_cache=False,
        )
        return True, f"Connected to {provider.name}."
    except Exception as e:
        return False, str(e)
