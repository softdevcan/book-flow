from typing import TypeVar

from pydantic import BaseModel

from app.services.llm.base import LLMProvider, LLMProviderError

T = TypeVar("T", bound=BaseModel)


class OpenRouterProvider(LLMProvider):
    name = "openrouter"

    def __init__(self, model: str | None = None, temperature: float | None = None) -> None:
        self._model = model
        self._temperature = temperature

    async def generate_json(self, system: str, user: str, schema: type[T]) -> T:
        raise LLMProviderError(
            "OpenRouter provider not implemented yet. Set LLM_PROVIDER=ollama for v1."
        )

    async def list_models(self) -> list[str]:
        return []
