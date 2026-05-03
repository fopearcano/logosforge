"""PSYKE Console command parser — turns free-form input into structured commands."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CommandType(Enum):
    SEARCH = "search"
    ENTITY = "entity"
    SYSTEM = "system"


SYSTEM_COMMANDS = frozenset({
    "create",
    "open",
    "go",
    "ai",
    "delete",
    "rename",
    "link",
    "export",
    "help",
})


@dataclass(frozen=True)
class ParsedCommand:
    kind: CommandType
    command: str
    args: list[str]
    raw: str

    @property
    def first_arg(self) -> str:
        return self.args[0] if self.args else ""


def parse(raw_input: str) -> ParsedCommand:
    """Parse console input into a structured command.

    Formats:
        "jean"              → SEARCH for "jean"
        "/create character" → SYSTEM command "create" with args ["character"]
        "/john open"        → ENTITY command "john" with action ["open"]
        "/ai summarize"     → SYSTEM command "ai" with args ["summarize"]
    """
    text = raw_input.strip()
    if not text:
        return ParsedCommand(kind=CommandType.SEARCH, command="", args=[], raw=raw_input)

    if not text.startswith("/"):
        return ParsedCommand(kind=CommandType.SEARCH, command=text, args=[], raw=raw_input)

    body = text[1:]
    if not body:
        return ParsedCommand(kind=CommandType.SEARCH, command="", args=[], raw=raw_input)

    parts = body.split()
    head = parts[0].lower()
    tail = parts[1:]

    if head in SYSTEM_COMMANDS:
        return ParsedCommand(
            kind=CommandType.SYSTEM,
            command=head,
            args=tail,
            raw=raw_input,
        )

    return ParsedCommand(
        kind=CommandType.ENTITY,
        command=head,
        args=tail,
        raw=raw_input,
    )
