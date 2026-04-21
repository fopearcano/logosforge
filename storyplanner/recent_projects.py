"""Track recently opened/saved project file paths."""

import json
from pathlib import Path

MAX_RECENT = 10
CONFIG_DIR = Path.home() / ".storyplanner"
RECENT_FILE = CONFIG_DIR / "recent_projects.json"


def load() -> list[str]:
    if not RECENT_FILE.exists():
        return []
    try:
        data = json.loads(RECENT_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [p for p in data if isinstance(p, str)]
    except (json.JSONDecodeError, OSError):
        pass
    return []


def add(path: str) -> None:
    paths = load()
    if path in paths:
        paths.remove(path)
    paths.insert(0, path)
    paths = paths[:MAX_RECENT]
    _save(paths)


def remove(path: str) -> None:
    paths = load()
    paths = [p for p in paths if p != path]
    _save(paths)


def clean() -> list[str]:
    """Drop paths whose files no longer exist on disk. Returns cleaned list."""
    paths = load()
    valid = [p for p in paths if Path(p).is_file()]
    if len(valid) != len(paths):
        _save(valid)
    return valid


def _save(paths: list[str]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    RECENT_FILE.write_text(json.dumps(paths, indent=2), encoding="utf-8")
