from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BookBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    author: str | None = Field(default=None, max_length=255)
    style_guide: str | None = None
    source_language: str = Field(min_length=2, max_length=8)
    target_language: str = Field(min_length=2, max_length=8)


class BookCreate(BookBase):
    pass


class BookUpdate(BaseModel):
    """Update payload.

    `source_language` and `target_language` are intentionally not exposed: the
    language pair is fixed at creation. Changing it after chunks have been
    translated would invalidate the existing translations.
    """

    title: str | None = Field(default=None, min_length=1, max_length=255)
    author: str | None = Field(default=None, max_length=255)
    style_guide: str | None = None


class BookRead(BookBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    total_chunks: int
    created_at: datetime
