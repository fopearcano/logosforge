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
    "ai_api_key": "",
    "ai_base_url": "",
    "sidebar_collapsed": False,
    "sidebar_groups_expanded": {},
    "assistant_open": False,
    "assistant_pinned": False,
    "assistant_collapsed": False,
    "assistant_panel_mode": "assistant",
    "assistant_include_outline": False,
    "assistant_include_memory": False,
    "assistant_include_bible": False,
    "assistant_include_notes": True,
    "assistant_irrational": False,
    # -- Logos proactive suggestions (Phase 4) -------------------------------
    "logos_proactive_enabled": True,
    "logos_confidence_threshold": 0.65,
    "logos_show_info": True,
    "logos_show_warning": True,
    "logos_ai_scan_enabled": False,   # AI-assisted scan deferred; off by default
    # -- Narrative Health (Phase 6) ------------------------------------------
    "health_enabled": True,
    "health_auto_refresh_on_load": True,
    "health_include_in_assistant": False,
    "health_show_unknown": True,
    # -- Strategy layer (Phase 7) --------------------------------------------
    "strategy_enabled": True,
    "strategy_show_indicator": True,
    "strategy_debug_explanation": False,
    "strategy_user_mode_override": "",   # "" = auto; else an engine id
    # -- Assistant context injection (Phase 8B / 9 / 10C) --------------------
    "include_project_mode_in_assistant_context": True,
    "include_screenplay_diagnostics_in_assistant_context": True,
    "include_screenplay_tracking_in_assistant_context": True,
    "include_screenplay_links_in_assistant_context": True,
    "include_screenplay_export_in_assistant_context": True,
    # Professional output (DOCX/PDF/FDX) — opt-in to avoid prompt bloat.
    "include_professional_output_in_assistant_context": False,
    # Production draft status — shown only when production mode is active.
    "include_production_draft_in_assistant_context": True,
    # Revision impact — shown only when a saved impact report exists.
    "include_revision_impact_in_assistant_context": True,
    # Rewrite sandbox — shown only when an open rewrite session exists.
    "include_rewrite_sandbox_in_assistant_context": True,
    # Controlled apply — shown only when a pending apply preview exists.
    "include_controlled_apply_in_assistant_context": True,
    # Project intelligence — concise dashboard state (light, opt-out).
    "include_project_intelligence_in_assistant_context": True,
    # Guided workflow — shown only when a guided workflow is active.
    "include_guided_workflow_in_assistant_context": True,
    "include_strategy_in_assistant_context": True,
    "include_health_in_assistant_context": False,
    "include_diagnostics_in_assistant_context": True,
    "max_health_risks_in_context": 3,
    "max_diagnostics_in_context": 5,
    "last_project_path": "",
    "plugin_states": {},
    "auto_link_ignored": [],
    "context_assistant_enabled": True,
    "context_assistant_ignored": [],
    "connector_enabled": False,
    "connector_allow_writes": False,
    "connector_confirm_writes": True,
    "connector_disabled_actions": [],
    "assistant_api_timeout": 0,
    "default_projects_folder": "",
    "open_anyway_on_lock": False,
    "graph_state": {},
    "graph_presets": {},
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
