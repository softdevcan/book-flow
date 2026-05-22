import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.chunk import ChunkStatus


def _notes_to_list(v):
    """Coerce a JSON-encoded editor_notes string into list[str] (or pass through)."""
    if v is None or isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            return parsed if isinstance(parsed, list) else [str(parsed)]
        except json.JSONDecodeError:
            return [v]
    return v


class ChunkCreate(BaseModel):
    sequence_number: int = Field(ge=0)
    source_text: str = Field(min_length=1)
    scene_context: str | None = None


class ChunkUpdate(BaseModel):
    translated_text: str | None = None
    editor_notes: list[str] | None = None
    status: ChunkStatus | None = None
    scene_context: str | None = None


class ChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    book_id: int
    sequence_number: int
    source_text: str
    translated_text: str | None
    status: ChunkStatus
    editor_notes: list[str] | None
    scene_context: str | None
    active_version_id: int | None = None

    @field_validator("editor_notes", mode="before")
    @classmethod
    def _parse_notes(cls, v):
        return _notes_to_list(v)


class TranslationVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chunk_id: int
    translated_text: str
    editor_notes: list[str] | None
    pipeline: str | None
    stage1_model: str | None
    stage2_model: str | None
    created_at: datetime

    @field_validator("editor_notes", mode="before")
    @classmethod
    def _parse_notes(cls, v):
        return _notes_to_list(v)
