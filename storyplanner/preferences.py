"""User preference flags persisted to a JSON file."""

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".storyplanner"
PREFS_FILE = CONFIG_DIR / "preferences.json"


def _load() -> dict:
    if not PREFS_FILE.exists():
        return {}
    try:
        data = json.loads(PREFS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def get_flag(name: str) -> bool:
    return bool(_load().get(name, False))


def set_flag(name: str, value: bool) -> None:
    data = _load()
    data[name] = bool(value)
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        PREFS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass
