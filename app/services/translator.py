import json
import logging
from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.book import Book
from app.models.chunk import Chunk, ChunkStatus
from app.models.glossary import GlossaryTerm
from app.models.translation_version import TranslationVersion
from app.schemas.translation import TranslationOutput
from app.services.llm import get_provider
from app.services.llm.lang_rules import (
    language_name,
    stage1_rules_block,
    stage2_rules_block,
)

logger = logging.getLogger(__name__)

# editor_notes markers used to track which two-stage phase a chunk has reached.
# Phase 1 (batch) tags STAGE1_DONE_NOTE; phase 2 reprocesses only those and
# retags TWO_STAGE_DONE_NOTE. No DB schema/enum change needed.
STAGE1_DONE_NOTE = "pipeline: stage1_done"
TWO_STAGE_DONE_NOTE = "pipeline: two_stage (builder+artist)"


# Language pair is interpolated per-book via `build_system_prompt(book, ...)`.
# `{stage1_rules_block}` carries the per-target translationese / style rules
# from lang_rules.py — TR keeps its tuned block, unknown targets fall back to
# a generic block.
SYSTEM_PROMPT_TEMPLATE = """You are an elite literary translator and editor specializing in translating books from {source_name} into fluent, natural, and evocative {target_name}. Your goal is not a literal word-for-word translation, but a "re-authoring" of the text in {target_name} while preserving the original author's voice, subtext, emotional resonance, and pacing.

CRITICAL TRANSLATION GUIDELINES:
{stage1_rules_block}
- Cultural Adaptation: Translate idioms, metaphors, and cultural references into their closest emotional or traditional {target_name} equivalents, not literal calques.
- Character Voice: Dialogue must sound like something a real native {target_name} speaker would actually say, matching the age, status, and mood described in the scene context.
- Strict Glossary Adherence: Prioritize the translations defined in the glossary below. Do not invent alternatives for terms listed there.
- Proper Nouns: Character names, place names, and brand names must be kept exactly as they appear in the source text. Never translate, decline, or phonetically adapt a proper noun unless it is explicitly listed in the glossary.
- Completeness First: Prioritize completeness and semantic accuracy over stylistic polish — preserve every clause, tense, and nuance. A later editing pass may refine the prose.

<style_guide>
{style_guide}
</style_guide>

MANDATORY GLOSSARY — ZERO EXCEPTIONS:
The terms below MUST be translated exactly as specified. Do NOT leave them in the source language, do NOT invent alternatives. Substitute every occurrence before writing any other word.

<glossary>
{glossary_block}
</glossary>

<scene_context>
{scene_context}
</scene_context>

OUTPUT FORMAT:
Translate the ENTIRE source text — every paragraph, every sentence, every line of dialogue. Do not summarize, do not stop early.
Respond strictly with a single JSON object and nothing else. No markdown fences, no commentary. The object must match this schema exactly:
{{
  "translated_text": "Complete {target_name} translation of the full source text, preserving paragraph breaks with \\n\\n.",
  "editor_notes": ["Brief notes on tricky choices or cultural adaptations. Empty array if none."]
}}"""


def _render_glossary(terms: Iterable[GlossaryTerm]) -> str:
    rows = [f"- {t.source_term}: {t.target_term}" for t in terms]
    return "\n".join(rows) if rows else "(no glossary terms provided)"


def build_system_prompt(
    book: Book,
    glossary: Iterable[GlossaryTerm],
    scene_context: str | None,
) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        source_name=language_name(book.source_language),
        target_name=language_name(book.target_language),
        stage1_rules_block=stage1_rules_block(book.target_language),
        style_guide=book.style_guide or "(no style guide provided)",
        glossary_block=_render_glossary(glossary),
        scene_context=scene_context or "(no scene context provided)",
    )


# --- Stage 2 (Artist): literary refinement of the Stage 1 draft -------------

STAGE2_SYSTEM_PROMPT_TEMPLATE = """You are an elite {target_name} literary editor. You receive a {source_name} source passage and a faithful but mechanical {target_name} draft. Your job is to rewrite the {target_name} so it reads as natural, evocative, publication-quality literary prose — while preserving the exact meaning, tense, and structure of the {source_name} source.

EDITING RULES:
{stage2_rules_block}
- Preserve meaning: do NOT add, drop, or reinterpret content. The {source_name} source is ground truth; the {target_name} draft is a starting point you may freely rephrase.
- Character Voice: dialogue must sound like something a real native {target_name} speaker would actually say, matching the tone, register, and mood of the scene.
- Keep paragraph breaks (use \\n\\n between paragraphs).
- Proper Nouns: keep character, place, and brand names exactly as in the source unless the glossary specifies otherwise.

<style_guide>
{style_guide}
</style_guide>

MANDATORY GLOSSARY — ZERO EXCEPTIONS:
The terms below MUST appear translated exactly as specified and MUST survive your edit unchanged. Do NOT revert them to the source language or substitute alternatives.

<glossary>
{glossary_block}
</glossary>

<scene_context>
{scene_context}
</scene_context>

OUTPUT FORMAT:
Refine the ENTIRE draft — every paragraph, every line of dialogue. Do not summarize, do not stop early.
Respond strictly with a single JSON object and nothing else. No markdown fences, no commentary. The object must match this schema exactly:
{{
  "translated_text": "The refined literary {target_name} translation of the full passage, preserving paragraph breaks with \\n\\n.",
  "editor_notes": ["Brief notes on what you changed and why. Empty array if none."]
}}"""


def build_stage2_system_prompt(
    book: Book,
    glossary: Iterable[GlossaryTerm],
    scene_context: str | None,
) -> str:
    return STAGE2_SYSTEM_PROMPT_TEMPLATE.format(
        source_name=language_name(book.source_language),
        target_name=language_name(book.target_language),
        stage2_rules_block=stage2_rules_block(book.target_language),
        style_guide=book.style_guide or "(no style guide provided)",
        glossary_block=_render_glossary(glossary),
        scene_context=scene_context or "(no scene context provided)",
    )


def _persist_translation(
    db: Session,
    chunk: Chunk,
    result: TranslationOutput,
    extra_notes: list[str] | None = None,
    pipeline: str | None = None,
    stage1_model: str | None = None,
    stage2_model: str | None = None,
) -> None:
    """Save a translation result: insert a version row, make it active, commit.

    Shared by both the single-pass and two-stage pipelines. `extra_notes` are
    prepended to the editor notes (e.g. a stage2_failed flag or pipeline marker).

    Each call appends an immutable `TranslationVersion` and points the chunk at
    it (newest becomes active). `chunk.translated_text` mirrors the active version
    so export and existing UI keep working unchanged.
    """
    src_len = len(chunk.source_text)
    out_len = len(result.translated_text)
    ratio = out_len / src_len if src_len else 1.0
    if ratio < 0.5:
        logger.warning(
            "translate_chunk: chunk %s output/input ratio %.2f — "
            "possible truncation (src=%d out=%d)",
            chunk.id, ratio, src_len, out_len,
        )

    notes = list(extra_notes or [])
    notes.extend(result.editor_notes)
    if ratio < 0.5:
        notes.insert(0, f"WARNING: output/input ratio {ratio:.2f} — translation may be truncated")
    notes_json = json.dumps(notes, ensure_ascii=False)

    version = TranslationVersion(
        chunk_id=chunk.id,
        translated_text=result.translated_text,
        editor_notes=notes_json,
        pipeline=pipeline,
        stage1_model=stage1_model,
        stage2_model=stage2_model,
    )
    db.add(version)
    db.flush()  # assign version.id

    # Mirror the new (active) version onto the chunk for export / back-compat.
    chunk.translated_text = result.translated_text
    chunk.editor_notes = notes_json
    chunk.active_version_id = version.id
    chunk.status = ChunkStatus.in_review
    db.commit()
    logger.info(
        "translate_chunk: chunk %s translated (ratio=%.2f, version=%s)",
        chunk.id, ratio, version.id,
    )


async def _run_two_stage(
    db: Session,
    chunk: Chunk,
    book: Book,
    glossary: list[GlossaryTerm],
    provider_name: str | None,
    stage1_model: str | None = None,
    stage2_model: str | None = None,
) -> None:
    """Builder -> Artist chain.

    Stage 1 failures propagate to the caller's except block (chunk -> raw).
    Stage 2 failures are caught here: the Stage 1 draft is saved and flagged so
    the reviewer always gets a usable translation.

    `stage1_model` / `stage2_model` are per-request overrides; each falls back to
    the matching .env default when None.
    """
    # Stage 1 — Builder: faithful source->target. Per-request model overrides the default.
    stage1_system = build_system_prompt(book, glossary, chunk.scene_context)
    stage1_user = f"<source_text>\n{chunk.source_text}\n</source_text>"
    s1_model = stage1_model or settings.OLLAMA_STAGE1_MODEL
    s1_provider = get_provider(provider=provider_name, model=s1_model)
    logger.info("translate_chunk: chunk %s stage 1 (builder) model=%s", chunk.id, s1_model)
    s1: TranslationOutput = await s1_provider.generate_json(
        stage1_system, stage1_user, TranslationOutput
    )

    # Stage 2 — Artist: literary refinement of the Stage 1 draft.
    try:
        stage2_system = build_stage2_system_prompt(book, glossary, chunk.scene_context)
        stage2_user = (
            f"<source_text>\n{chunk.source_text}\n</source_text>\n\n"
            f"<draft_translation>\n{s1.translated_text}\n</draft_translation>"
        )
        s2_model = stage2_model or settings.OLLAMA_STAGE2_MODEL
        s2_provider = get_provider(provider=provider_name, model=s2_model)
        logger.info("translate_chunk: chunk %s stage 2 (artist) model=%s", chunk.id, s2_model)
        s2: TranslationOutput = await s2_provider.generate_json(
            stage2_system, stage2_user, TranslationOutput
        )
        _persist_translation(
            db, chunk, s2,
            extra_notes=[TWO_STAGE_DONE_NOTE],
            pipeline="two_stage", stage1_model=s1_model, stage2_model=s2_model,
        )
    except Exception as exc:
        # Stage 1 succeeded; keep its draft rather than discarding good work.
        logger.exception(
            "translate_chunk: chunk %s stage 2 failed; saving stage 1 draft", chunk.id
        )
        _persist_translation(
            db,
            chunk,
            s1,
            extra_notes=[
                f"stage2_failed: {exc}",
                "pipeline: two_stage (stage 1 draft only)",
            ],
            pipeline="two_stage", stage1_model=s1_model,
        )


def resolve_required_models(
    model: str | None = None,
    stage1_model: str | None = None,
    stage2_model: str | None = None,
) -> dict[str, str | None]:
    """Resolve which model each stage will use, given the request overrides.

    Mirrors the precedence used at translate time so the endpoint can validate
    up-front. A value of None means "no model resolved" — the caller should
    reject the request rather than let a background task fail later.

    Single pass uses one model (`model` -> OLLAMA_MODEL). Two-stage resolves a
    Builder and an Artist; each falls back to its .env default, which may be
    empty (-> None) by design.
    """
    if settings.TRANSLATION_PIPELINE == "two_stage":
        s1 = stage1_model or model or settings.OLLAMA_STAGE1_MODEL or None
        s2 = stage2_model or settings.OLLAMA_STAGE2_MODEL or None
        return {"stage1": s1, "stage2": s2}
    return {"single": model or settings.OLLAMA_MODEL or None}


def _mark_failed(db: Session, chunk: Chunk, note: str) -> None:
    """Record a hard failure on a chunk: status -> raw, single-note, commit.

    Mirrors the failure write in translate_chunk so behavior is consistent.
    """
    db.rollback()
    chunk = db.get(Chunk, chunk.id)
    if chunk is not None:
        chunk.status = ChunkStatus.raw
        chunk.editor_notes = json.dumps([note], ensure_ascii=False)
        db.commit()


def _append_note(db: Session, chunk: Chunk, note: str) -> None:
    """Append a note to a chunk's existing editor_notes, leaving status/text intact.

    Used when Phase 2 fails but the Phase-1 draft is already saved and worth keeping.
    """
    db.rollback()
    chunk = db.get(Chunk, chunk.id)
    if chunk is None:
        return
    try:
        existing = json.loads(chunk.editor_notes) if chunk.editor_notes else []
        if not isinstance(existing, list):
            existing = []
    except (json.JSONDecodeError, TypeError):
        existing = []
    existing.append(note)
    chunk.editor_notes = json.dumps(existing, ensure_ascii=False)
    db.commit()


async def translate_book_batched(
    book_id: int,
    provider_name: str | None = None,
    stage1_model: str | None = None,
    stage2_model: str | None = None,
    chunk_ids: list[int] | None = None,
) -> None:
    """Two-stage translation batched BY STAGE rather than by chunk.

    Phase 1 loads the Builder once and translates every pending chunk; Phase 2
    loads the Artist once and refines every chunk that cleared Phase 1. This
    swaps the Ollama model once instead of twice per chunk — essential when the
    two models cannot share VRAM (e.g. an 8 GB GPU).

    Resilient: a chunk that fails Phase 1 is marked failed and skipped; Phase 2
    only processes chunks tagged STAGE1_DONE_NOTE. Phase-2 failures keep the
    Phase-1 draft and just append a stage2_failed note.

    If ``chunk_ids`` is given, only those chunks (still scoped to ``book_id``)
    are processed — and the approved-only skip is dropped so the user can
    explicitly re-translate even an approved chunk.
    """
    s1_model = stage1_model or settings.OLLAMA_STAGE1_MODEL
    s2_model = stage2_model or settings.OLLAMA_STAGE2_MODEL
    id_filter = set(chunk_ids) if chunk_ids else None

    with SessionLocal() as db:
        book = db.get(Book, book_id)
        if book is None:
            logger.warning("translate_book_batched: book %s not found", book_id)
            return
        glossary = list(db.query(GlossaryTerm).filter_by(book_id=book_id).all())

        all_chunks = (
            db.query(Chunk)
            .filter_by(book_id=book_id)
            .order_by(Chunk.sequence_number.asc())
            .all()
        )
        if id_filter is not None:
            # Explicit selection: honor it as-is (even approved chunks).
            pending = [c for c in all_chunks if c.id in id_filter]
        else:
            pending = [c for c in all_chunks if c.status != ChunkStatus.approved]

        if not pending:
            logger.info("translate_book_batched: book %s has no pending chunks", book_id)
            return

        # ---- PHASE 1: Builder — model loaded once, all chunks translated ----
        s1_provider = get_provider(provider=provider_name, model=s1_model)
        logger.info(
            "translate_book_batched: book %s phase 1 (builder) model=%s chunks=%d",
            book_id, s1_model, len(pending),
        )
        for chunk in pending:
            try:
                system_prompt = build_system_prompt(book, glossary, chunk.scene_context)
                user_prompt = f"<source_text>\n{chunk.source_text}\n</source_text>"
                out = await s1_provider.generate_json(
                    system_prompt, user_prompt, TranslationOutput
                )
                _persist_translation(
                    db, chunk, out,
                    extra_notes=[STAGE1_DONE_NOTE],
                    pipeline="two_stage", stage1_model=s1_model,
                )
            except Exception as exc:
                logger.exception(
                    "translate_book_batched: book %s chunk %s phase 1 failed",
                    book_id, chunk.id,
                )
                _mark_failed(db, chunk, f"stage1_failed: {exc}")

        # ---- PHASE 2: Artist — model loaded once, all stage-1 drafts refined ----
        # Re-query: only chunks that cleared Phase 1 (tagged STAGE1_DONE_NOTE),
        # still scoped to the same selection so a selective run doesn't sweep
        # in unrelated chunks that happened to be tagged from a previous run.
        stage1_done = [
            c
            for c in (
                db.query(Chunk)
                .filter_by(book_id=book_id)
                .order_by(Chunk.sequence_number.asc())
                .all()
            )
            if c.editor_notes
            and STAGE1_DONE_NOTE in c.editor_notes
            and (id_filter is None or c.id in id_filter)
        ]
        if not stage1_done:
            logger.warning("translate_book_batched: book %s no chunks survived phase 1", book_id)
            return

        s2_provider = get_provider(provider=provider_name, model=s2_model)
        logger.info(
            "translate_book_batched: book %s phase 2 (artist) model=%s chunks=%d",
            book_id, s2_model, len(stage1_done),
        )
        for chunk in stage1_done:
            try:
                stage2_system = build_stage2_system_prompt(
                    book, glossary, chunk.scene_context
                )
                stage2_user = (
                    f"<source_text>\n{chunk.source_text}\n</source_text>\n\n"
                    f"<draft_translation>\n{chunk.translated_text}\n</draft_translation>"
                )
                out = await s2_provider.generate_json(
                    stage2_system, stage2_user, TranslationOutput
                )
                _persist_translation(
                    db, chunk, out,
                    extra_notes=[TWO_STAGE_DONE_NOTE],
                    pipeline="two_stage", stage1_model=s1_model, stage2_model=s2_model,
                )
            except Exception as exc:
                # Phase-1 draft is already persisted; keep it, just flag Phase 2.
                logger.exception(
                    "translate_book_batched: book %s chunk %s phase 2 failed; keeping draft",
                    book_id, chunk.id,
                )
                _append_note(db, chunk, f"stage2_failed: {exc}")

        logger.info("translate_book_batched: book %s done", book_id)


async def translate_chunk(
    chunk_id: int,
    provider_name: str | None = None,
    model: str | None = None,
    stage1_model: str | None = None,
    stage2_model: str | None = None,
) -> None:
    """Background task: translate a single chunk and persist the result.

    Opens its own DB session — BackgroundTasks runs outside the request scope.
    All failures are caught and recorded on the chunk; nothing is raised.

    Per-call model overrides (else .env defaults are used):
      - `model`        — single-pass model / legacy Stage 1 override.
      - `stage1_model` — two_stage Builder override (takes precedence over `model`).
      - `stage2_model` — two_stage Artist override.
    """
    with SessionLocal() as db:
        chunk = db.get(Chunk, chunk_id)
        if chunk is None:
            logger.warning("translate_chunk: chunk %s not found", chunk_id)
            return

        book = chunk.book
        glossary = list(db.query(GlossaryTerm).filter_by(book_id=book.id).all())

        try:
            if settings.TRANSLATION_PIPELINE == "two_stage":
                await _run_two_stage(
                    db, chunk, book, glossary, provider_name,
                    stage1_model=stage1_model or model,
                    stage2_model=stage2_model,
                )
            else:
                system_prompt = build_system_prompt(book, glossary, chunk.scene_context)
                user_prompt = f"<source_text>\n{chunk.source_text}\n</source_text>"
                single_model = model or settings.OLLAMA_MODEL
                provider = get_provider(provider=provider_name, model=single_model)
                result: TranslationOutput = await provider.generate_json(
                    system_prompt, user_prompt, TranslationOutput
                )
                _persist_translation(
                    db, chunk, result,
                    pipeline="single", stage1_model=single_model,
                )
        except Exception as exc:
            logger.exception("translate_chunk: failed for chunk %s", chunk_id)
            db.rollback()
            chunk = db.get(Chunk, chunk_id)
            if chunk is not None:
                chunk.status = ChunkStatus.raw
                chunk.editor_notes = json.dumps(
                    [f"translation_failed: {exc}"], ensure_ascii=False
                )
                db.commit()
