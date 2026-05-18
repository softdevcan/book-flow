from pydantic import BaseModel, Field


class TranslationOutput(BaseModel):
    translated_text: str = Field(min_length=1)
    editor_notes: list[str] = Field(default_factory=list)
