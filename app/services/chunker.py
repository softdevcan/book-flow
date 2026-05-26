"""Paragraph-aware text chunker for literary translation.

Strategy:
1. Split source on blank lines into paragraphs.
2. Paragraphs that look like chapter/section headings are flagged as hard
   boundaries — they always start a new chunk and are never merged into the
   preceding content.
3. Greedily merge consecutive non-heading paragraphs into a chunk while the
   total length stays below `max_chars`. This preserves narrative flow.
4. A paragraph longer than `max_chars` is itself split on sentence boundaries
   (., !, ?, …) followed by any Unicode uppercase letter — covers Latin (incl.
   Turkish, accented), Cyrillic, Greek, etc. Then re-greedily packed.
5. Very short tail chunks are folded into the previous one when they fall
   below `min_chars`, to avoid translating one-line fragments.
"""

from __future__ import annotations

import re

import regex

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")
# `regex` package — needed for the Unicode `\p{Lu}` (any uppercase letter) class.
_SENTENCE_SPLIT = regex.compile(r"(?<=[.!?…])\s+(?=[\p{Lu}\"'(])")

# Lines that force a chunk boundary.
# Two flavours are recognised:
#   1. Any Markdown ATX heading line ("# …", "## …", "### …").  The PDF
#      parser produces these for chapter/part markers detected via the PDF
#      outline or its own multi-language heading classifier — so the chunker
#      doesn't need to second-guess the heading text.
#   2. Plain-text headings still present in EPUB / TXT / DOCX inputs that
#      use known multilingual keywords ("Chapter 3", "Bölüm 5", "Capítulo
#      II", …) without Markdown prefixes.
_HEADING = re.compile(
    r"^(?:"
    r"#{1,6}\s+\S.*"
    r"|(?:chapter|chap\.?|part|book|section|prologue|epilogue|prolog|epilog"
    r"|bölüm|kısım|önsöz|giriş|sonuç"
    r"|capítulo|capitulo|parte"
    r"|kapitel|teil|abschnitt"
    r"|chapitre|partie"
    r"|глава|часть)"
    r"\b[\s\d\w:.\-–—']*"
    r")$",
    re.IGNORECASE,
)

DEFAULT_MAX_CHARS = 1500
DEFAULT_MIN_CHARS = 200


def _is_heading(paragraph: str) -> bool:
    line = paragraph.strip()
    # Must be a single line (no embedded newlines after strip)
    if "\n" in line:
        return False
    # Short enough to be a heading
    if len(line) > 80:
        return False
    return bool(_HEADING.match(line))


def chunk_text(
    text: str,
    max_chars: int = DEFAULT_MAX_CHARS,
    min_chars: int = DEFAULT_MIN_CHARS,
) -> list[str]:
    text = text.strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT.split(text) if p.strip()]

    units: list[str] = []
    for p in paragraphs:
        if len(p) <= max_chars:
            units.append(p)
        else:
            units.extend(_split_long_paragraph(p, max_chars))

    chunks: list[str] = []
    buffer: list[str] = []
    buffer_len = 0
    for unit in units:
        is_hdg = _is_heading(unit)
        added = len(unit) + (2 if buffer else 0)
        # A new heading always flushes the current buffer first.
        # Also flush on max_chars overflow (non-heading case).
        if buffer and (is_hdg or buffer_len + added > max_chars):
            chunks.append("\n\n".join(buffer))
            buffer = []
            buffer_len = 0
        buffer.append(unit)
        buffer_len += len(unit) + (2 if len(buffer) > 1 else 0)
        # Headings are NOT emitted immediately — they stay in buffer so the
        # following paragraphs can be merged into the same chunk.

    if buffer:
        chunks.append("\n\n".join(buffer))

    # Fold short tail into previous — but never fold a heading chunk, because
    # headings must stay as boundaries regardless of their character count.
    if len(chunks) >= 2 and len(chunks[-1]) < min_chars and not _is_heading(chunks[-1]):
        tail = chunks.pop()
        chunks[-1] = chunks[-1] + "\n\n" + tail

    return chunks


def _split_long_paragraph(paragraph: str, max_chars: int) -> list[str]:
    sentences = _SENTENCE_SPLIT.split(paragraph)
    if len(sentences) <= 1:
        return _hard_split(paragraph, max_chars)

    out: list[str] = []
    buffer: list[str] = []
    buffer_len = 0
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if len(s) > max_chars:
            if buffer:
                out.append(" ".join(buffer))
                buffer, buffer_len = [], 0
            out.extend(_hard_split(s, max_chars))
            continue
        added = len(s) + (1 if buffer else 0)
        if buffer and buffer_len + added > max_chars:
            out.append(" ".join(buffer))
            buffer = [s]
            buffer_len = len(s)
        else:
            buffer.append(s)
            buffer_len += added
    if buffer:
        out.append(" ".join(buffer))
    return out


def _hard_split(text: str, max_chars: int) -> list[str]:
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]
