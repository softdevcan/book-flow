from fastapi import APIRouter

from app.schemas.language import (
    SUPPORTED_TARGETS,
    LangOption,
    LanguageDetectionRequest,
    LanguageDetectionResponse,
)
from app.services.lang_detect import detect_language

router = APIRouter(prefix="/api/languages", tags=["languages"])


@router.get("", response_model=list[LangOption])
def list_supported_languages() -> list[LangOption]:
    """Return the curated set of target languages the UI dropdown should show."""
    return SUPPORTED_TARGETS


@router.post("/detect", response_model=LanguageDetectionResponse)
async def detect(payload: LanguageDetectionRequest) -> LanguageDetectionResponse:
    """Auto-detect the language of a text snippet.

    Used by the upload form to pre-fill the source-language dropdown before the
    file is committed. lingua-py is tried first; if its top confidence is below
    threshold, the configured LLM is asked to classify.
    """
    return await detect_language(payload.text)
