import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.book import Book
from app.models.chunk import Chunk
from app.schemas.chunk import ChunkCreate, ChunkRead, ChunkUpdate
from app.services.translator import translate_chunk


class TranslateRequest(BaseModel):
    provider: str | None = None
    model: str | None = None

router = APIRouter(tags=["chunks"])


@router.post(
    "/api/books/{book_id}/chunks",
    response_model=list[ChunkRead],
    status_code=status.HTTP_201_CREATED,
)
def create_chunks(
    book_id: int,
    payload: list[ChunkCreate],
    db: Session = Depends(get_db),
) -> list[Chunk]:
    book = db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    if not payload:
        raise HTTPException(status_code=400, detail="Empty chunk list")

    chunks = [Chunk(book_id=book_id, **item.model_dump()) for item in payload]
    db.add_all(chunks)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Duplicate sequence_number for this book",
        ) from exc

    book.total_chunks = db.query(Chunk).filter_by(book_id=book_id).count()
    db.commit()
    for c in chunks:
        db.refresh(c)
    return chunks


@router.get("/api/books/{book_id}/chunks", response_model=list[ChunkRead])
def list_chunks(book_id: int, db: Session = Depends(get_db)) -> list[Chunk]:
    if db.get(Book, book_id) is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return (
        db.query(Chunk)
        .filter_by(book_id=book_id)
        .order_by(Chunk.sequence_number.asc())
        .all()
    )


@router.get("/api/chunks/{chunk_id}", response_model=ChunkRead)
def get_chunk(chunk_id: int, db: Session = Depends(get_db)) -> Chunk:
    chunk = db.get(Chunk, chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk not found")
    return chunk


@router.patch("/api/chunks/{chunk_id}", response_model=ChunkRead)
def update_chunk(
    chunk_id: int,
    payload: ChunkUpdate,
    db: Session = Depends(get_db),
) -> Chunk:
    chunk = db.get(Chunk, chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk not found")

    data = payload.model_dump(exclude_unset=True)
    if "editor_notes" in data and data["editor_notes"] is not None:
        data["editor_notes"] = json.dumps(data["editor_notes"], ensure_ascii=False)

    for field, value in data.items():
        setattr(chunk, field, value)
    db.commit()
    db.refresh(chunk)
    return chunk


@router.post(
    "/api/chunks/{chunk_id}/translate",
    response_model=ChunkRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_translate(
    chunk_id: int,
    background_tasks: BackgroundTasks,
    payload: TranslateRequest | None = None,
    db: Session = Depends(get_db),
) -> Chunk:
    chunk = db.get(Chunk, chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk not found")
    overrides = payload or TranslateRequest()
    background_tasks.add_task(
        translate_chunk,
        chunk_id,
        provider_name=overrides.provider,
        model=overrides.model,
    )
    return chunk


@router.post(
    "/api/books/{book_id}/translate",
    response_model=list[ChunkRead],
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_translate_book(
    book_id: int,
    background_tasks: BackgroundTasks,
    payload: TranslateRequest | None = None,
    db: Session = Depends(get_db),
) -> list[Chunk]:
    """Queue translation for every non-approved chunk of a book."""
    if db.get(Book, book_id) is None:
        raise HTTPException(status_code=404, detail="Book not found")

    chunks = (
        db.query(Chunk)
        .filter_by(book_id=book_id)
        .order_by(Chunk.sequence_number.asc())
        .all()
    )
    overrides = payload or TranslateRequest()
    for c in chunks:
        if c.status.value == "approved":
            continue
        background_tasks.add_task(
            translate_chunk,
            c.id,
            provider_name=overrides.provider,
            model=overrides.model,
        )
    return chunks
