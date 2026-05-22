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

# Reasoning models (qwen3.x and friends) emit a chain-of-thought block before the
# actual answer. Even with format="json" some builds leak it, which crashes JSON
# parsing. Strip it defensively for every model — harmless when no block is present.
_THINK_BLOCK = re.compile(r"<think\b[^>]*>.*?</think\s*>", re.DOTALL | re.IGNORECASE)
_DANGLING_OPEN_THINK = re.compile(r"^.*?<think\b[^>]*>", re.DOTALL | re.IGNORECASE)
_DANGLING_CLOSE_THINK = re.compile(r".*?</think\s*>", re.DOTALL | re.IGNORECASE)


def _strip_reasoning(text: str) -> str:
    """Remove native <think>...</think> reasoning blocks from raw model output.

    Handles three shapes:
      - well-formed `<think>...</think>` pairs (any number, anywhere)
      - a dangling open tag with no close (truncated reasoning) — drop up to it
      - a dangling close tag with no open (model started mid-thought) — drop up to it
    Returns the surviving text, stripped. Safe to call on output with no tags.
    """
    cleaned = _THINK_BLOCK.sub("", text)
    if "<think" in cleaned.lower():
        cleaned = _DANGLING_OPEN_THINK.sub("", cleaned)
    if "</think" in cleaned.lower():
        cleaned = _DANGLING_CLOSE_THINK.sub("", cleaned, count=1)
    return cleaned.strip()


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
        self._think = settings.OLLAMA_THINK

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
        # `think` toggles reasoning on capable models. Passing it is harmless on
        # non-reasoning models. Older ollama-python may not accept the kwarg — if
        # so we retry without it (only matters when think is the default False).
        kwargs["think"] = self._think

        try:
            response = await self._client.chat(**kwargs)
        except TypeError as exc:
            if "think" in str(exc):
                kwargs.pop("think", None)
                response = await self._client.chat(**kwargs)
            else:
                raise LLMProviderError(
                    f"Ollama request failed (TypeError) for model '{self._model}': {exc}"
                ) from exc
        except Exception as exc:
            # Some exceptions (notably httpx.ReadTimeout) stringify to "", which
            # produced an opaque "Ollama request failed: " note. Include the type
            # and the model so timeouts vs. 404s vs. connection errors are tellable.
            detail = str(exc) or repr(exc)
            raise LLMProviderError(
                f"Ollama request failed ({type(exc).__name__}) "
                f"for model '{self._model}': {detail}"
            ) from exc

        message = response["message"]
        content = (message.get("content") if isinstance(message, dict)
                   else getattr(message, "content", None)) or ""
        # Reasoning models (qwen3.x) put their chain-of-thought in a separate
        # `thinking` field and leave `content` with just the answer. But if the
        # token budget is exhausted by reasoning, `content` can come back EMPTY.
        # In that case, fall back to scanning `thinking` for a JSON object — the
        # model often writes the final JSON at the end of its reasoning too.
        thinking = (message.get("thinking") if isinstance(message, dict)
                    else getattr(message, "thinking", None)) or ""

        # Strip any inline <think>...</think> (some models embed it in content).
        content = _strip_reasoning(content)
        raw = _extract_json(content)

        if not raw.strip() and thinking:
            raw = _extract_json(_strip_reasoning(thinking))

        if not raw.strip():
            done = response.get("done_reason") if isinstance(response, dict) else None
            raise LLMProviderError(
                f"Ollama returned no parseable content for model '{self._model}' "
                f"(done_reason={done!r}, content_empty={not content.strip()}, "
                f"thinking_len={len(thinking)}). The reasoning may have exhausted "
                f"num_predict ({self._num_predict}) before emitting the answer."
            )

        # Many local models emit literal newlines/tabs inside JSON strings (technically
        # invalid). `strict=False` accepts them; if that still fails, fall back to a
        # manual scrub of unescaped control chars inside string literals.
        try:
            payload = json.loads(raw, strict=False)
        except json.JSONDecodeError:
            payload = json.loads(_escape_control_chars_in_strings(raw), strict=False)
        return schema.model_validate(payload)
