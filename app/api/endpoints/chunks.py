import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.book import Book
from app.models.chunk import Chunk
from app.models.translation_version import TranslationVersion
from app.schemas.chunk import (
    ChunkCreate,
    ChunkRead,
    ChunkUpdate,
    TranslationVersionRead,
)
from app.core.config import settings
from app.services.translator import (
    resolve_required_models,
    translate_book_batched,
    translate_chunk,
)


class TranslateRequest(BaseModel):
    provider: str | None = None
    # `model` is the legacy single-pass / Stage 1 override (kept for back-compat).
    # In two_stage mode the UI may instead send explicit per-stage models.
    model: str | None = None
    stage1_model: str | None = None
    stage2_model: str | None = None

router = APIRouter(tags=["chunks"])


def _require_models(req: TranslateRequest) -> None:
    """Reject a translate request whose pipeline has no model to run with.

    Stage defaults are intentionally empty, so a request that omits the model(s)
    must be rejected here (400) instead of failing later inside the background
    task with an opaque Ollama 404 / timeout.
    """
    resolved = resolve_required_models(
        model=req.model,
        stage1_model=req.stage1_model,
        stage2_model=req.stage2_model,
    )
    missing = [stage for stage, name in resolved.items() if not name]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=(
                "No model selected for: "
                + ", ".join(missing)
                + ". Pick a model in the UI (no default is configured)."
            ),
        )


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
    _require_models(overrides)
    background_tasks.add_task(
        translate_chunk,
        chunk_id,
        provider_name=overrides.provider,
        model=overrides.model,
        stage1_model=overrides.stage1_model,
        stage2_model=overrides.stage2_model,
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

    overrides = payload or TranslateRequest()
    _require_models(overrides)

    chunks = (
        db.query(Chunk)
        .filter_by(book_id=book_id)
        .order_by(Chunk.sequence_number.asc())
        .all()
    )

    if settings.TRANSLATION_PIPELINE == "two_stage":
        # One batched task that swaps the model once (all Stage 1, then all Stage 2),
        # instead of N per-chunk tasks that swap twice each.
        background_tasks.add_task(
            translate_book_batched,
            book_id,
            provider_name=overrides.provider,
            stage1_model=overrides.stage1_model or overrides.model,
            stage2_model=overrides.stage2_model,
        )
    else:
        for c in chunks:
            if c.status.value == "approved":
                continue
            background_tasks.add_task(
                translate_chunk,
                c.id,
                provider_name=overrides.provider,
                model=overrides.model,
                stage1_model=overrides.stage1_model,
                stage2_model=overrides.stage2_model,
            )
    return chunks


@router.get(
    "/api/chunks/{chunk_id}/versions",
    response_model=list[TranslationVersionRead],
)
def list_versions(chunk_id: int, db: Session = Depends(get_db)) -> list[TranslationVersion]:
    """All translation versions a chunk has received, newest first."""
    if db.get(Chunk, chunk_id) is None:
        raise HTTPException(status_code=404, detail="Chunk not found")
    return (
        db.query(TranslationVersion)
        .filter_by(chunk_id=chunk_id)
        .order_by(TranslationVersion.created_at.desc(), TranslationVersion.id.desc())
        .all()
    )


@router.post(
    "/api/chunks/{chunk_id}/versions/{version_id}/activate",
    response_model=ChunkRead,
)
def activate_version(
    chunk_id: int,
    version_id: int,
    db: Session = Depends(get_db),
) -> Chunk:
    """Make an older version the active one: mirror its text/notes onto the chunk."""
    chunk = db.get(Chunk, chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk not found")
    version = db.get(TranslationVersion, version_id)
    if version is None or version.chunk_id != chunk_id:
        raise HTTPException(status_code=404, detail="Version not found for this chunk")

    chunk.translated_text = version.translated_text
    chunk.editor_notes = version.editor_notes
    chunk.active_version_id = version.id
    db.commit()
    db.refresh(chunk)
    return chunk
