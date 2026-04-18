"""Local LM Studio writing assistant — HTTP client and prompt construction."""

import json
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "http://localhost:1234/v1"

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
    "Alternatives": (
        "Suggest 3 alternative approaches for this scene. For each, "
        "describe the key change and how it would affect the story."
    ),
    "Dialogue": (
        "Rewrite the dialogue in this scene to be more natural, concise, "
        "and character-appropriate. Remove filler and sharpen subtext."
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
}


def build_messages(
    action_prompt: str,
    scene_context: str,
    outline_context: str = "",
    user_note: str = "",
) -> list[dict]:
    system = (
        "You are a skilled writing assistant helping a fiction author. "
        "You have access to the current scene and story context. "
        "Provide clear, creative, and actionable writing assistance. "
        "Respond directly with your writing or suggestions — "
        "no meta-commentary about being an AI."
    )

    user_parts: list[str] = []
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


def chat_completion(
    messages: list[dict],
    base_url: str = DEFAULT_BASE_URL,
    model: str = "",
    timeout: int = 120,
) -> str:
    url = f"{base_url.rstrip('/')}/chat/completions"

    body: dict = {
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2048,
        "stream": False,
    }
    if model:
        body["model"] = model

    payload = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except urllib.error.URLError as e:
        raise ConnectionError(
            f"Cannot reach LM Studio at {base_url}.\n"
            "Make sure LM Studio is running with the local server enabled.\n\n"
            f"Details: {e}"
        ) from e
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise RuntimeError(
            f"Unexpected response from LM Studio:\n{e}"
        ) from e
    except OSError as e:
        raise ConnectionError(f"Connection error: {e}") from e
