import json
import re
from typing import TypeVar

from ollama import AsyncClient
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.services.llm.base import LLMProvider, LLMProviderError

T = TypeVar("T", bound=BaseModel)

_RETRY_REMINDER = (
    "\n\nIMPORTANT: previous response was not valid JSON matching the required schema. "
    "Output ONLY the JSON object, no prose, no markdown fences."
)

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> str:
    """Pull the first {...} block out of free-form model output."""
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return fence.group(1)
    match = _JSON_BLOCK.search(text)
    if match:
        return match.group(0)
    return text


def _escape_control_chars_in_strings(text: str) -> str:
    """Escape raw newlines / tabs / CRs that appear inside JSON string literals.

    Local LLMs often emit `"foo\n\nbar"` as literal newlines instead of `\\n`,
    which json.loads rejects even with strict=False on some control chars.
    Walks the text, tracks whether we're inside a string (respecting backslash
    escapes), and replaces raw control chars with their escaped form.
    """
    out: list[str] = []
    in_string = False
    escape = False
    replacements = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}
    for ch in text:
        if in_string:
            if escape:
                out.append(ch)
                escape = False
                continue
            if ch == "\\":
                out.append(ch)
                escape = True
                continue
            if ch == '"':
                out.append(ch)
                in_string = False
                continue
            out.append(replacements.get(ch, ch))
        else:
            out.append(ch)
            if ch == '"':
                in_string = True
    return "".join(out)


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, model: str | None = None, temperature: float | None = None) -> None:
        self._client = AsyncClient(
            host=settings.OLLAMA_HOST,
            timeout=settings.OLLAMA_TIMEOUT_SECONDS,
        )
        self._model = model or settings.OLLAMA_MODEL
        self._temperature = (
            temperature if temperature is not None else settings.OLLAMA_TEMPERATURE
        )
        self._num_predict = settings.OLLAMA_NUM_PREDICT
        self._num_ctx = settings.OLLAMA_NUM_CTX
        self._force_json_format = settings.OLLAMA_FORCE_JSON_FORMAT

    async def generate_json(self, system: str, user: str, schema: type[T]) -> T:
        try:
            return await self._call(system, user, schema)
        except (ValidationError, json.JSONDecodeError):
            return await self._call(system + _RETRY_REMINDER, user, schema)

    async def list_models(self) -> list[str]:
        try:
            res = await self._client.list()
        except Exception as exc:
            raise LLMProviderError(f"Ollama list failed: {exc}") from exc
        models = res.get("models", []) if isinstance(res, dict) else getattr(res, "models", [])
        names: list[str] = []
        for m in models:
            name = m.get("model") if isinstance(m, dict) else getattr(m, "model", None)
            if name:
                names.append(name)
        return sorted(set(names))

    async def _call(self, system: str, user: str, schema: type[T]) -> T:
        kwargs: dict = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {
                "temperature": self._temperature,
                "num_predict": self._num_predict,
                "num_ctx": self._num_ctx,
            },
        }
        if self._force_json_format:
            kwargs["format"] = "json"

        try:
            response = await self._client.chat(**kwargs)
        except Exception as exc:
            raise LLMProviderError(f"Ollama request failed: {exc}") from exc

        content = response["message"]["content"]
        raw = _extract_json(content)
        # Many local models emit literal newlines/tabs inside JSON strings (technically
        # invalid). `strict=False` accepts them; if that still fails, fall back to a
        # manual scrub of unescaped control chars inside string literals.
        try:
            payload = json.loads(raw, strict=False)
        except json.JSONDecodeError:
            payload = json.loads(_escape_control_chars_in_strings(raw), strict=False)
        return schema.model_validate(payload)
