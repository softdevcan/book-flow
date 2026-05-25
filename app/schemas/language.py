from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LangOption(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=2, max_length=8)
    name: str


class LanguageDetectionResponse(BaseModel):
    code: str = Field(min_length=2, max_length=8)
    confidence: float = Field(ge=0.0, le=1.0)
    method: Literal["lib", "llm"]


class LanguageDetectionRequest(BaseModel):
    text: str = Field(min_length=1)


# Curated v1 target set. Per-language prompt rules live in
# app/services/llm/lang_rules.py; languages without tuned rules fall back to a
# generic block. To add a language: append here AND add a LANG_RULES entry.
SUPPORTED_TARGETS: list[LangOption] = [
    LangOption(code="tr", name="Turkish"),
    LangOption(code="en", name="English"),
    LangOption(code="fr", name="French"),
    LangOption(code="de", name="German"),
    LangOption(code="es", name="Spanish"),
    LangOption(code="ru", name="Russian"),
    LangOption(code="it", name="Italian"),
    LangOption(code="pt", name="Portuguese"),
]

SUPPORTED_CODES: set[str] = {opt.code for opt in SUPPORTED_TARGETS}
