# Plan: Multilingual Literary Translation

## Context

BookFlow currently hardwires English→Turkish across the entire stack:

- System prompts in [app/services/translator.py:25](../app/services/translator.py#L25) and [app/services/translator.py:78](../app/services/translator.py#L78) embed TR-specific translationese rules (`tarafından`, `sahip olmak`, `bunun hakkında`) and call out "English into ... Turkish" by name.
- [app/models/book.py](../app/models/book.py) has no `source_language` / `target_language` columns. Same for [app/schemas/book.py](../app/schemas/book.py), [app/models/chunk.py](../app/models/chunk.py), and [app/models/translation_version.py](../app/models/translation_version.py).
- Upload + chunk endpoints accept no language params.
- [app/services/chunker.py:21](../app/services/chunker.py#L21) sentence-split regex only knows Latin + Turkish uppercase (`[A-ZÇĞİÖŞÜ...]`) — Cyrillic/Greek/extended Latin sentences break.
- Frontend hardcodes `EN → TR` in header ([App.tsx:20](../frontend/src/App.tsx#L20)), "Source (EN)" / "Translation (TR)" labels ([ChunkCard.tsx:103,112](../frontend/src/components/ChunkCard.tsx#L103)), `_TR.txt` export suffix ([BookDetail.tsx:57](../frontend/src/views/BookDetail.tsx#L57)), and Turkish UI error strings in [GlossaryPanel.tsx](../frontend/src/components/GlossaryPanel.tsx) (violates CLAUDE.md "all UI strings in English").

Goal: support multiple source **and** target languages — including major literary languages (French, German, Spanish, Russian, Italian, Portuguese) — while preserving the existing TR translation quality. The system must auto-detect source language at upload time, let the user confirm/override, and lock the pair per book.

### Decisions locked with the user

1. **Source language is auto-detected on upload.** Hybrid: local lib (`lingua-py`) on parsed text first; if confidence < 0.7, an Ollama LLM fallback classifies. UI shows the suggestion pre-filled and the user may override.
2. **Target language is picked from a curated 8-language dropdown:** TR, EN, FR, DE, ES, RU, IT, PT.
3. **Language pair is fixed per book.** Stored as `source_language` + `target_language` on the `books` row, immutable after creation. Glossary, prompts, chunks all inherit.
4. **Per-language prompt registry.** A small `LANG_RULES` dict keyed by ISO 639-1 code holds optional `stage1_rules` / `stage2_rules` fragments. Missing entries fall through to a generic block — quality stays at current TR level for TR, generic for others until rules are tuned.
5. **Alembic introduced now** for long-term migration health. Replaces the current `Base.metadata.create_all` on lifespan startup. Update CLAUDE.md to drop the "no Alembic migrations" out-of-scope line.

---

## Current state (verified)

- Translator: [app/services/translator.py](../app/services/translator.py) — `build_system_prompt` (Stage 1 / single-pass) and `build_stage2_system_prompt` (Artist) format three placeholders (`style_guide`, `glossary_block`, `scene_context`) into TR-locked templates. `translate_chunk`, `_run_two_stage`, and `translate_book_batched` already load the parent `Book` and glossary — language fields can be threaded through with **no signature changes** to public callers, since the `Book` already carries them.
- Models: [app/models/book.py:9-27](../app/models/book.py#L9-L27) — no language columns. Glossary ([app/models/glossary.py](../app/models/glossary.py)) is book-scoped only.
- Schemas: [app/schemas/book.py:6-28](../app/schemas/book.py#L6-L28) — `BookBase`, `BookCreate`, `BookUpdate`, `BookRead` have no language fields.
- Endpoints: [app/api/endpoints/books.py:31-78](../app/api/endpoints/books.py) — `upload_book` accepts `file`, `title`, `author`, `style_guide`, `max_chars`, `min_chars`. No language form fields.
- Chunker: [app/services/chunker.py:21](../app/services/chunker.py#L21) — `_SENTENCE_SPLIT` uses Latin+Turkish capitals only.
- Frontend types: [frontend/src/types.ts](../frontend/src/types.ts) — neutral field names (`source_text`, `translated_text`). Adding language fields is additive, no rename churn.
- Provider layer: [app/services/llm/__init__.py](../app/services/llm/__init__.py), [app/services/llm/base.py](../app/services/llm/base.py), [app/services/llm/ollama_provider.py](../app/services/llm/ollama_provider.py) — fully language-agnostic. **No change needed.**
- Persistence: [_persist_translation](../app/services/translator.py#L123) and [resolve_required_models](../app/services/translator.py#L245) — fully language-agnostic. **No change needed.**

**Conclusion:** the change concentrates in (1) DB schema (languages on `books`), (2) prompt registry, (3) detection service + endpoint, (4) upload form. All translator orchestration code remains intact — it just reads two extra fields off the already-loaded `Book`.

---

## Implementation plan

### 1. Dependencies + migrations

- **`requirements.txt`**: add `alembic`, `lingua-language-detector`, `regex` (for Unicode-aware sentence splitting).
- **Alembic init**: `alembic.ini` + `migrations/env.py` (configured to import `app.db.base.Base` and target the same `DATABASE_URL` as the app).
- **`migrations/versions/0001_initial.py`**: autogenerated from current models. Snapshot of today's schema.
- **`migrations/versions/0002_add_book_languages.py`**:
  - `op.add_column("books", sa.Column("source_language", sa.String(8), nullable=False, server_default="en"))`
  - `op.add_column("books", sa.Column("target_language", sa.String(8), nullable=False, server_default="tr"))`
  - Downgrade drops both. `server_default` only for backfill; new rows must set explicitly via the API.
- **[main.py](../main.py) lifespan**: replace `Base.metadata.create_all(...)` with a programmatic `alembic upgrade head` call (use `alembic.command.upgrade(Config("alembic.ini"), "head")`). Dev flow stays one command.

### 2. `app/core/config.py`

No new env vars — language behavior lives in the DB + prompt registry. Drop the hardcoded "EN→TR" comment near `TRANSLATION_PIPELINE`.

### 3. `app/models/book.py`

```python
source_language: Mapped[str] = mapped_column(String(8), nullable=False)
target_language: Mapped[str] = mapped_column(String(8), nullable=False)
```

### 4. `app/schemas/book.py`

- `BookBase`: add `source_language: str = Field(min_length=2, max_length=8)` and `target_language: str = Field(min_length=2, max_length=8)`.
- `BookCreate`: inherits, both required.
- `BookUpdate`: keep both as `None` defaults but ignored server-side (immutable post-create — enforced in the PATCH handler).
- `BookRead`: inherits via `from_attributes`.

### 5. New `app/schemas/language.py`

```python
class LangOption(BaseModel):
    code: str
    name: str

class LanguageDetectionResponse(BaseModel):
    code: str
    confidence: float
    method: Literal["lib", "llm"]

SUPPORTED_TARGETS: list[LangOption] = [
    LangOption(code="tr", name="Turkish"),
    LangOption(code="en", name="English"),
    LangOption(code="fr", name="French"),
    LangOption(code="de", name="German"),
    LangOption(code="es", name="Spanish"),
    LangOption(code="ru", name="Russian"),
    LangOption(code="it", name="Italian"),
    LangOption(code="pt", name="Portuguese"),
]
SUPPORTED_CODES = {opt.code for opt in SUPPORTED_TARGETS}
```

### 6. New `app/services/lang_detect.py`

```python
async def detect_language(text: str) -> LanguageDetectionResponse:
    snippet = text[:3000]
    # Stage A: lingua
    detector = _build_detector()  # cached: LanguageDetectorBuilder.from_all_languages().build()
    confidences = detector.compute_language_confidence_values(snippet)
    top = max(confidences, key=lambda c: c.value)
    if top.value >= 0.7:
        return LanguageDetectionResponse(code=top.language.iso_code_639_1.name.lower(),
                                         confidence=top.value, method="lib")
    # Stage B: LLM fallback
    provider = get_provider()  # uses settings.LLM_PROVIDER + default model
    sys_prompt = "Classify the language of the user's text. Respond strictly with JSON: {\"code\": <ISO 639-1 lowercase>}"
    result = await provider.generate_json(sys_prompt, snippet, _LangCodeSchema)
    return LanguageDetectionResponse(code=result.code, confidence=0.0, method="llm")
```

Cache the lingua detector at module level (initialization is expensive — ~100 ms).

### 7. New `app/services/llm/lang_rules.py`

```python
@dataclass(frozen=True)
class LangRules:
    name: str
    stage1_rules: str | None = None
    stage2_rules: str | None = None

# Extracted verbatim from current translator.py L28 to preserve TR quality:
TR_STAGE1_RULES = """- Avoid \"AI Turkish\" (Translationese): Do not follow English sentence structures or passive voice traps (e.g., avoid overusing \"tarafından\", \"bunun hakkında\", \"sahip olmak\")..."""

# Extracted verbatim from current translator.py L81:
TR_STAGE2_RULES = """- Eliminate \"translationese\": remove overused passive voice, \"tarafından\", \"sahip olmak\", \"bunun hakkında\"..."""

# Seed rules for the other locked targets — short, can be expanded over time:
FR_STAGE1_RULES = "- Avoid Anglicism: do not calque English syntax (\"être en train de\" overuse, literal \"avoir\" possessives where French prefers nominal phrasing)..."
DE_STAGE1_RULES = "- Avoid English-shaped sentence order: respect German V2 / verb-final clause structure; do not transliterate Anglo-Saxon participle chains..."
# ES, RU, IT, PT — start with no per-language rules; rely on generic block + model knowledge.

GENERIC_STAGE1_RULES = "- Avoid literal calques; translate idioms by emotional/cultural equivalent.\n- Match register to scene context.\n- Preserve every clause, tense, and nuance — fidelity first; polish comes in Stage 2."
GENERIC_STAGE2_RULES = "- Eliminate translationese typical of the target language: drop calqued source-language structures, recast as idiomatic literary prose.\n- Preserve meaning exactly. Dialogue must sound native."

LANG_RULES: dict[str, LangRules] = {
    "tr": LangRules("Turkish", TR_STAGE1_RULES, TR_STAGE2_RULES),
    "en": LangRules("English"),
    "fr": LangRules("French", FR_STAGE1_RULES),
    "de": LangRules("German", DE_STAGE1_RULES),
    "es": LangRules("Spanish"),
    "ru": LangRules("Russian"),
    "it": LangRules("Italian"),
    "pt": LangRules("Portuguese"),
}

def resolve_rules(code: str) -> LangRules:
    return LANG_RULES.get(code, LangRules(name=code.upper()))

def stage1_block(code: str) -> str:
    return resolve_rules(code).stage1_rules or GENERIC_STAGE1_RULES

def stage2_block(code: str) -> str:
    return resolve_rules(code).stage2_rules or GENERIC_STAGE2_RULES
```

### 8. `app/services/translator.py` — template rewrite

Rewrite `SYSTEM_PROMPT_TEMPLATE` and `STAGE2_SYSTEM_PROMPT_TEMPLATE` so the language pair is interpolated:

```python
SYSTEM_PROMPT_TEMPLATE = """You are an elite literary translator and editor specializing in translating books from {source_name} into fluent, natural, and evocative {target_name}. Your goal is not a literal word-for-word translation, but a "re-authoring" of the text in {target_name} while preserving the original author's voice, subtext, emotional resonance, and pacing.

CRITICAL TRANSLATION GUIDELINES:
{stage1_rules_block}
- Cultural Adaptation: Translate idioms, metaphors, and cultural references into their closest emotional or traditional {target_name} equivalents, not literal calques.
- Character Voice: Dialogue must sound like something a real native {target_name} speaker would actually say...
- Strict Glossary Adherence: ...
- Proper Nouns: ...
- Completeness First: ...

<style_guide>{style_guide}</style_guide>
...
"""
```

Same treatment for Stage 2. The Stage 2 user-prompt tags become generic:

```python
stage2_user = (
    f"<source_text>\n{chunk.source_text}\n</source_text>\n\n"
    f"<draft_translation>\n{s1.translated_text}\n</draft_translation>"
)
```

Change the builder signatures from `(style_guide, glossary, scene_context)` to `(book, glossary, scene_context)` — the book already carries both language codes plus the style guide:

```python
def build_system_prompt(book: Book, glossary, scene_context) -> str:
    rules = resolve_rules(book.target_language)
    source_name = resolve_rules(book.source_language).name
    return SYSTEM_PROMPT_TEMPLATE.format(
        source_name=source_name,
        target_name=rules.name,
        stage1_rules_block=stage1_block(book.target_language),
        style_guide=book.style_guide or "(no style guide provided)",
        glossary_block=_render_glossary(glossary),
        scene_context=scene_context or "(no scene context provided)",
    )
```

Update all three call sites — [_run_two_stage](../app/services/translator.py#L180), [translate_book_batched](../app/services/translator.py#L300), and the single-pass branch in [translate_chunk](../app/services/translator.py#L416) — to pass `book` instead of `book.style_guide`. No language threading needed beyond that; the book is already loaded.

Update doc strings / comments that say "EN→TR" → "source→target".

### 9. `app/services/chunker.py`

Replace `_SENTENCE_SPLIT` with a Unicode-aware regex using the `regex` package:

```python
import regex
_SENTENCE_SPLIT = regex.compile(r"(?<=[.!?…])\s+(?=[\p{Lu}\"'(])")
```

`\p{Lu}` matches any Unicode uppercase letter — covers Cyrillic, Greek, all Latin variants, plus Turkish capitals.

### 10. Endpoints

- **[app/api/endpoints/books.py](../app/api/endpoints/books.py)**:
  - `POST /api/books/upload`: add form fields `source_language: str | None = Form(None)` and `target_language: str = Form(...)`. If `source_language` is omitted, server runs `detect_language` on the parsed text and uses the result. Validate both against `SUPPORTED_CODES`. If equal, return 400 ("source and target language must differ").
  - `POST /api/books`: require both language fields via the updated `BookCreate` schema.
  - `PATCH /api/books/{id}`: reject changes to `source_language` / `target_language` if provided in the body (return 400 or silently ignore — pick 400 for clarity).
- **New `app/api/endpoints/languages.py`**:
  - `POST /api/languages/detect` — body `{ "text": str }` (or accept multipart for direct-from-file detection). Returns `LanguageDetectionResponse`. Used by the UI to call detection *before* the upload form is submitted, so the user sees and can change the suggestion.
  - `GET /api/languages` — returns `SUPPORTED_TARGETS`.
- **[main.py](../main.py)**: mount the new languages router.

### 11. Frontend

- **[frontend/src/types.ts](../frontend/src/types.ts)**: add `source_language: string` and `target_language: string` to `Book`. New types: `LangOption { code: string; name: string }`, `LangDetection { code: string; confidence: number; method: "lib" | "llm" }`.
- **[frontend/src/api.ts](../frontend/src/api.ts)**: add `detectLanguage(text: string): Promise<LangDetection>` and `getSupportedLanguages(): Promise<LangOption[]>`. Update `uploadBook` to include `source_language` and `target_language` in the FormData.
- **[frontend/src/components/UploadForm.tsx](../frontend/src/components/UploadForm.tsx)**:
  - On file pick: read the first ~5 KB client-side as text, POST it to `/api/languages/detect`. Pre-fill the **Source language** dropdown with the returned code and show a small helper line: "Detected: French (lib, conf 0.94)".
  - **Target language** dropdown populated from `GET /api/languages`. No default. Required.
  - Client-side guard: if source === target, disable submit + show inline error.
- **[frontend/src/App.tsx:20](../frontend/src/App.tsx#L20)**: replace `"AI-assisted literary translation · EN → TR"` with `"AI-assisted literary translation"`. The per-book pair is shown in the book view, not the global header.
- **[frontend/src/views/BookList.tsx:53](../frontend/src/views/BookList.tsx#L53)**: drop "into Turkish"; generic copy: "let you translate them chunk-by-chunk."
- **[frontend/src/views/BookDetail.tsx](../frontend/src/views/BookDetail.tsx)**:
  - Render `{book.source_language.toUpperCase()} → {book.target_language.toUpperCase()}` next to the title.
  - Line 57 export filename: ``` `${book.title.replace(/\s+/g, "_")}_${book.target_language.toUpperCase()}.txt` ```
  - Line 29 chapter regex: leave the mixed EN/TR keyword list for now. Acceptable short-term — chapter detection is heuristic only. Track as deferred polish.
- **[frontend/src/components/ChunkCard.tsx](../frontend/src/components/ChunkCard.tsx)** lines 103, 112: labels become `` `Source (${book.source_language.toUpperCase()})` `` and `` `Translation (${book.target_language.toUpperCase()})` ``. Pass the `book` prop down from `BookDetail`.
- **[frontend/src/components/GlossaryPanel.tsx](../frontend/src/components/GlossaryPanel.tsx)** lines 26, 51, 63, 105, 107: convert Turkish error/status strings to English. Per CLAUDE.md: "All user-facing strings and docs in English. The translation **output** is Turkish — never translate UI labels."

### 12. CLAUDE.md updates

- Update the project blurb (drop "into Turkish"; describe as configurable multi-lingual literary translation).
- Add `source_language` / `target_language` to the `books` row in the **Key data model** section.
- Note Alembic in **Repository layout** and remove "Alembic migrations" from **What's intentionally out of scope**.
- Document the new endpoints: `POST /api/languages/detect`, `GET /api/languages`.
- Note the prompt registry at `app/services/llm/lang_rules.py` and the convention for adding new languages.

---

## Files touched

| File | Change |
|---|---|
| `requirements.txt` | + `alembic`, `lingua-language-detector`, `regex` |
| `alembic.ini`, `migrations/env.py`, `migrations/versions/0001_initial.py`, `migrations/versions/0002_add_book_languages.py` | new — initial Alembic setup + first feature migration |
| `main.py` | swap `create_all` for `alembic upgrade head`; mount languages router |
| `app/models/book.py` | + `source_language`, `target_language` |
| `app/schemas/book.py` | + language fields on `BookBase` / `BookCreate` / `BookRead` |
| `app/schemas/language.py` | new — `LangOption`, `LanguageDetectionResponse`, `SUPPORTED_TARGETS` |
| `app/services/lang_detect.py` | new — lingua + LLM fallback |
| `app/services/llm/lang_rules.py` | new — `LANG_RULES` registry, TR rules extracted verbatim, FR/DE seeded, others generic |
| `app/services/translator.py` | templates take language placeholders; builders take `book` instead of `style_guide`; comments updated |
| `app/services/chunker.py` | `_SENTENCE_SPLIT` switched to `regex` + `\p{Lu}` |
| `app/api/endpoints/books.py` | upload accepts + validates language fields; PATCH rejects language changes |
| `app/api/endpoints/languages.py` | new — `POST /detect`, `GET /` |
| `frontend/src/types.ts`, `frontend/src/api.ts` | + language fields, detect/list calls |
| `frontend/src/components/UploadForm.tsx` | source dropdown (pre-filled by detection), target dropdown |
| `frontend/src/components/ChunkCard.tsx` | parameterized source/target labels |
| `frontend/src/components/GlossaryPanel.tsx` | Turkish strings → English |
| `frontend/src/App.tsx`, `BookList.tsx`, `BookDetail.tsx` | drop hardcoded EN/TR; show per-book pair; parameterize export filename |
| `CLAUDE.md` | documentation pass |

**Not touched:** [app/services/llm/__init__.py](../app/services/llm/__init__.py), [app/services/llm/base.py](../app/services/llm/base.py), [app/services/llm/ollama_provider.py](../app/services/llm/ollama_provider.py), [app/schemas/translation.py](../app/schemas/translation.py), [app/models/chunk.py](../app/models/chunk.py), [app/models/translation_version.py](../app/models/translation_version.py), [app/services/translator.py:_persist_translation](../app/services/translator.py#L123), [resolve_required_models](../app/services/translator.py#L245). Provider and persistence layers are language-agnostic.

---

## Verification

1. **Migration**: delete `bookflow.db`. Start backend. Confirm Alembic runs both revisions; `sqlite3 bookflow.db ".schema books"` shows `source_language` + `target_language`.
2. **Detection — lib path**: `curl -X POST http://localhost:8200/api/languages/detect -H 'content-type: application/json' -d '{"text":"<long French paragraph>"}'` → `{"code":"fr","confidence":>=0.7,"method":"lib"}`.
3. **Detection — LLM fallback**: send a 50-char ambiguous snippet → confidence < 0.7 → response `method:"llm"` with a sensible code.
4. **Supported list**: `GET /api/languages` returns the 8 locked targets.
5. **Upload flow (UI)**: pick an English `.epub`, source dropdown pre-fills to `en` with helper text. Change target to `fr`. Submit. Book row in DB has `source_language='en'` and `target_language='fr'`. Book detail shows "EN → FR".
6. **TR regression test (critical)**: upload an English book with target=`tr` exactly as before. Translate one chunk in two-stage mode. Compare the system prompt sent to Ollama (log at DEBUG) against the pre-change prompt — TR translationese rules must appear verbatim. Quality of the result must be indistinguishable from current main.
7. **FR target — happy path**: upload an English book with target=`fr`, two-stage. Verify prompt contains "from English into ... French" and the seeded `FR_STAGE1_RULES` block. Output must be idiomatic French.
8. **Generic-rules language (e.g. `es`)**: upload English → Spanish. Prompt contains the generic Stage 1 / Stage 2 blocks. Output should still be acceptable Spanish.
9. **Two-stage book batch**: `POST /api/books/{id}/translate` on an EN→FR book with `TRANSLATION_PIPELINE=two_stage`. Both phases run; versions table has stage-1 and stage-2 rows per chunk.
10. **Unicode chunker**: feed `chunker.chunk_text` a Russian passage with multiple sentences. Verify it splits on `.` before Cyrillic uppercase.
11. **Validation**: try uploading with `source_language=en`, `target_language=en` → 400. Try `target_language=xx` (not in `SUPPORTED_CODES`) → 400.
12. **UI labels**: chunk card on a FR→DE book shows "Source (FR)" / "Translation (DE)". Export filename ends `_DE.txt`. Glossary panel error messages are English.

---

## Out of scope (deferred)

- Per-language chapter-detection regex in the frontend (the existing mixed EN/TR list is fine as heuristic; revisit when adding a 5th+ supported target).
- Glossary language-pair scoping. Book already pins the pair; per-pair glossary is unnecessary churn until users request it.
- Configurable detection confidence threshold (0.7 is a sane default — promote to env var only if real-world misses are common).
- Tuned `stage1_rules` / `stage2_rules` for ES, RU, IT, PT. Generic block covers them; add per-language rules once we have user feedback on each.
- LLM-based source language *override* validation (e.g., warn if user picks `de` for an obviously French file). Pure detection on the suggestion path is enough.
