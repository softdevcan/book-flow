from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.book import Book
from app.models.glossary import GlossaryTerm
from app.schemas.glossary import GlossaryTermCreate, GlossaryTermRead

router = APIRouter(tags=["glossary"])


@router.post(
    "/api/books/{book_id}/glossary",
    response_model=GlossaryTermRead,
    status_code=status.HTTP_201_CREATED,
)
def add_term(
    book_id: int,
    payload: GlossaryTermCreate,
    db: Session = Depends(get_db),
) -> GlossaryTerm:
    if db.get(Book, book_id) is None:
        raise HTTPException(status_code=404, detail="Book not found")

    term = (
        db.query(GlossaryTerm)
        .filter_by(book_id=book_id, source_term=payload.source_term)
        .one_or_none()
    )
    if term is None:
        term = GlossaryTerm(book_id=book_id, **payload.model_dump())
        db.add(term)
    else:
        term.target_term = payload.target_term

    db.commit()
    db.refresh(term)
    return term


@router.get("/api/books/{book_id}/glossary", response_model=list[GlossaryTermRead])
def list_terms(book_id: int, db: Session = Depends(get_db)) -> list[GlossaryTerm]:
    if db.get(Book, book_id) is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return (
        db.query(GlossaryTerm)
        .filter_by(book_id=book_id)
        .order_by(GlossaryTerm.source_term.asc())
        .all()
    )


@router.delete("/api/glossary/{term_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_term(term_id: int, db: Session = Depends(get_db)) -> None:
    term = db.get(GlossaryTerm, term_id)
    if term is None:
        raise HTTPException(status_code=404, detail="Glossary term not found")
    db.delete(term)
    db.commit()
