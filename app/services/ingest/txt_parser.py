"""Plain-text ingestion with chapter-aware extraction.

TXT files have no structural metadata, so chapter detection relies entirely
on the shared text-pattern classifier.  Two extra cleanups are applied
before classification:

  1. Project Gutenberg boilerplate (``*** START / END OF THE PROJECT
     GUTENBERG EBOOK …***``) is stripped along with everything outside it.
     A title and author can usually be extracted from the prelude.
  2. The standard front-matter / appendix heuristics from
     ``text_structure`` are applied to drop common preludes (copyright,
     dedications) and trailing addenda.
"""

from __future__ import annotations

import re
from pathlib import PurePath
from typing import TYPE_CHECKING

from app.services.ingest.text_structure import (
    collapse_blank_lines,
    detect_headings_in_text,
    drop_appendix,
    drop_front_matter,
)

if TYPE_CHECKING:
    from app.services.ingest.dispatcher import ParsedBook

_GUTENBERG_START = re.compile(
    r"\*\*\*\s*START OF (?:THE |THIS )?PROJECT GUTENBERG (?:EBOOK|E-BOOK).*?\*\*\*",
    re.IGNORECASE | re.DOTALL,
)
_GUTENBERG_END = re.compile(
    r"\*\*\*\s*END OF (?:THE |THIS )?PROJECT GUTENBERG (?:EBOOK|E-BOOK).*?\*\*\*",
    re.IGNORECASE | re.DOTALL,
)
_GUTENBERG_TITLE = re.compile(r"^\s*Title:\s*(.+?)\s*$", re.MULTILINE)
_GUTENBERG_AUTHOR = re.compile(r"^\s*Author:\s*(.+?)\s*$", re.MULTILINE)


def parse_txt(data: bytes, filename: str) -> "ParsedBook":
    from app.services.ingest.dispatcher import ParsedBook

    raw = data.decode("utf-8", errors="replace")

    title, author, body = _strip_gutenberg(raw)
    title = title or PurePath(filename).stem

    body = collapse_blank_lines(body)

    # Split on blank-line paragraphs so the shared front-matter / appendix
    # filters can work on coherent blocks (rather than a single giant string).
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", body) if p.strip()]
    paragraphs = drop_front_matter(paragraphs)
    paragraphs = drop_appendix(paragraphs)

    cleaned = "\n\n".join(paragraphs)

    # Pattern-based heading detection runs on the whole cleaned body.
    text = detect_headings_in_text(cleaned)

    return ParsedBook(title=title, author=author, text=text)


def _strip_gutenberg(raw: str) -> tuple[str | None, str | None, str]:
    """Detect Project Gutenberg envelope; return (title, author, body)."""
    title: str | None = None
    author: str | None = None
    body = raw

    # Extract title / author from the Gutenberg prelude if present.
    title_match = _GUTENBERG_TITLE.search(raw)
    if title_match:
        title = title_match.group(1).strip()
    author_match = _GUTENBERG_AUTHOR.search(raw)
    if author_match:
        author = author_match.group(1).strip()

    start_match = _GUTENBERG_START.search(raw)
    end_match = _GUTENBERG_END.search(raw)
    if start_match:
        body = raw[start_match.end():]
        if end_match and end_match.start() > start_match.end():
            body = raw[start_match.end():end_match.start()]
    elif end_match:
        body = raw[:end_match.start()]

    return title, author, body.strip()
