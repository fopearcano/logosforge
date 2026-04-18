"""LLM provider configuration for the writing assistant."""

from dataclasses import dataclass, field


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_key: str = ""
    model: str = ""
    extra_headers: dict[str, str] = field(default_factory=dict)


PROVIDER_DEFAULTS: dict[str, ProviderConfig] = {
    "LM Studio": ProviderConfig(
        name="LM Studio",
        base_url="http://localhost:1234/v1",
    ),
    "Ollama": ProviderConfig(
        name="Ollama",
        base_url="http://localhost:11434/v1",
    ),
    "OpenAI": ProviderConfig(
        name="OpenAI",
        base_url="https://api.openai.com/v1",
        model="gpt-4o",
    ),
    "OpenRouter": ProviderConfig(
        name="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        extra_headers={"HTTP-Referer": "storyplanner-app"},
    ),
}

PROVIDER_NAMES = list(PROVIDER_DEFAULTS.keys())
