import logging
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, inspect

from app.api.endpoints import books, chunks, glossary, languages, models as models_endpoint
from app.core.config import settings
from app.models import Book, Chunk, GlossaryTerm  # noqa: F401  (register mappers)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _run_migrations() -> None:
    """Bring the DB to the latest revision on startup.

    Replaces the previous `Base.metadata.create_all` so schema changes flow through
    Alembic (incl. existing-DB upgrades). If the DB already has tables but no
    `alembic_version` row, we stamp it at the initial revision first so the
    follow-up revisions can run cleanly (handles upgrades from the pre-Alembic era).
    """
    repo_root = Path(__file__).resolve().parent
    cfg = Config(str(repo_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(repo_root / "migrations"))
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

    engine = create_engine(settings.DATABASE_URL)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "books" in tables and "alembic_version" not in tables:
        logger.info("Pre-Alembic DB detected; stamping at 0001 before upgrade")
        command.stamp(cfg, "0001")
    engine.dispose()

    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(_: FastAPI):
    _run_migrations()
    yield


app = FastAPI(title="BookFlow API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(books.router)
app.include_router(chunks.router)
app.include_router(glossary.router)
app.include_router(languages.router)
app.include_router(models_endpoint.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "provider": settings.LLM_PROVIDER}
