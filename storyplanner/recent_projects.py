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
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    RECENT_FILE.write_text(json.dumps(paths, indent=2), encoding="utf-8")
