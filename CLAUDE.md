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
| `TRANSLATION_PIPELINE` | `single` | `single` (one pass) \| `two_stage` (Builder → Artist). |
| `OLLAMA_HOST` | `http://localhost:11434` | |
| `OLLAMA_MODEL` | `llama3.1:8b` | Default model when no per-request override (single pass). |
| `OLLAMA_STAGE1_MODEL` | `qwen2.5:14b` | Two-stage Builder. Per-request `model` overrides this. |
| `OLLAMA_STAGE2_MODEL` | `gemma2:9b` | Two-stage Artist (literary refinement). |
| `OLLAMA_TEMPERATURE` | `0.4` | Lower = more conservative. |
| `OLLAMA_TIMEOUT_SECONDS` | `400` | Long, and raised for two-stage: two passes + model swap. |
| `OPENROUTER_API_KEY` | _(unset)_ | Reserved for future provider. |
| `OPENROUTER_MODEL` | _(unset)_ | |
| `CORS_ORIGINS` | `["*"]` | JSON-encoded list. |

## Key data model

- `books` — title, author, style_guide (text), total_chunks, created_at
- `chunks` — book_id FK (cascade), sequence_number (unique per book), source_text, translated_text (nullable), status (`raw` | `in_review` | `approved`), editor_notes (JSON-encoded list of strings), scene_context (nullable), active_version_id (nullable FK → translation_versions; the chosen version, mirrored into translated_text)
- `translation_versions` — chunk_id FK (cascade), translated_text, editor_notes (JSON list), pipeline (`single`|`two_stage`), stage1_model, stage2_model, created_at. One row per translation run; lets the user compare/revert. `chunk.translated_text` always mirrors the active version, so export/UI need no version awareness.
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
| GET | `/api/chunks/{id}/versions` | List all translation versions (newest first). |
| POST | `/api/chunks/{id}/versions/{version_id}/activate` | Make an older version active (mirrors its text onto the chunk). |
| POST | `/api/chunks/{id}/translate` | Queue background translation. Body: `{ "provider"?, "model"?, "stage1_model"?, "stage2_model"? }`. |
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

### Two-stage pipeline (`TRANSLATION_PIPELINE=two_stage`)

Two sequential LLM passes. `OLLAMA_STAGE1_MODEL` / `OLLAMA_STAGE2_MODEL` are **empty by default** — the model must be picked per request (UI shows two `ModelPicker`s); the translate endpoints return 400 if no model resolves.

1. **Stage 1 — Builder**: faithful EN→TR translation, fidelity over polish. Reuses `build_system_prompt`.
2. **Stage 2 — Artist**: receives the English source **and** the Stage 1 Turkish draft, rewrites it into literary Turkish, strips translationese. Uses `build_stage2_system_prompt`. Both stages emit the same `TranslationOutput` schema.

**Two execution modes (by endpoint):**

- **Single chunk** (`POST /api/chunks/{id}/translate`) → `_run_two_stage`: runs Stage 1 then Stage 2 for that one chunk (swaps the model twice).
- **Whole book** (`POST /api/books/{id}/translate`) → `translate_book_batched`: **batched by stage**. Phase 1 loads the Builder once and translates *every* pending chunk; Phase 2 loads the Artist once and refines *every* chunk that cleared Phase 1. The Ollama model swaps **once** instead of twice per chunk — essential when the two models can't share VRAM (e.g. an 8 GB GPU). Phase tracking uses `editor_notes` markers (`pipeline: stage1_done` → `pipeline: two_stage (builder+artist)`); no schema change.

Failure handling:
- **Stage 1 fails** → chunk → `raw`, note `stage1_failed: <reason>` (single-chunk path uses `translation_failed:`). The batch **skips it and continues**; Phase 2 only runs on chunks tagged `stage1_done`.
- **Stage 2 fails** → the **Stage 1 draft is kept** (`status = in_review`) with an appended `stage2_failed: <reason>` note, so the reviewer always gets a usable draft.

Both paths share `_persist_translation` (ratio check + notes + status + commit) and the provider's built-in `<think>`-strip + one-shot JSON-repair retry. Pull both chosen models first, e.g. `ollama pull qwen3.5:9b gemma4:e4b`.

**Versioning:** every `_persist_translation` call inserts a `TranslationVersion` row (text + pipeline + stage models + created_at) and points `chunk.active_version_id` at it (newest = active), mirroring its text into `chunk.translated_text`. So a chunk accumulates a history; the user can re-activate an older version via the activate endpoint. In two-stage book batches a chunk gets a Stage-1 version then a Stage-2 version, so the Builder draft and Artist refinement are both comparable.

## Provider selection

- The factory `get_provider(provider?, model?, temperature?)` in `app/services/llm/__init__.py` resolves the provider name (defaults to `settings.LLM_PROVIDER`) and forwards `model` / `temperature` to the concrete provider.
- The chunks router exposes `provider`, `model`, `stage1_model`, and `stage2_model` fields on the `POST /api/chunks/{id}/translate` body. In single-pass mode the UI sends `model`. In two-stage mode the UI shows two `ModelPicker`s ("Stage 1 (Builder)" / "Stage 2 (Artist)") and sends `stage1_model` / `stage2_model`; each falls back to its `.env` default when omitted. `stage1_model` takes precedence over the legacy `model` for Stage 1.
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
