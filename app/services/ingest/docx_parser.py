"""DOCX ingestion with chapter-aware extraction.

Layered chapter detection:

  1. Paragraph styles — "Heading 1".."Heading 6", "Title" (or their localized
     equivalents like "Başlık 1") map directly to Markdown ``## …`` headings.
     This is the most reliable signal in any well-structured Word document.
  2. Multi-language text-pattern matching (shared classifier) on paragraphs
     for documents that author headings as plain bold text rather than using
     proper styles.

Front matter (cover / copyright / dedication blocks) is dropped using the
shared heuristic.
"""

from __future__ import annotations

import io
import re
from pathlib import PurePath
from typing import TYPE_CHECKING

from docx import Document

from app.services.ingest.text_structure import (
    detect_headings_in_text,
    drop_appendix,
    drop_front_matter,
    is_outline_junk,
)

if TYPE_CHECKING:
    from app.services.ingest.dispatcher import ParsedBook

# Style names that indicate a heading paragraph.
# Covers English defaults and common localizations (Turkish, German, French,
# Spanish).  Match is case-insensitive on the style's display name.
_HEADING_STYLE = re.compile(
    r"^(?:"
    r"heading\s*[1-6]?"
    r"|title|subtitle"
    r"|başlık\s*[1-6]?"
    r"|überschrift\s*[1-6]?"
    r"|titre\s*[1-6]?"
    r"|título\s*[1-6]?|titulo\s*[1-6]?"
    r")$",
    re.IGNORECASE,
)


def parse_docx(data: bytes, filename: str) -> "ParsedBook":
    from app.services.ingest.dispatcher import ParsedBook

    doc = Document(io.BytesIO(data))
    props = doc.core_properties

    title = (props.title or "").strip() or PurePath(filename).stem
    author = (props.author or "").strip() or None

    sections: list[str] = []
    current: list[str] = []
    saw_native_heading = False

    def flush() -> None:
        if current:
            sections.append("\n\n".join(current).strip())
            current.clear()

    for para in doc.paragraphs:
        text = (para.text or "").strip()
        if not text:
            continue

        style_name = ""
        try:
            style_name = (para.style.name or "").strip()
        except Exception:
            style_name = ""

        if _HEADING_STYLE.match(style_name) and not is_outline_junk(text):
            # New chapter / section.  Close current accumulator and start
            # fresh with the heading line as the first paragraph.
            saw_native_heading = True
            flush()
            current.append(f"## {text}")
            continue

        current.append(text)

    flush()

    # Drop front matter and trailing addenda using shared heuristics.
    sections = drop_front_matter(sections)
    sections = drop_appendix(sections)

    # Fallback: no styled headings → text-pattern detection on the joined body.
    if not saw_native_heading:
        sections = [detect_headings_in_text(s) for s in sections]

    full_text = "\n\n".join(s.strip() for s in sections if s.strip())
    return ParsedBook(title=title, author=author, text=full_text)
