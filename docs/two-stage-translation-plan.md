# Plan: 2-Stage LLM Chaining Translation Pipeline

## Context

BookFlow currently does a **single-pass** translation: `translate_chunk` builds one system
prompt, calls `provider.generate_json` once, and saves the result. We want higher literary
quality without loading a single huge model into limited local VRAM. The solution is a
**2-stage chain** where two smaller models run sequentially:

- **Stage 1 — The Builder** (`qwen2.5:14b`): faithful, structurally-complete EN→TR translation.
- **Stage 2 — The Artist** (`gemma2:9b`): takes the English original **and** the Stage 1 draft,
  and rewrites the Turkish to be literary and natural, stripping translationese.

Because two inference passes + Ollama model swapping take longer than one pass, the timeout
must grow. Because Stage 2 can fail independently, we must not throw away a good Stage 1 draft.

### Decisions locked with the user
1. **Stage 2 failure → save the Stage 1 draft and flag it** (status `in_review`, note prepended). A usable draft always survives.
2. **Models configured via new `.env` settings.** Per-request `model` override (if sent) applies to **Stage 1** only.
3. **Toggleable** via a new `TRANSLATION_PIPELINE` setting (`single` | `two_stage`). The existing single-pass path stays intact for A/B comparison and as a fallback.

---

## Current state (verified)

- `app/services/translator.py` — `translate_chunk(chunk_id, provider_name, model)` opens its own
  `SessionLocal`, loads chunk + book + glossary, builds the prompt via `build_system_prompt`, calls
  `get_provider(provider=..., model=...).generate_json(system, user, TranslationOutput)`, runs an
  output/input length ratio check, and persists or records the error. **No raise** — failures are
  written to the chunk.
- `app/services/llm/__init__.py` — `get_provider(provider, model, temperature)` already supports
  **per-call model overrides**. This is the key enabler: two stages = two `get_provider(model=...)`
  calls. **No change needed here.**
- `app/services/llm/base.py` — `LLMProvider.generate_json(system, user, schema) -> T`. **No change needed.**
- `app/services/llm/ollama_provider.py` — `OllamaProvider` reads timeout from
  `settings.OLLAMA_TIMEOUT_SECONDS` at `AsyncClient` init, has one JSON-repair retry in
  `generate_json`. **No change needed** — it already does everything a single stage needs.
- `app/schemas/translation.py` — `TranslationOutput { translated_text: str (min_len 1), editor_notes: list[str] }`. Reused unchanged for **both** stages.
- `app/core/config.py` — `Settings` with `OLLAMA_MODEL`, `OLLAMA_TEMPERATURE`, `OLLAMA_TIMEOUT_SECONDS`, etc.
- `app/api/endpoints/chunks.py` — `TranslateRequest { provider, model }`, calls `translate_chunk` via `BackgroundTasks`. **No signature change needed** — `model` keeps flowing in as the Stage 1 override.

**Conclusion:** The provider layer (`base.py`, `ollama_provider.py`, `__init__.py`) needs **no changes**.
The chaining lives entirely in `translator.py` + config. This keeps the single background-task flow intact.

---

## Implementation plan

### 1. `app/core/config.py` — new settings
Add to `Settings` (keep defaults that work even if user hasn't pulled both models):
```python
TRANSLATION_PIPELINE: Literal["single", "two_stage"] = "single"
OLLAMA_STAGE1_MODEL: str = "qwen2.5:14b"   # Builder
OLLAMA_STAGE2_MODEL: str = "gemma2:9b"     # Artist
OLLAMA_TIMEOUT_SECONDS: float = 400.0      # raise from 180.0 — two passes + model swap
```
Rationale: timeout is set once at `AsyncClient` init, and each stage builds its own provider, so 400s
applies per stage (each pass gets the full budget — correct, since either pass can be the slow one).

### 2. `.env.example` — document the new knobs
Add, with comments:
```
# Translation pipeline: "single" (one pass) or "two_stage" (Builder -> Artist)
TRANSLATION_PIPELINE=single
# Stage 1 (Builder): faithful EN->TR. Stage 2 (Artist): literary refinement.
OLLAMA_STAGE1_MODEL=qwen2.5:14b
OLLAMA_STAGE2_MODEL=gemma2:9b
# Raised for two sequential passes + Ollama model swap latency.
OLLAMA_TIMEOUT_SECONDS=400
```

### 3. `app/services/translator.py` — the core refactor
Keep `translate_chunk` as the **single** background task and entry point. Internally branch on
`settings.TRANSLATION_PIPELINE`.

**a. Add two new prompt templates + builders** (alongside the existing `SYSTEM_PROMPT_TEMPLATE`,
which is reused as the Stage 1 / single-pass prompt):

- `STAGE2_SYSTEM_PROMPT_TEMPLATE` — the Artist. Same `{style_guide}` / `{glossary_block}` /
  `{scene_context}` placeholders so glossary + style guide are still enforced (see Prompt Engineering
  section below). Add `build_stage2_system_prompt(...)` mirroring `build_system_prompt`.
- Stage 2 **user prompt** carries both texts:
  ```
  <english_source>\n{source_text}\n</english_source>\n\n<turkish_draft>\n{stage1_translated}\n</turkish_draft>
  ```

**b. Extract the existing persist logic** (ratio check + save) into a small helper
`_persist_translation(db, chunk, result, extra_notes: list[str]) -> None` so both pipelines reuse it.
`extra_notes` lets us prepend the `stage2_failed: ...` flag.

**c. Refactor the body of `translate_chunk`:**
```
load chunk/book/glossary (unchanged)
if settings.TRANSLATION_PIPELINE == "single":
    <-- existing single-pass logic, now via _persist_translation -->
else:
    _run_two_stage(...)
all wrapped so a hard failure still records translation_failed (unchanged catch behavior)
```

**d. New `_run_two_stage(db, chunk, book, glossary)`** (still `async`, still inside the one task):
```
# Stage 1 — Builder
s1_provider = get_provider(model=(per_request_model or settings.OLLAMA_STAGE1_MODEL))
s1 = await s1_provider.generate_json(stage1_system, stage1_user, TranslationOutput)
# (if Stage 1 raises -> propagate to outer except -> chunk back to raw, translation_failed)

# Stage 2 — Artist
try:
    s2_provider = get_provider(model=settings.OLLAMA_STAGE2_MODEL)
    s2 = await s2_provider.generate_json(stage2_system, stage2_user(s1.translated_text), TranslationOutput)
    _persist_translation(db, chunk, s2, extra_notes=["pipeline: two_stage (builder+artist)"])
except Exception as exc:
    logger.exception("stage 2 failed for chunk %s; saving stage 1 draft", chunk.id)
    _persist_translation(db, chunk, s1, extra_notes=[f"stage2_failed: {exc}", "pipeline: two_stage (stage1 draft only)"])
```

### 4. Error handling summary (per locked decision #1)
- **Stage 1 fails** → falls through to the **existing** outer `except` in `translate_chunk`:
  `db.rollback()`, status → `raw`, note `translation_failed: <reason>`. No partial output exists, so this is correct.
- **Stage 2 fails** → caught **inside** `_run_two_stage`; we persist the **Stage 1 draft** with
  status `in_review` and a prepended `stage2_failed: <reason>` note. Reviewer always gets a usable draft.
- Each stage keeps the provider's built-in one-shot JSON-repair retry (in `ollama_provider.generate_json`) — no extra retry budget added.

---

## Prompt engineering (drafts to refine during implementation)

### Stage 1 — Builder (reuse existing `SYSTEM_PROMPT_TEMPLATE`, lightly retargeted)
The existing template is already strong on glossary/style/JSON. For two-stage mode we want Stage 1 to
prioritize **fidelity over polish** (the Artist handles polish). Add one line to its guidelines:
> "Prioritize completeness and semantic accuracy over stylistic polish — preserve every clause, tense,
> and nuance. A later editing pass will refine the prose."
Glossary, proper-noun, style-guide, and strict-JSON (`TranslationOutput`) rules stay identical.

### Stage 2 — Artist (new `STAGE2_SYSTEM_PROMPT_TEMPLATE`)
```
You are an elite Turkish literary editor. You receive an English source passage and a faithful but
mechanical Turkish draft. Your job is to rewrite the Turkish so it reads as natural, evocative,
publication-quality literary Turkish — while preserving the exact meaning, tense, and structure of
the English source.

EDITING RULES:
- Eliminate "translationese": remove overused passive voice, "tarafından", "sahip olmak",
  "bunun hakkında", and any calqued English sentence structures. Recast as idiomatic Turkish.
- Preserve meaning: do NOT add, drop, or reinterpret content. The English source is ground truth;
  the Turkish draft is a starting point you may freely rephrase.
- Dialogue must sound like a real native Turkish speaker, matching the scene's tone and register.
- Keep paragraph breaks (\n\n). Keep proper nouns exactly as in the source unless the glossary says otherwise.

<style_guide>{style_guide}</style_guide>

MANDATORY GLOSSARY — ZERO EXCEPTIONS (must survive the edit unchanged):
<glossary>{glossary_block}</glossary>

<scene_context>{scene_context}</scene_context>

OUTPUT FORMAT: Respond strictly with a single JSON object, no markdown, matching:
{ "translated_text": "the refined literary Turkish, full text, \\n\\n paragraph breaks",
  "editor_notes": ["notes on what you changed and why. Empty array if none."] }
```
Both stages output the **same** `TranslationOutput` schema, so parsing/validation is unchanged.

---

## Files touched
| File | Change |
|---|---|
| `app/core/config.py` | + `TRANSLATION_PIPELINE`, `OLLAMA_STAGE1_MODEL`, `OLLAMA_STAGE2_MODEL`; bump `OLLAMA_TIMEOUT_SECONDS` 180→400 |
| `.env.example` | document the four settings above |
| `app/services/translator.py` | add Stage 2 prompt + builder; extract `_persist_translation`; add `_run_two_stage`; branch in `translate_chunk` |
| `CLAUDE.md` | document the pipeline + new settings (per repo rule: update CLAUDE.md in the same PR when adding scope) |

**Not touched:** `llm/base.py`, `llm/ollama_provider.py`, `llm/__init__.py`, `schemas/translation.py`,
`api/endpoints/chunks.py`, frontend — the existing provider factory and schema already support everything.

---

## Verification

1. **Default unchanged (single):** with `TRANSLATION_PIPELINE=single`, translate a chunk via
   `POST /api/chunks/{id}/translate` and confirm behavior is identical to today.
2. **Two-stage happy path:** set `TRANSLATION_PIPELINE=two_stage`, `ollama pull qwen2.5:14b gemma2:9b`,
   translate a chunk. Confirm: status `in_review`, `translated_text` populated, an `editor_notes`
   entry `pipeline: two_stage (builder+artist)`. Check uvicorn logs show two provider calls (two models).
3. **Stage 2 failure path:** temporarily set `OLLAMA_STAGE2_MODEL` to a non-pulled model name and
   translate. Confirm the chunk is still `in_review` with the **Stage 1** draft and an
   `editor_notes[0]` of `stage2_failed: ...` — i.e. the draft survived.
4. **Timeout sanity:** confirm a 14b chunk completes within 400s on the target hardware; watch logs for the ratio-check warning.
5. **Glossary survives Stage 2:** include a glossary term, translate two-stage, and confirm the
   target term appears in the final `translated_text` (Artist must not undo it).
