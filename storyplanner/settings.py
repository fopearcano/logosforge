"""Persistent settings manager — loads once, auto-saves on change."""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".storyplanner"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

DEFAULTS: dict[str, object] = {
    "appearance": "Dark",
    "ai_provider": "LM Studio",
    "ai_model": "",
    "sidebar_collapsed": False,
    "assistant_open": False,
}


class SettingsManager:
    def __init__(self) -> None:
        self._data: dict[str, object] = dict(DEFAULTS)
        self._load()

    def _load(self) -> None:
        if not SETTINGS_FILE.exists():
            return
        try:
            raw = SETTINGS_FILE.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, dict):
                self._data.update(data)
        except (json.JSONDecodeError, OSError):
            pass

    def _save(self) -> None:
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            SETTINGS_FILE.write_text(
                json.dumps(self._data, indent=2), encoding="utf-8",
            )
        except OSError:
            pass

    def get(self, key: str) -> object:
        return self._data.get(key, DEFAULTS.get(key))

    def set(self, key: str, value: object) -> None:
        if self._data.get(key) == value:
            return
        self._data[key] = value
        self._save()


_instance: SettingsManager | None = None


def get_manager() -> SettingsManager:
    global _instance
    if _instance is None:
        _instance = SettingsManager()
    return _instance
