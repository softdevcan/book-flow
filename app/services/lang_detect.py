"""Source-language detection: lingua-py first, Ollama LLM fallback.

The lingua detector is cached at module load (initialization is ~100 ms). If
its top confidence is below CONFIDENCE_THRESHOLD we fall back to the configured
LLM provider to classify the snippet. The result feeds the upload form so the
user can confirm or override before saving the book.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from pydantic import BaseModel, Field

from app.schemas.language import LanguageDetectionResponse
from app.services.llm import get_provider

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.7
SNIPPET_MAX_CHARS = 3000


class _LangCode(BaseModel):
    code: str = Field(min_length=2, max_length=8)


@lru_cache(maxsize=1)
def _get_detector():
    # Imported lazily so the rest of the app loads even if the optional dep is
    # missing in a dev environment.
    from lingua import LanguageDetectorBuilder

    return LanguageDetectorBuilder.from_all_languages().with_preloaded_language_models().build()


def _normalize(text: str) -> str:
    return text.strip()[:SNIPPET_MAX_CHARS]


async def detect_language(text: str) -> LanguageDetectionResponse:
    snippet = _normalize(text)
    if not snippet:
        # No content — default to English, low confidence, so the UI keeps the
        # user-pick mandatory.
        return LanguageDetectionResponse(code="en", confidence=0.0, method="lib")

    # Stage A — lingua-py
    try:
        detector = _get_detector()
        confidences = detector.compute_language_confidence_values(snippet)
        if confidences:
            top = max(confidences, key=lambda c: c.value)
            code = top.language.iso_code_639_1.name.lower()
            if top.value >= CONFIDENCE_THRESHOLD:
                return LanguageDetectionResponse(
                    code=code, confidence=float(top.value), method="lib"
                )
            logger.info(
                "detect_language: lingua low confidence %.2f for %r — falling back to LLM",
                top.value, code,
            )
    except Exception:
        logger.exception("detect_language: lingua failed; falling back to LLM")

    # Stage B — LLM fallback
    try:
        provider = get_provider()
        system_prompt = (
            "Identify the language of the user's text. Respond strictly with a single JSON "
            "object: {\"code\": \"<ISO 639-1 lowercase code>\"}. No commentary."
        )
        result = await provider.generate_json(system_prompt, snippet, _LangCode)
        return LanguageDetectionResponse(
            code=result.code.lower(), confidence=0.0, method="llm"
        )
    except Exception:
        logger.exception("detect_language: LLM fallback failed; defaulting to 'en'")
        return LanguageDetectionResponse(code="en", confidence=0.0, method="llm")
