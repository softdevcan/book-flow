from app.core.config import settings
from app.services.llm.base import LLMProvider, LLMProviderError
from app.services.llm.ollama_provider import OllamaProvider
from app.services.llm.openrouter_provider import OpenRouterProvider


def get_provider(
    provider: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
) -> LLMProvider:
    """Return an LLM provider instance.

    `provider` and `model` are optional per-call overrides; if omitted, falls back
    to the values from `settings` (driven by .env).
    """
    name = (provider or settings.LLM_PROVIDER).lower()
    match name:
        case "ollama":
            return OllamaProvider(model=model, temperature=temperature)
        case "openrouter":
            return OpenRouterProvider(model=model, temperature=temperature)
        case _:
            raise LLMProviderError(f"Unknown LLM provider: {name}")


__all__ = ["LLMProvider", "LLMProviderError", "get_provider"]
