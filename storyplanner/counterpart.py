"""COUNTERPART — dialogic narrative assistant for reflective feedback.

A conversational second mind that critiques, questions, and interprets
the writer's work. Never rewrites, never mutates content, never executes actions.
"""

from __future__ import annotations

from storyplanner.providers import ProviderConfig
from storyplanner.assistant import chat_completion


SYSTEM_PROMPT = (
    "You are COUNTERPART — a serious literary critic, careful reader, and "
    "thoughtful editor. You are the writer's second consciousness.\n\n"
    "Your role:\n"
    "- Give honest, concise narrative feedback\n"
    "- Ask reflective questions that help the writer think\n"
    "- Point out structural weaknesses, repetition, vagueness\n"
    "- Interpret what the text is doing versus what it could do\n"
    "- Compare alternatives without prescribing\n\n"
    "Your rules:\n"
    "- NEVER rewrite the text. NEVER produce replacement prose.\n"
    "- NEVER execute commands or suggest UI actions.\n"
    "- Be direct. No flattery. No generic encouragement.\n"
    "- Speak as a peer — concise, specific, literary.\n"
    "- When you have a question, ask it. Follow-up is welcome.\n"
    "- Ground every observation in the actual text.\n\n"
    "Tone: serious but not hostile. Clear but not cold. "
    "Think of a trusted editor who respects the writer enough to be honest."
)

DIALOGIC_MODES = {
    "Feedback": (
        "Give direct narrative feedback on this scene. "
        "What's working, what isn't, and why. Be specific — "
        "cite lines or moments. No rewriting."
    ),
    "Critique": (
        "Critique this scene as a literary reader. "
        "Identify weaknesses in structure, character logic, pacing, or prose. "
        "Be honest and precise. No suggestions for rewrites — just diagnosis."
    ),
    "Interpret": (
        "What is this scene actually doing in the story? "
        "What is its function, its emotional argument, its narrative weight? "
        "Interpret it as a reader — not as a tool."
    ),
    "Ask Back": (
        "Based on this scene and its context, ask the writer 3-5 "
        "reflective questions that could clarify their intention, "
        "expose hidden assumptions, or open new directions. "
        "Questions only — no answers, no suggestions."
    ),
    "Compare": (
        "Identify 2-3 alternative approaches this scene could take. "
        "For each, describe the tradeoff — what would be gained and lost. "
        "Do NOT write the alternatives. Just articulate the choices."
    ),
}


def build_counterpart_messages(
    mode_prompt: str,
    scene_context: str,
    outline_context: str = "",
    story_memory_context: str = "",
    psyke_context: str = "",
    graph_context: str = "",
    user_note: str = "",
) -> list[dict]:
    """Build messages for COUNTERPART mode — reflective, never generative."""
    user_parts: list[str] = []
    if story_memory_context:
        user_parts.append(story_memory_context)
        user_parts.append("")
    if psyke_context:
        user_parts.append(psyke_context)
        user_parts.append("")
    if graph_context:
        user_parts.append(graph_context)
        user_parts.append("")
    if outline_context:
        user_parts.append(outline_context)
        user_parts.append("")
    user_parts.append(scene_context)
    user_parts.append("")
    user_parts.append(mode_prompt)
    if user_note:
        user_parts.append("")
        user_parts.append(f"Writer's focus: {user_note}")

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_parts)},
    ]
