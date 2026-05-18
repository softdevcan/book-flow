# CLAUDE.md

This file gives Claude Code (or any AI assistant) the context it needs to work productively in this repo.

## Project

**BookFlow** is an AI-assisted literary translation tool. Users upload a book in EPUB, PDF, DOCX, or TXT format. The backend parses the text, splits it into translation-friendly chunks, and translates each chunk from English into Turkish using a local Ollama model (with optional OpenRouter support). Every chunk preserves a glossary, a per-book style guide, and an optional per-chunk scene context.

Target output is **literary** Turkish — not a literal word-for-word rendering. The system prompt explicitly forbids "translationese" patterns (overuse of `tarafından`, `sahip olmak`, passive constructions, calqued idioms).

## Repository layout

```
book-flow/
├── main.py                          FastAPI entrypoint
├── requirements.txt
├── .env.example                     Copy to .env to override defaults
├── bookflow.db                      SQLite, auto-created on first run
├── app/
│   ├── core/config.py               pydantic-settings, reads .env
│   ├── db/                          SQLAlchemy 2.0 sync engine + session
│   ├── models/                      Book, Chunk (+ ChunkStatus), GlossaryTerm
│   ├── schemas/                     Pydantic request/response schemas
│   ├── api/endpoints/               books, chunks, glossary, models
│   └── services/
│       ├── ingest/                  epub/pdf/docx/txt parsers + dispatcher
│       ├── chunker.py               Paragraph-aware splitter
│       ├── translator.py            Background-task orchestrator
│       └── llm/                     Provider abstraction (Ollama, OpenRouter stub)
└── frontend/                        Vite + React + TypeScript + Tailwind UI
    └── src/
        ├── api.ts                   Typed fetch client
        ├── App.tsx                  View switcher (BookList ↔ BookDetail)
        ├── components/              UploadForm, ModelPicker, ChunkCard, GlossaryPanel
        └── types.ts                 Shared TypeScript types mirroring backend schemas
```

## Ports

| Service | Port |
|---|---|
| Backend (FastAPI / uvicorn) | **8200** |
| Frontend (Vite dev or nginx) | **5273** |
| Ollama (host machine) | **11434** |

Both ports are deliberately offset from defaults (8000, 5173) to avoid collisions with other dev stacks.

## Running locally (no Docker)

### Prerequisites
- Python 3.13
- Node 18+ / npm 8+
- [Ollama](https://ollama.com) running on `http://localhost:11434`
- A pulled model, default `llama3.1:8b`: `ollama pull llama3.1:8b`

### Backend
```powershell
python -m pip install -r requirements.txt
copy .env.example .env
python -m uvicorn main:app --host 0.0.0.0 --port 8200 --reload
```
Backend listens on `http://localhost:8200`. Swagger UI at `/docs`.

### Frontend
```powershell
cd frontend
npm install
npm run dev
```
Dev server on `http://localhost:5273` with Vite proxying `/api` and `/health` to the backend. Override with `VITE_BACKEND_URL=http://...` if the backend is elsewhere.

## Running with Docker

The compose stack runs **backend + frontend** in containers; **Ollama stays on the host** so it can use GPU and existing model cache.

```powershell
ollama serve                    # on host
docker compose up --build       # in repo root
```

- Frontend at http://localhost:5273 (nginx, proxies `/api` and `/health` to `backend:8200`)
- Backend at http://localhost:8200
- SQLite persists in the named volume `bookflow_data` (mounted at `/data` inside the backend container)

Inside the backend container, `OLLAMA_HOST` defaults to `http://host.docker.internal:11434`. The compose file adds `extra_hosts: host.docker.internal:host-gateway` so it resolves on Linux too.

Stop everything: `docker compose down`. Wipe DB too: `docker compose down -v`.

## Configuration (.env)

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./bookflow.db` | Any SQLAlchemy URL works. |
| `LLM_PROVIDER` | `ollama` | `ollama` \| `openrouter` (stub). |
| `OLLAMA_HOST` | `http://localhost:11434` | |
| `OLLAMA_MODEL` | `llama3.1:8b` | Default model when no per-request override. |
| `OLLAMA_TEMPERATURE` | `0.4` | Lower = more conservative. |
| `OLLAMA_TIMEOUT_SECONDS` | `180` | Long, because literary chunks are slow. |
| `OPENROUTER_API_KEY` | _(unset)_ | Reserved for future provider. |
| `OPENROUTER_MODEL` | _(unset)_ | |
| `CORS_ORIGINS` | `["*"]` | JSON-encoded list. |

## Key data model

- `books` — title, author, style_guide (text), total_chunks, created_at
- `chunks` — book_id FK (cascade), sequence_number (unique per book), source_text, translated_text (nullable), status (`raw` | `in_review` | `approved`), editor_notes (JSON-encoded list of strings), scene_context (nullable)
- `glossary_terms` — book_id FK (cascade), source_term, target_term (unique per book + source)

Schema is created via `Base.metadata.create_all` in the FastAPI `lifespan`. **No Alembic migrations yet** — if you change a model, delete `bookflow.db` and let it recreate, or add Alembic.

## API surface

Mounted in `main.py`:

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/books` | Create a book by JSON. |
| POST | `/api/books/upload` | Multipart upload, parse, auto-chunk, persist. |
| GET / PATCH / DELETE | `/api/books/{id}` | CRUD. |
| GET | `/api/books` | List all. |
| POST | `/api/books/{book_id}/chunks` | Bulk insert chunks manually. |
| GET | `/api/books/{book_id}/chunks` | Ordered list. |
| GET / PATCH | `/api/chunks/{id}` | Read / edit translation + status. |
| POST | `/api/chunks/{id}/translate` | Queue background translation. Body: `{ "provider"?, "model"? }`. |
| POST | `/api/books/{book_id}/translate` | Queue all non-approved chunks. |
| GET / POST / DELETE | `/api/books/{book_id}/glossary` and `/api/glossary/{id}` | Glossary CRUD (upsert on POST). |
| GET | `/api/models?provider=ollama` | List installed Ollama models for UI dropdowns. |
| GET | `/health` | Liveness + active provider name. |

## Translation flow

1. `POST /api/chunks/{id}/translate` schedules `translate_chunk` via FastAPI `BackgroundTasks` and returns 202 immediately.
2. The background task opens its **own** `SessionLocal`, loads the chunk + parent book + glossary, and builds the system prompt (`app/services/translator.py:build_system_prompt`).
3. The active LLM provider (default Ollama) is asked for **strict JSON** matching `TranslationOutput` (`translated_text`, `editor_notes`). One automatic retry on Pydantic/JSON failure.
4. On success: chunk gets `translated_text`, `editor_notes` (JSON-encoded), `status = in_review`.
5. On failure: chunk stays/returns to `status = raw` and `editor_notes` records `translation_failed: <reason>`. No HTTP 500 is surfaced because it's an out-of-request task.
6. The frontend polls `GET /api/books/{id}/chunks` every 3 s while any chunk is still `raw` with no translation, then stops automatically.

## Provider selection

- The factory `get_provider(provider?, model?, temperature?)` in `app/services/llm/__init__.py` resolves the provider name (defaults to `settings.LLM_PROVIDER`) and forwards `model` / `temperature` to the concrete provider.
- The chunks router exposes `provider` and `model` fields on the `POST /api/chunks/{id}/translate` body. The UI sends `model` to switch between locally installed Ollama models per request.
- To add a new provider: subclass `LLMProvider` (in `app/services/llm/base.py`), implement `generate_json` and `list_models`, then register it in the factory's `match` block. Keep the JSON-mode contract identical so the prompt stays portable.

## Coding conventions

- Python: 3.13, type-annotated, SQLAlchemy 2.0 `Mapped[...]` style, Pydantic 2 (`model_config = ConfigDict(...)`). Avoid `from __future__ import annotations` unless needed.
- All user-facing strings and docs in **English**. The translation **output** is Turkish — never translate prompts, comments, identifiers, or UI labels.
- Frontend: React 18 functional components, TypeScript strict mode, Tailwind utility classes. No state library — `useState` + `useEffect` are sufficient.
- The Vite dev server proxies `/api` to the backend, so the frontend always uses relative paths.

## What's intentionally out of scope (v1)

- Alembic migrations
- Auth / multi-user
- Streaming translation responses
- Rate limiting / retry budgets beyond the one-shot Pydantic-fail retry
- Export to translated EPUB/PDF
- OpenRouter (stub only — raises `LLMProviderError`)

When you add any of these, update this file in the same PR.
