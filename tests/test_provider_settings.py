"""Tests for AI provider switching stability and settings persistence.

Covers two fixes:
1. Switching the provider no longer flashes the editable model combo's
   completer popup (the "tiny window" glitch).
2. Provider / server settings persist immediately and survive restart.
"""

import pytest

from storyplanner.db import Database
from storyplanner.providers import PROVIDER_NAMES
from storyplanner.ui.assistant_view import AssistantPanel
from storyplanner.ui.provider_settings import ProviderSettingsWidget


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch, tmp_path):
    """Fresh settings file per test so provider keys don't leak/persist
    into the real user settings."""
    import storyplanner.settings as settings
    settings._instance = None
    monkeypatch.setattr(settings, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    yield
    settings._instance = None


# =========================================================================
# 1. Tiny-window fix: editable model combo has no completer popup
# =========================================================================

def test_compact_model_combo_has_no_completer():
    w = ProviderSettingsWidget(compact=True)
    assert w._model_combo.completer() is None


def test_wide_model_combo_has_no_completer():
    w = ProviderSettingsWidget(compact=False)
    assert w._model_combo.completer() is None


def test_model_combo_still_editable():
    """Killing the popup must not remove the ability to type a model."""
    w = ProviderSettingsWidget(compact=True)
    assert w._model_combo.isEditable() is True


def test_model_combo_no_insert_on_type():
    from PySide6.QtWidgets import QComboBox
    w = ProviderSettingsWidget(compact=True)
    assert w._model_combo.insertPolicy() == QComboBox.InsertPolicy.NoInsert


# =========================================================================
# 2. Provider switching is stable
# =========================================================================

def test_provider_switch_updates_model_list():
    w = ProviderSettingsWidget(compact=True)
    w._provider_combo.setCurrentText("OpenAI")
    models = [w._model_combo.itemText(i) for i in range(w._model_combo.count())]
    assert "o3" in models or "gpt-4o" in models


def test_repeated_provider_switching_is_stable():
    w = ProviderSettingsWidget(compact=True)
    # Cycle through every provider several times — must not raise.
    for _ in range(3):
        for name in PROVIDER_NAMES:
            w._provider_combo.setCurrentText(name)
            cfg = w.get_provider_config()
            assert cfg.name == name
    # Final state is internally consistent.
    final = w.get_provider_config()
    assert final.name in PROVIDER_NAMES


# =========================================================================
# 2b. Updated model presets (newer OpenAI / Anthropic Claude IDs)
# =========================================================================

def test_anthropic_presets_include_latest():
    from storyplanner.providers import PROVIDER_CAPABILITIES
    models = PROVIDER_CAPABILITIES["Anthropic"].default_models
    assert "claude-opus-4-8" in models
    # Existing IDs are preserved (nothing removed).
    assert "claude-sonnet-4-6" in models
    assert "claude-3-opus-20240229" in models


def test_anthropic_default_is_latest():
    from storyplanner.providers import default_config
    assert default_config("Anthropic").model == "claude-opus-4-8"


def test_openai_presets_updated_and_preserved():
    from storyplanner.providers import PROVIDER_CAPABILITIES
    models = PROVIDER_CAPABILITIES["OpenAI"].default_models
    assert "o3-pro" in models
    # Existing IDs are preserved.
    for keep in ("o3", "o4-mini", "gpt-4.1", "gpt-4o", "gpt-3.5-turbo"):
        assert keep in models


def test_openrouter_presets_updated():
    from storyplanner.providers import PROVIDER_CAPABILITIES
    models = PROVIDER_CAPABILITIES["OpenRouter"].default_models
    assert "anthropic/claude-opus-4-8" in models
    assert "openai/o3-pro" in models


def test_unknown_custom_model_is_handled_gracefully():
    """A model ID not in the preset list must still be selectable and
    produce a valid config — presets are convenience, not a whitelist."""
    from storyplanner.providers import ProviderConfig, validate_provider
    cfg = ProviderConfig(
        name="Anthropic",
        base_url="https://api.anthropic.com",
        api_key="k",
        model="claude-some-future-model",
    )
    assert validate_provider(cfg) is None


def test_custom_model_typed_into_combo_survives():
    """Typing a custom model the presets don't contain is kept verbatim."""
    w = ProviderSettingsWidget(compact=True)
    w._provider_combo.setCurrentText("OpenAI")
    w._model_combo.setCurrentText("my-finetuned-model:v2")
    assert w.get_provider_config().model == "my-finetuned-model:v2"



def test_switch_to_local_then_cloud_then_local():
    w = ProviderSettingsWidget(compact=True)
    w._provider_combo.setCurrentText("LM Studio")
    assert "localhost:1234" in w._url_input.text()
    w._provider_combo.setCurrentText("OpenAI")
    assert "api.openai.com" in w._url_input.text()
    w._provider_combo.setCurrentText("Ollama")
    assert "localhost:11434" in w._url_input.text()


# =========================================================================
# 3. settings_changed signal
# =========================================================================

def test_settings_changed_emitted_on_provider_change():
    w = ProviderSettingsWidget(compact=True)
    seen = []
    w.settings_changed.connect(lambda: seen.append(True))
    w._provider_combo.setCurrentText("OpenAI")
    assert seen  # at least one emission


def test_settings_changed_emitted_on_model_change():
    w = ProviderSettingsWidget(compact=True)
    w._provider_combo.setCurrentText("OpenAI")
    seen = []
    w.settings_changed.connect(lambda: seen.append(True))
    w._model_combo.setCurrentText("gpt-4o-mini")
    assert seen


# =========================================================================
# 4. AssistantPanel persists provider settings immediately
# =========================================================================

def _panel():
    db = Database()
    proj = db.create_project("P")
    return AssistantPanel(db, proj.id)


def test_panel_persists_provider_on_change():
    from storyplanner.settings import get_manager
    panel = _panel()
    panel._provider_widget._provider_combo.setCurrentText("OpenAI")
    # Persisted immediately — no closeEvent / save_settings needed.
    assert get_manager().get("ai_provider") == "OpenAI"


def test_panel_persists_base_url_on_change():
    from storyplanner.settings import get_manager
    panel = _panel()
    pw = panel._provider_widget
    pw._url_input.setText("http://192.168.1.50:1234/v1")
    pw._url_input.editingFinished.emit()
    assert get_manager().get("ai_base_url") == "http://192.168.1.50:1234/v1"


def test_panel_persists_model_on_change():
    from storyplanner.settings import get_manager
    panel = _panel()
    panel._provider_widget._provider_combo.setCurrentText("Ollama")
    panel._provider_widget._model_combo.setCurrentText("mistral")
    assert get_manager().get("ai_model") == "mistral"


def test_panel_persists_timeout_on_change():
    from storyplanner.settings import get_manager
    panel = _panel()
    panel._timeout_spin.setValue(45)
    assert get_manager().get("assistant_api_timeout") == 45


def test_panel_persists_api_key_on_change():
    from storyplanner.settings import get_manager
    panel = _panel()
    pw = panel._provider_widget
    pw._provider_combo.setCurrentText("OpenAI")
    pw._key_input.setText("sk-test-123")
    pw._key_input.editingFinished.emit()
    assert get_manager().get("ai_api_key") == "sk-test-123"


# =========================================================================
# 5. Settings survive a restart (fresh SettingsManager reads the file)
# =========================================================================

def test_provider_settings_survive_restart():
    import storyplanner.settings as settings
    panel = _panel()
    pw = panel._provider_widget
    pw._provider_combo.setCurrentText("Ollama")
    pw._model_combo.setCurrentText("llama3.3")
    pw._url_input.setText("http://localhost:11434/v1")
    pw._url_input.editingFinished.emit()

    # Simulate restart: new SettingsManager reads the same file on disk.
    settings._instance = None
    fresh = settings.get_manager()
    assert fresh.get("ai_provider") == "Ollama"
    assert fresh.get("ai_model") == "llama3.3"
    assert fresh.get("ai_base_url") == "http://localhost:11434/v1"


def test_local_server_settings_persist_across_restart():
    import storyplanner.settings as settings
    panel = _panel()
    pw = panel._provider_widget
    # OpenAI-compatible local endpoint typed by hand.
    pw._provider_combo.setCurrentText("LM Studio")
    pw._url_input.setText("http://127.0.0.1:8080/v1")
    pw._url_input.editingFinished.emit()
    pw._model_combo.setCurrentText("local-model")

    settings._instance = None
    fresh = settings.get_manager()
    assert fresh.get("ai_provider") == "LM Studio"
    assert fresh.get("ai_base_url") == "http://127.0.0.1:8080/v1"
    assert fresh.get("ai_model") == "local-model"


def test_restored_panel_reflects_saved_provider():
    """A panel built after settings were saved restores them."""
    from storyplanner.settings import get_manager
    get_manager().set("ai_provider", "OpenRouter")
    get_manager().set("ai_model", "openrouter/auto")
    get_manager().set("ai_base_url", "https://openrouter.ai/api/v1")

    panel = _panel()
    pw = panel._provider_widget
    assert pw._provider_combo.currentText() == "OpenRouter"
    assert pw._model_combo.currentText() == "openrouter/auto"


# =========================================================================
# 6. Restore does not clobber saved settings (ordering guard)
# =========================================================================

def test_construction_does_not_overwrite_saved_settings():
    """Building a panel must not reset persisted provider to defaults."""
    from storyplanner.settings import get_manager
    get_manager().set("ai_provider", "Anthropic")
    get_manager().set("ai_model", "claude-sonnet-4-6")

    _panel()  # construction triggers restore + handlers

    assert get_manager().get("ai_provider") == "Anthropic"
    assert get_manager().get("ai_model") == "claude-sonnet-4-6"
