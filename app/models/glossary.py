from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class GlossaryTerm(Base):
    __tablename__ = "glossary_terms"
    __table_args__ = (
        UniqueConstraint("book_id", "source_term", name="uq_glossary_book_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_term: Mapped[str] = mapped_column(String(255), nullable=False)
    target_term: Mapped[str] = mapped_column(String(255), nullable=False)

    book: Mapped["Book"] = relationship(back_populates="glossary")  # noqa: F821
