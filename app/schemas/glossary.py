from pydantic import BaseModel, ConfigDict, Field


class GlossaryTermCreate(BaseModel):
    source_term: str = Field(min_length=1, max_length=255)
    target_term: str = Field(min_length=1, max_length=255)


class GlossaryTermRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    book_id: int
    source_term: str
    target_term: str
