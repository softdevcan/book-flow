import json
import logging
from collections.abc import Iterable

from app.db.session import SessionLocal
from app.models.chunk import Chunk, ChunkStatus
from app.models.glossary import GlossaryTerm
from app.schemas.translation import TranslationOutput
from app.services.llm import get_provider

logger = logging.getLogger(__name__)


SYSTEM_PROMPT_TEMPLATE = """You are an elite literary translator and editor specializing in translating books from English into fluent, natural, and evocative Turkish. Your goal is not a literal word-for-word translation, but a "re-authoring" of the text in Turkish while preserving the original author's voice, subtext, emotional resonance, and pacing.

CRITICAL TRANSLATION GUIDELINES:
- Avoid "AI Turkish" (Translationese): Do not follow English sentence structures or passive voice traps (e.g., avoid overusing "tarafından", "bunun hakkında", "sahip olmak"). Break long English sentences into punchy, natural Turkish clauses where it improves readability.
- Cultural Adaptation: Translate idioms, metaphors, and cultural references into their closest emotional or traditional Turkish equivalents, not literal calques.
- Character Voice: Dialogue must sound like something a real native Turkish speaker would actually say, matching the age, status, and mood described in the scene context.
- Strict Glossary Adherence: Prioritize the translations defined in the glossary below. Do not invent alternatives for terms listed there.
- Proper Nouns: Character names, place names, and brand names must be kept exactly as they appear in the source text. Never translate, decline, or phonetically adapt a proper noun unless it is explicitly listed in the glossary.

<style_guide>
{style_guide}
</style_guide>

MANDATORY GLOSSARY — ZERO EXCEPTIONS:
The terms below MUST be translated exactly as specified. Do NOT leave them in English, do NOT invent alternatives. Substitute every occurrence before writing any other word.

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
  "translated_text": "Complete Turkish translation of the full source text, preserving paragraph breaks with \\n\\n.",
  "editor_notes": ["Brief notes on tricky choices or cultural adaptations. Empty array if none."]
}}"""


def _render_glossary(terms: Iterable[GlossaryTerm]) -> str:
    rows = [f"- {t.source_term}: {t.target_term}" for t in terms]
    return "\n".join(rows) if rows else "(no glossary terms provided)"


def build_system_prompt(
    style_guide: str | None,
    glossary: Iterable[GlossaryTerm],
    scene_context: str | None,
) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        style_guide=style_guide or "(no style guide provided)",
        glossary_block=_render_glossary(glossary),
        scene_context=scene_context or "(no scene context provided)",
    )


async def translate_chunk(
    chunk_id: int,
    provider_name: str | None = None,
    model: str | None = None,
) -> None:
    """Background task: translate a single chunk and persist the result.

    Opens its own DB session — BackgroundTasks runs outside the request scope.
    All failures are caught and recorded on the chunk; nothing is raised.

    `provider_name` and `model` are optional per-call overrides; otherwise
    the .env defaults are used.
    """
    with SessionLocal() as db:
        chunk = db.get(Chunk, chunk_id)
        if chunk is None:
            logger.warning("translate_chunk: chunk %s not found", chunk_id)
            return

        book = chunk.book
        glossary = list(db.query(GlossaryTerm).filter_by(book_id=book.id).all())

        system_prompt = build_system_prompt(book.style_guide, glossary, chunk.scene_context)
        user_prompt = f"<source_text>\n{chunk.source_text}\n</source_text>"

        try:
            provider = get_provider(provider=provider_name, model=model)
            result: TranslationOutput = await provider.generate_json(
                system_prompt, user_prompt, TranslationOutput
            )

            src_len = len(chunk.source_text)
            out_len = len(result.translated_text)
            ratio = out_len / src_len if src_len else 1.0
            if ratio < 0.5:
                logger.warning(
                    "translate_chunk: chunk %s output/input ratio %.2f — "
                    "possible truncation (src=%d out=%d)",
                    chunk_id, ratio, src_len, out_len,
                )

            chunk.translated_text = result.translated_text
            notes = list(result.editor_notes)
            if ratio < 0.5:
                notes.insert(0, f"WARNING: output/input ratio {ratio:.2f} — translation may be truncated")
            chunk.editor_notes = json.dumps(notes, ensure_ascii=False)
            chunk.status = ChunkStatus.in_review
            db.commit()
            logger.info("translate_chunk: chunk %s translated (ratio=%.2f)", chunk_id, ratio)
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
