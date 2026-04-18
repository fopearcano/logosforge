"""LLM provider configuration and capabilities for the writing assistant."""

from dataclasses import dataclass, field


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_key: str = ""
    model: str = ""
    extra_headers: dict[str, str] = field(default_factory=dict)


@dataclass
class ProviderCapabilities:
    requires_api_key: bool
    default_base_url: str
    supports_local: bool
    default_models: list[str]
    supports_model_selection: bool
    extra_headers: dict[str, str] = field(default_factory=dict)


PROVIDER_CAPABILITIES: dict[str, ProviderCapabilities] = {
    "LM Studio": ProviderCapabilities(
        requires_api_key=False,
        default_base_url="http://localhost:1234/v1",
        supports_local=True,
        default_models=[],
        supports_model_selection=False,
    ),
    "Ollama": ProviderCapabilities(
        requires_api_key=False,
        default_base_url="http://localhost:11434/v1",
        supports_local=True,
        default_models=["llama3", "mistral"],
        supports_model_selection=True,
    ),
    "OpenAI": ProviderCapabilities(
        requires_api_key=True,
        default_base_url="https://api.openai.com/v1",
        supports_local=False,
        default_models=["gpt-4o-mini", "gpt-4o"],
        supports_model_selection=True,
    ),
    "OpenRouter": ProviderCapabilities(
        requires_api_key=True,
        default_base_url="https://openrouter.ai/api/v1",
        supports_local=False,
        default_models=["openrouter/auto"],
        supports_model_selection=True,
        extra_headers={"HTTP-Referer": "storyplanner-app"},
    ),
}

PROVIDER_NAMES = list(PROVIDER_CAPABILITIES.keys())


def default_config(name: str) -> ProviderConfig:
    caps = PROVIDER_CAPABILITIES[name]
    return ProviderConfig(
        name=name,
        base_url=caps.default_base_url,
        model=caps.default_models[0] if caps.default_models else "",
        extra_headers=dict(caps.extra_headers),
    )


def validate_provider(config: ProviderConfig) -> str | None:
    """Return an error message, or None if config is valid."""
    caps = PROVIDER_CAPABILITIES.get(config.name)
    if caps is None:
        return f"Unknown provider: {config.name}"
    if not config.base_url:
        return "Base URL is required."
    if caps.requires_api_key and not config.api_key:
        return f"{config.name} requires an API key."
    return None
