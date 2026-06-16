from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.book import Book
from app.models.chunk import Chunk
from app.schemas.book import BookCreate, BookRead, BookUpdate
from app.schemas.language import SUPPORTED_CODES
from app.services.chunker import DEFAULT_MAX_CHARS, DEFAULT_MIN_CHARS, chunk_text
from app.services.ingest import parse_upload
from app.services.ingest.dispatcher import UnsupportedFormatError
from app.services.lang_detect import detect_language

router = APIRouter(prefix="/api/books", tags=["books"])

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


def _validate_language_pair(source: str, target: str) -> None:
    if source not in SUPPORTED_CODES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported source_language '{source}'. Supported: {sorted(SUPPORTED_CODES)}",
        )
    if target not in SUPPORTED_CODES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported target_language '{target}'. Supported: {sorted(SUPPORTED_CODES)}",
        )
    if source == target:
        raise HTTPException(
            status_code=400,
            detail="source_language and target_language must differ",
        )
"""
1   
2   
3   
4   
5   
6   
7
"""

@router.post("", response_model=BookRead, status_code=status.HTTP_201_CREATED)
def create_book(payload: BookCreate, db: Session = Depends(get_db)) -> Book:
    _validate_language_pair(payload.source_language, payload.target_language)
    book = Book(**payload.model_dump())
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


@router.post(
    "/upload",
    response_model=BookRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_book(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    author: str | None = Form(default=None),
    style_guide: str | None = Form(default=None),
    # Source is optional: when omitted, the server auto-detects from the parsed
    # text (lingua-py with LLM fallback). Target is required — the user must
    # pick the language they want to translate into.
    source_language: str | None = Form(default=None),
    target_language: str = Form(...),
    max_chars: int = Form(default=DEFAULT_MAX_CHARS, ge=200, le=8000),
    min_chars: int = Form(default=DEFAULT_MIN_CHARS, ge=0, le=2000),
    db: Session = Depends(get_db),
) -> Book:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 50 MB)")

    try:
        parsed = parse_upload(file.filename, data)
    except UnsupportedFormatError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {exc}") from exc

    if not parsed.text.strip():
        raise HTTPException(status_code=422, detail="No extractable text in file")

    if not source_language:
        # Fall back to detection if the UI didn't run the /api/languages/detect
        # preview flow (e.g. curl or scripted clients).
        detected = await detect_language(parsed.text)
        source_language = detected.code

    _validate_language_pair(source_language, target_language)

    pieces = chunk_text(parsed.text, max_chars=max_chars, min_chars=min_chars)
    if not pieces:
        raise HTTPException(status_code=422, detail="Chunker produced no chunks")

    book = Book(
        title=title or parsed.title or file.filename,
        author=author or parsed.author,
        style_guide=style_guide,
        source_language=source_language,
        target_language=target_language,
        total_chunks=len(pieces),
    )
    db.add(book)
    db.flush()

    db.add_all(
        Chunk(book_id=book.id, sequence_number=i, source_text=text)
        for i, text in enumerate(pieces)
    )
    db.commit()
    db.refresh(book)
    return book


@router.get("", response_model=list[BookRead])
def list_books(db: Session = Depends(get_db)) -> list[Book]:
    return db.query(Book).order_by(Book.id.desc()).all()


@router.get("/{book_id}", response_model=BookRead)
def get_book(book_id: int, db: Session = Depends(get_db)) -> Book:
    book = db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@router.patch("/{book_id}", response_model=BookRead)
def update_book(book_id: int, payload: BookUpdate, db: Session = Depends(get_db)) -> Book:
    book = db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(book, field, value)
    db.commit()
    db.refresh(book)
    return book


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(book_id: int, db: Session = Depends(get_db)) -> None:
    book = db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    db.delete(book)
    db.commit()
