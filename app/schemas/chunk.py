import json

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.chunk import ChunkStatus


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

    @field_validator("editor_notes", mode="before")
    @classmethod
    def _parse_notes(cls, v):
        if v is None or isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else [str(parsed)]
            except json.JSONDecodeError:
                return [v]
        return v
