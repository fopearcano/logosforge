"""Context-aware assistant output contracts + response validation.

Encodes the LogosForge assistant behavior model: assistant output is determined
by the current **section**, **writing mode**, **action**, and the user's explicit
instruction. Direct manuscript-writing actions must produce real manuscript
content in the project's mode format — never planning structure, analysis, or
markdown templates (those belong to Outline/planning sections or explicit
analysis actions). Pure functions only: no model/provider/DB/UI calls.

This module is the single source of truth for the strict system "output
contract" given to the model, and for validating responses before they are
shown/applied. It does not change provider behavior.
"""

from __future__ import annotations

import re

# ---- normalization ----------------------------------------------------------
_MODES = ("novel", "screenplay", "graphic_novel", "stage_script", "series")


def norm_mode(mode: str | None) -> str:
    m = (mode or "").strip().lower().replace(" ", "_").replace("-", "_")
    if m in _MODES:
        return m
    if "screen" in m:
        return "screenplay"
    if "graphic" in m or m == "gn" or "comic" in m:
        return "graphic_novel"
    if "stage" in m or "theatre" in m or "theater" in m or "play" in m:
        return "stage_script"
    if "series" in m or "episode" in m or "tv" in m:
        return "series"
    return "novel"


def norm_section(section: str | None) -> str:
    return (section or "").strip().lower()


def norm_action(action: str | None) -> str:
    a = (action or "").strip().lower()
    return a or "generate"


# Actions that produce DIRECT manuscript content (mode-formatted text/edits).
WRITING_ACTIONS = {
    "generate", "write", "continue", "dialogue", "rewrite", "expand", "tension",
}
# Sections whose primary job is writing manuscript content.
_WRITING_SECTIONS = {"manuscript", "scenes"}
_STRUCTURE_SECTIONS = {"outline", "plot", "acts", "beats", "pacing"}


def is_direct_manuscript_writing(section: str | None, action: str | None) -> bool:
    """True when the user is in a writing section doing a direct-writing action
    (so output must be manuscript content, never structure/analysis)."""
    return (norm_section(section) in _WRITING_SECTIONS
            and norm_action(action) in WRITING_ACTIONS)


# ---- output contracts -------------------------------------------------------
_FORBIDDEN_TAIL = (
    "FORBIDDEN — never output any of: markdown headings (#, ##, ###); bullet or "
    "numbered lists; 'Suggested Scene Structure'; 'Production Notes'; 'Your "
    "Scene'; 'Expanded & Refined'; bracketed planning labels such as "
    "[INTRODUCING] / [MAIN ACTION] / [CULMINATING MOMENT]; 'Key Questions'; "
    "scene breakdowns; outlines; analysis; critique; commentary; explanations; "
    "or any meta-description of what you will do. Output the content and "
    "NOTHING else."
)

_SCREENPLAY_WRITE = (
    "ROLE: You are writing the SCREENPLAY MANUSCRIPT directly for the author.\n"
    "OUTPUT: screenplay-formatted text ONLY that continues or edits the current "
    "scene, honoring the user's request and the existing characters.\n"
    "FORMAT:\n"
    "- Scene heading (INT./EXT. LOCATION - TIME) only when a new scene starts.\n"
    "- Action lines in present tense, only when needed.\n"
    "- CHARACTER name in CAPITALS on its own line, with the dialogue beneath it.\n"
    "- Parentheticals used sparingly.\n"
    "Write in the project's writing language and continue naturally.\n"
    + _FORBIDDEN_TAIL
)

_NOVEL_WRITE = (
    "ROLE: You are writing the NOVEL MANUSCRIPT directly.\n"
    "OUTPUT: pure narrative PROSE — action, description, inner thought, and "
    "dialogue woven into paragraphs — that continues or edits the scene per the "
    "user's request, in the story's voice and the project's writing language.\n"
    "Do NOT use screenplay scene headings (INT./EXT.) or CHARACTER cue blocks "
    "unless the user explicitly asks.\n"
    + _FORBIDDEN_TAIL
)

_GRAPHIC_NOVEL_WRITE = (
    "ROLE: You are writing the GRAPHIC NOVEL MANUSCRIPT directly "
    "(Act → Page → Scene → Panel).\n"
    "OUTPUT: panel-level script content for the current scene/page per the "
    "user's request, using the panel fields — number panels where helpful:\n"
    "  Panel N\n  Visual: ...\n  Caption: ...\n  Dialogue: CHARACTER: ...\n"
    "  SFX: ...\n  Notes: ...\n"
    "Write in the project's writing language.\n"
    "Do NOT use old 'Comics Script'/page-manager language and do NOT produce "
    "image-generation / ComfyUI prompts.\n"
    + _FORBIDDEN_TAIL
)

_STAGE_WRITE = (
    "ROLE: You are writing the STAGE SCRIPT MANUSCRIPT directly.\n"
    "OUTPUT: stage-script text ONLY — CHARACTER cues with their dialogue, and "
    "(stage directions) only where needed — continuing or editing the scene per "
    "the user's request, in the project's writing language.\n"
    "Do NOT use screenplay INT./EXT. slugs unless requested, and do NOT write "
    "novel-style narration.\n"
    + _FORBIDDEN_TAIL
)

_SERIES_WRITE = (
    "ROLE: You are writing the SERIES MANUSCRIPT directly for the current "
    "episode/scene (Series → Season → Episode → Act → Chapter → Scene).\n"
    "OUTPUT: manuscript content for the current scene per the user's request, in "
    "the project's established prose/teleplay voice and writing language.\n"
    + _FORBIDDEN_TAIL
)

_WRITE_BY_MODE = {
    "screenplay": _SCREENPLAY_WRITE, "novel": _NOVEL_WRITE,
    "graphic_novel": _GRAPHIC_NOVEL_WRITE, "stage_script": _STAGE_WRITE,
    "series": _SERIES_WRITE,
}

_STRUCTURE_CONTRACT = (
    "ROLE: You are planning the story STRUCTURE. Produce a clear, structured "
    "outline (acts / chapters / scenes / beats as appropriate) per the user's "
    "request — concise descriptions; structure is expected here. Do not write "
    "full manuscript prose unless the user asks."
)
_PSYKE_CONTRACT = (
    "ROLE: You are developing the STORY BIBLE / codex (PSYKE). Produce "
    "structured entity content (character / place / object / lore / theme / "
    "relationship facts) per the user's request. Do not write manuscript scene "
    "prose unless the user asks."
)
_NOTES_CONTRACT = (
    "ROLE: You are working with the user's NOTES. Organize, brainstorm, "
    "summarize, extract tasks, or develop raw ideas per the user's request."
)


def output_contract(*, writing_mode: str | None, section: str | None,
                    action: str | None, user_instruction: str = "") -> str:
    """The strict system/output contract for this (section, mode, action).

    The user's explicit instruction always governs *what* to produce; this
    contract governs the *form* and forbids structure/analysis leakage in
    direct manuscript writing.
    """
    sec = norm_section(section)
    if is_direct_manuscript_writing(section, action):
        return _WRITE_BY_MODE.get(norm_mode(writing_mode), _NOVEL_WRITE)
    if sec in _STRUCTURE_SECTIONS:
        return _STRUCTURE_CONTRACT
    if sec == "psyke":
        return _PSYKE_CONTRACT
    if sec == "notes":
        return _NOTES_CONTRACT
    # Manuscript/Scenes with an ANALYSIS action (suggest/summarize/diagnose…).
    if sec in _WRITING_SECTIONS:
        return (
            f"ROLE: You are assisting the current scene (action: "
            f"{norm_action(action)}). Give concise, directly actionable output "
            f"for the scene per the user's request. Do not rewrite the whole "
            f"manuscript and do not invent unrelated structure.")
    return (
        "ROLE: You are a context-aware writing assistant. Produce output "
        "appropriate to the current section and writing mode per the user's "
        "request. Do not output planning structure unless asked.")


# ---- response validation ----------------------------------------------------
_LEAK_MARKERS = (
    "suggested scene structure", "production notes", "your scene",
    "expanded & refined", "expanded and refined", "[introducing]",
    "[main action]", "[culminating moment]", "key questions to explore",
    "key questions", "prose style & cadence", "the user is writing",
    "suggested structure", "scene breakdown", "as an ai",
    "here's how i will", "here is how i will",
)
_MD_HEADING = re.compile(r"(?m)^\s{0,3}#{1,6}\s+\S")
_LIST_LINE = re.compile(r"(?m)^\s*(?:[-*]|\d+[.)])\s+\S")


def validate_response(text: str, *, writing_mode: str | None,
                      section: str | None, action: str | None) -> list[str]:
    """Detect structure/analysis/template leakage in a DIRECT manuscript-writing
    response. Returns a list of human-readable issues ([] when clean or when the
    action is not direct manuscript writing)."""
    if not is_direct_manuscript_writing(section, action):
        return []
    body = text or ""
    low = body.lower()
    issues: list[str] = []
    for marker in _LEAK_MARKERS:
        if marker in low:
            issues.append(f"contains '{marker}'")
    if _MD_HEADING.search(body):
        issues.append("contains markdown headings")
    if len(_LIST_LINE.findall(body)) >= 3:
        issues.append("contains a bullet/numbered list (planning structure)")
    return issues
