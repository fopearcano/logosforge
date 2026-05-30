"""Parse an Assistant outline response into structured outline operations.

Outline Mode asks the model for a structured outline (acts / chapters /
scenes / beats). This module turns that free text into a hierarchy of
proposed nodes so the Assistant can PROPOSE the structure and then apply it
additively through the existing outline services — instead of only showing
text.

The Outline data model is a single ``OutlineNode`` table whose hierarchy is
pure parent/child nesting (no node_type column). We infer depth from
Markdown headers (``#`` levels), list indentation, and act/chapter/scene/
beat keywords, then emit nodes with parent links + sort order.

Pure logic: no UI, no DB writes here — the caller applies the result.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class OutlineOp:
    """One proposed outline node (a create operation)."""

    title: str
    description: str = ""
    level: int = 0                     # 0 = top (act/part), deeper = nested
    kind: str = ""                     # act|chapter|scene|beat|section (label)
    children: list["OutlineOp"] = field(default_factory=list)

    def count(self) -> int:
        return 1 + sum(c.count() for c in self.children)


# Keyword → canonical level (used to normalise mixed inputs).
_KIND_LEVEL = {"act": 0, "part": 0, "chapter": 1, "sequence": 1,
               "scene": 2, "beat": 3}
_KIND_RE = re.compile(
    r"^\s*(act|part|chapter|sequence|scene|beat)\b[\s:.\-)]*",
    re.IGNORECASE,
)
# "1.", "1)", "- ", "* ", "1.2", "•"
_LIST_RE = re.compile(r"^(\s*)(?:[-*•]|\d+[.)](?:\d+[.)])*)\s+(.*)$")
_HEADER_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def _split_title_desc(text: str) -> tuple[str, str]:
    """Split "Title: description" / "Title — description" into parts."""
    text = text.strip().strip("*_`").strip()
    for sep in (" — ", " – ", " - ", ": "):
        if sep in text:
            head, tail = text.split(sep, 1)
            if head.strip():
                return head.strip().rstrip(":").strip(), tail.strip()
    return text.rstrip(":").strip(), ""


def _classify(raw: str) -> tuple[str, int | None]:
    """Return (kind, forced_level) from a leading act/chapter/... keyword."""
    m = _KIND_RE.match(raw)
    if not m:
        return "", None
    kw = m.group(1).lower()
    kind = ("act" if kw in ("act", "part") else
            "chapter" if kw in ("chapter", "sequence") else kw)
    return kind, _KIND_LEVEL[kw]


def _titled(kind: str, raw: str) -> tuple[str, str]:
    """Split a keyword-led line into (title, description).

    Keeps the numbered identity ("Act 1", "Chapter 2") but drops a bare type
    label ("Scene:", "Beat -") so the title is the meaningful text.
    """
    rest = _KIND_RE.sub("", raw).strip()
    head, desc = _split_title_desc(rest)
    label = kind.capitalize()
    if head[:1].isdigit():
        # Keep the numbered identity ("Act 1"); drop any punctuation.
        num = re.match(r"[\d.]+", head)
        num = num.group(0).rstrip(".") if num else ""
        return f"{label} {num}".strip(), desc
    # Bare label like "Scene: title" — title is the remainder.
    return (head or label), desc


def parse_outline_response(text: str) -> list[OutlineOp]:
    """Parse outline text into a tree of OutlineOp (top-level list).

    Robust to: Markdown headers, numbered/bulleted lists with indentation,
    and explicit Act/Chapter/Scene/Beat labels. Lines that look like prose
    (no list/header marker) attach as description to the current node.
    """
    roots: list[OutlineOp] = []
    # stack of (level, op) for the current open ancestry.
    stack: list[tuple[int, OutlineOp]] = []
    last: OutlineOp | None = None
    # Level of the most recent header/keyword section — list items nest
    # beneath it. Reset whenever a header opens a new section.
    section_level = -1
    # (physical_indent, logical_level) frames for the current list, mapping
    # indentation to nesting depth. Reset by headers / bare section keywords.
    indent_stack: list[tuple[int, int]] = []

    def _attach(level: int, op: OutlineOp) -> None:
        nonlocal last
        while stack and stack[-1][0] >= level:
            stack.pop()
        if stack:
            stack[-1][1].children.append(op)
        else:
            roots.append(op)
        stack.append((level, op))
        last = op

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue

        header = _HEADER_RE.match(line)
        listm = _LIST_RE.match(line)

        if header:
            depth = len(header.group(1)) - 1   # "#"=0, "##"=1, ...
            kind, forced = _classify(header.group(2))
            if kind:
                title, desc = _titled(kind, header.group(2))
            else:
                title, desc = _split_title_desc(header.group(2))
            level = forced if forced is not None else depth
            section_level = level
            indent_stack = []
            _attach(level, OutlineOp(title=title or header.group(2).strip(),
                                     description=desc, level=level, kind=kind))
            continue

        if listm:
            indent = len(listm.group(1).replace("\t", "  "))
            body = listm.group(2)
            kind, _forced = _classify(body)
            if kind:
                title, desc = _titled(kind, body)
            else:
                title, desc = _split_title_desc(body)
            # Nesting follows INDENTATION (the keyword only labels the kind),
            # so same-indent items are siblings — e.g. "- Scene" then "- Beat"
            # at the same indent both sit under the section, not under each
            # other. Drop frames at >= this indent, then nest one deeper than
            # the surviving parent (or the section if none).
            while indent_stack and indent_stack[-1][0] >= indent:
                indent_stack.pop()
            level = (indent_stack[-1][1] + 1) if indent_stack else (
                section_level + 1
            )
            indent_stack.append((indent, level))
            _attach(level, OutlineOp(title=title or body.strip(),
                                     description=desc, level=level, kind=kind))
            continue

        # Bare line: a labelled heading (e.g. "Act 1: ...") or prose desc.
        kind, forced = _classify(line)
        if kind:
            title, desc = _titled(kind, line)
            level = forced if forced is not None else 0
            if kind in ("act", "chapter"):
                section_level = level
                indent_stack = []
            _attach(level, OutlineOp(title=title or line.strip(),
                                     description=desc, level=level, kind=kind))
        elif last is not None:
            # Continuation prose → append to the current node's description.
            extra = line.strip()
            last.description = (
                (last.description + " " + extra).strip()
                if last.description else extra
            )
        else:
            # Leading prose with no structure yet → a top-level section.
            title, desc = _split_title_desc(line)
            _attach(0, OutlineOp(title=title, description=desc, level=0))

    return roots


def _renumber(ops: list[OutlineOp]) -> list[OutlineOp]:
    return ops


def count_ops(ops: list[OutlineOp]) -> int:
    return sum(o.count() for o in ops)


def format_outline_preview(ops: list[OutlineOp]) -> str:
    """Human-readable preview of the proposed structure (for confirmation)."""
    lines: list[str] = []

    def _walk(op: OutlineOp, depth: int) -> None:
        bullet = "  " * depth + "• "
        label = f"[{op.kind}] " if op.kind else ""
        line = f"{bullet}{label}{op.title}"
        if op.description:
            line += f" — {op.description[:60]}"
        lines.append(line)
        for child in op.children:
            _walk(child, depth + 1)

    for op in ops:
        _walk(op, 0)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# AI generation prompt builder (scope-aware, engine-aware, PSYKE-aware)
# ---------------------------------------------------------------------------

# Per-narrative-engine outline vocabulary so the prompt fits the medium.
_ENGINE_OUTLINE_GUIDE = {
    "novel": "Structure as Acts → Chapters → Scenes/Beats.",
    "screenplay": "Structure as Acts → Sequences → Scenes/Beats.",
    "stage_script": "Structure as Acts → Scenes → Beats.",
    "graphic_novel": "Structure as Issues/Acts → Sequences/Chapters → "
                     "Pages/Scenes → Beats.",
    "series": "Structure as Seasons/Acts → Episodes/Chapters → Scenes/Beats.",
}


def build_outline_generation_prompt(
    scope: str = "full", *, engine: str = "novel", template_name: str = "",
    template_beats: list[str] | None = None, psyke_context: str = "",
    target_title: str = "", instructions: str = "",
) -> str:
    """Build the user prompt for an AI outline generation request.

    scope: "full" | "act" | "chapter" | "scene". *engine* tailors the
    structural vocabulary; *template_*/psyke_context/target_title are folded
    in when present. Pure text — the caller sends it to the model.
    """
    guide = _ENGINE_OUTLINE_GUIDE.get(engine, _ENGINE_OUTLINE_GUIDE["novel"])
    parts: list[str] = []

    if scope == "act":
        parts.append("Generate ONE act for the story outline, with its "
                     "chapters and key scenes/beats.")
    elif scope == "chapter":
        parts.append("Generate ONE chapter for the story outline, with its "
                     "scenes/beats.")
    elif scope == "scene":
        parts.append("Generate the scenes/beats for this part of the outline.")
    else:
        parts.append("Generate a complete story outline.")

    if target_title:
        parts.append(f"This continues under: {target_title}.")

    parts.append(guide)
    parts.append(
        "Format as a Markdown outline using '#'/'##'/'###' headers and/or "
        "'- ' bullets. Prefix items with Act/Chapter/Scene/Beat where "
        "appropriate. Give each node a short title and a one-line "
        "description. Do not write prose."
    )

    if template_name:
        parts.append(f"Follow the '{template_name}' structure.")
    if template_beats:
        parts.append("Template beats to honour: " + "; ".join(template_beats))
    if psyke_context:
        parts.append(psyke_context)
    if instructions:
        parts.append(instructions)

    return "\n\n".join(parts)


def apply_outline_ops(
    db, project_id: int, ops: list[OutlineOp], parent_id: int | None = None,
) -> list[int]:
    """Apply parsed ops ADDITIVELY under *parent_id* via outline services.

    Appends after existing siblings (never deletes / overwrites). Returns the
    flat list of created node ids in creation order.
    """
    created: list[int] = []
    existing = db.get_outline_children(project_id, parent_id)
    base = len(existing)
    for i, op in enumerate(ops):
        node = db.create_outline_node(
            project_id, op.title or "(untitled)", description=op.description,
            parent_id=parent_id, sort_order=base + i,
        )
        created.append(node.id)
        if op.children:
            created.extend(
                apply_outline_ops(db, project_id, op.children, parent_id=node.id)
            )
    return created
