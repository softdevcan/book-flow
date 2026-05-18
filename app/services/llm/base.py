from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProviderError(RuntimeError):
    pass


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def generate_json(self, system: str, user: str, schema: type[T]) -> T:
        """Generate a JSON response and validate it against the given Pydantic schema."""
        raise NotImplementedError

    @abstractmethod
    async def list_models(self) -> list[str]:
        """List models available from this provider, if discoverable."""
        raise NotImplementedError
