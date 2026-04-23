"""Writing assistant — HTTP client, prompt construction, and response cache."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from collections import OrderedDict

from storyplanner.providers import ProviderConfig, get_api_format, resolve_api_key

DEFAULT_BASE_URL = "http://localhost:1234/v1"

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


def build_messages(
    action_prompt: str,
    scene_context: str,
    outline_context: str = "",
    story_memory_context: str = "",
    psyke_context: str = "",
    graph_context: str = "",
    mode_context: str = "",
    user_note: str = "",
    structural_context: str = "",
    irrational_context: str = "",
) -> list[dict]:
    system = (
        "You are a skilled writing assistant helping a fiction author. "
        "You have access to the current scene and story context. "
        "Provide clear, creative, and actionable writing assistance. "
        "Respond directly with your writing or suggestions — "
        "no meta-commentary about being an AI."
    )

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
    if psyke_context:
        user_parts.append(psyke_context)
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

    with urllib.request.urlopen(req, timeout=timeout) as resp:
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

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data["content"][0]["text"]


def chat_completion(
    messages: list[dict],
    provider: ProviderConfig | None = None,
    base_url: str = "",
    model: str = "",
    timeout: int = 120,
    use_cache: bool = True,
) -> tuple[str, bool]:
    if provider is None:
        provider = ProviderConfig(
            name="LM Studio",
            base_url=base_url or DEFAULT_BASE_URL,
            model=model,
        )

    key: str | None = None
    if use_cache:
        key = _cache_key(messages, provider)
        cached = _cache_get(key)
        if cached is not None:
            return cached, True

    api_key = resolve_api_key(provider)
    api_format = get_api_format(provider)

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
    except urllib.error.URLError as e:
        raise ConnectionError(
            f"Cannot reach {provider.name} at {provider.base_url}.\n\n"
            f"Details: {e}"
        ) from e
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise RuntimeError(
            f"Unexpected response from {provider.name}:\n{e}"
        ) from e
    except OSError as e:
        raise ConnectionError(f"Connection error: {e}") from e


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
