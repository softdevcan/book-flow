import enum

from sqlalchemy import Enum, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChunkStatus(str, enum.Enum):
    raw = "raw"
    in_review = "in_review"
    approved = "approved"


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("book_id", "sequence_number", name="uq_chunk_book_seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    translated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ChunkStatus] = mapped_column(
        Enum(ChunkStatus, name="chunk_status"), default=ChunkStatus.raw, nullable=False
    )
    editor_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    scene_context: Mapped[str | None] = mapped_column(Text, nullable=True)

    book: Mapped["Book"] = relationship(back_populates="chunks")  # noqa: F821
