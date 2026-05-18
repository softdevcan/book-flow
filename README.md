# BookFlow

AI-assisted literary translation tool. Upload a book in **EPUB / PDF / DOCX / TXT**, BookFlow parses it, splits it into translation-friendly chunks, and translates each chunk from English into Turkish using a **local Ollama** model (or any future provider plugged into the abstraction).

The goal is literary "re-authoring", not literal translation: preserved voice, no translationese, strict glossary, per-book style guide.

## Features

- File ingest for EPUB, PDF, DOCX, TXT, Markdown.
- Paragraph-aware chunker with configurable max chunk size.
- Per-book style guide + glossary, enforced in every system prompt.
- Per-chunk scene context (form of address, mood, characters).
- Provider abstraction: Ollama today, OpenRouter stub for tomorrow.
- Per-request model override and a `/api/models` endpoint that lists installed Ollama models.
- Modern React + Tailwind UI: upload, library view, side-by-side source/translation, glossary panel, editor approval flow, live polling.

## Ports

| Service | Port |
|---|---|
| Backend API | **8200** |
| Frontend (Vite dev or nginx) | **5273** |
| Ollama (host) | **11434** |

## Quick start — Docker (recommended)

Ollama runs on the **host** (not inside Docker), so it can use your GPU and your existing model cache. The compose file points the backend at `http://host.docker.internal:11434`.

```powershell
# 1. Make sure Ollama is running on the host
ollama pull llama3.1:8b
ollama serve

# 2. Build and start the stack
docker compose up --build
```

- Frontend: http://localhost:5273
- Backend API + Swagger: http://localhost:8200/docs
- Health: http://localhost:8200/health

The SQLite database is persisted in the named volume `bookflow_data`. To wipe it: `docker compose down -v`.

### Configuration

Compose reads variables from a `.env` file in the project root (optional — defaults are fine). Copy the template and tweak:

```powershell
copy .env.example .env
```

## Quick start — local dev (no Docker)

### Backend (Python 3.13)

```powershell
python -m pip install -r requirements.txt
copy .env.example .env
ollama pull llama3.1:8b
ollama serve
python -m uvicorn main:app --host 0.0.0.0 --port 8200 --reload
```

- API base: http://localhost:8200
- Swagger: http://localhost:8200/docs

### Frontend (Node 18+)

```powershell
cd frontend
npm install
npm run dev
```

Vite serves on http://localhost:5273 and proxies `/api` and `/health` to the backend. Override the backend URL with `VITE_BACKEND_URL=... npm run dev` if needed.

## Typical workflow

1. Open the frontend.
2. Drag a file (EPUB / PDF / DOCX / TXT) into the **Upload** form, set an optional style guide.
3. Open the book. Add glossary terms (e.g. `Grid → Şebeke`, `ICE → BUZ`).
4. Pick a model from the **Model** dropdown (auto-populated from `ollama list`).
5. Click **Translate all pending** or translate chunks one by one.
6. Status pill on each chunk: `raw → in_review → approved`. Edit or approve translations in-place.

## Configuration

Edit `.env`. Defaults work for a local Ollama installation:

```dotenv
DATABASE_URL=sqlite:///./bookflow.db

LLM_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

OPENROUTER_API_KEY=
OPENROUTER_MODEL=

CORS_ORIGINS=["*"]
```

## Architecture

```
EPUB / PDF / DOCX / TXT
        │
        ▼
┌──────────────────────┐
│ app/services/ingest/ │  parse_upload(filename, bytes) → ParsedBook(text, title, author)
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ app/services/        │  chunk_text(text, max_chars) → list[str]
│   chunker.py         │
└──────────────────────┘
        │
        ▼
SQLite (books, chunks, glossary)
        │
        ▼  POST /api/chunks/{id}/translate (BackgroundTasks)
┌──────────────────────┐
│ translator.py        │  build_system_prompt + glossary + scene_context
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ services/llm/        │  LLMProvider.generate_json(system, user, TranslationOutput)
│   ollama_provider.py │
└──────────────────────┘
        │
        ▼
chunk.translated_text + editor_notes + status=in_review
```

See [CLAUDE.md](CLAUDE.md) for the deeper map (data model, API surface, conventions, scope boundaries).

## Project status

V1 — local, single-user, no migrations, no auth. See the "Out of scope" section in `CLAUDE.md` for the deferred list.

## License

TBD.
