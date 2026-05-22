from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TranslationVersion(Base):
    """An immutable record of one translation a chunk received.

    Every translate run inserts a new row; the parent chunk points at one of
    them via `chunk.active_version_id` (the version shown/exported by default).
    Lets the user compare versions produced by different models or pipelines.
    """

    __tablename__ = "translation_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chunk_id: Mapped[int] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    translated_text: Mapped[str] = mapped_column(Text, nullable=False)
    editor_notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-encoded list
    pipeline: Mapped[str | None] = mapped_column(String(32), nullable=True)  # single | two_stage
    stage1_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    stage2_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    chunk: Mapped["Chunk"] = relationship(  # noqa: F821
        back_populates="versions", foreign_keys=[chunk_id]
    )
