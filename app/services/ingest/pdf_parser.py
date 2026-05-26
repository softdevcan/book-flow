"""PDF ingestion with chapter-aware extraction.

Layered chapter detection (most-reliable-first):

  1. PDF outline / bookmarks (publisher-set; usually accurate).
  2. Multi-language text-pattern matching (shared classifier).

Pages are also filtered to drop blanks, scrambled publisher blurbs, front
matter (cover / copyright / dedication) and trailing addenda.

All format-agnostic helpers live in ``text_structure`` so EPUB / DOCX / TXT
share the same logic.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import PurePath
from typing import TYPE_CHECKING

from pypdf import PdfReader

from app.services.ingest.text_structure import (
    MIN_PRINTABLE_RATIO,
    MIN_WORD_RATIO,
    collapse_blank_lines,
    detect_headings_in_text,
    is_appendix_marker,
    is_outline_junk,
    looks_like_front_matter,
    printable_ratio,
    word_ratio,
)

if TYPE_CHECKING:
    from app.services.ingest.dispatcher import ParsedBook

# ── tuneable constants (PDF-specific) ─────────────────────────────────────────
MIN_PAGE_CHARS = 80
MAX_FRONT_MATTER_PAGES = 12

# PDF-specific cleanup: leading / trailing page-number folio lines.
_FOLIO_LINE = re.compile(r"^\s*\d{1,4}\s*$")


# ── per-page extraction ──────────────────────────────────────────────────────


@dataclass
class _Page:
    index: int  # 0-based PDF page index
    raw: str  # original extracted text
    cleaned: str  # after _clean_page
    skip: bool  # True ⇒ drop entirely


def _clean_page(raw: str) -> str:
    """Strip pypdf artefacts: page-number folio line + redundant blanks."""
    lines = raw.splitlines()
    if not lines:
        return ""
    if lines and _FOLIO_LINE.match(lines[0]):
        lines = lines[1:]
    if lines and _FOLIO_LINE.match(lines[-1]):
        lines = lines[:-1]
    return collapse_blank_lines("\n".join(lines))


def _extract_pages(reader: PdfReader) -> list[_Page]:
    pages: list[_Page] = []
    for idx, page in enumerate(reader.pages):
        try:
            raw = (page.extract_text() or "").strip()
        except Exception:
            raw = ""

        skip = (
            not raw
            or len(raw) < MIN_PAGE_CHARS
            or printable_ratio(raw) < MIN_PRINTABLE_RATIO
            or word_ratio(raw) < MIN_WORD_RATIO
            or is_appendix_marker(raw)
        )

        cleaned = "" if skip else _clean_page(raw)
        pages.append(_Page(index=idx, raw=raw, cleaned=cleaned, skip=skip))

    # Drop leading front-matter pages (test raw text — heuristics expect it).
    first_content = None
    for p in pages[:MAX_FRONT_MATTER_PAGES]:
        if p.skip:
            continue
        if looks_like_front_matter(p.raw):
            p.skip = True
            continue
        first_content = p.index
        break
    if first_content is not None:
        for p in pages[:first_content]:
            p.skip = True

    # Cascade-skip everything after the first appendix marker.
    found_appendix = False
    for p in pages:
        if found_appendix:
            p.skip = True
            continue
        if p.raw and is_appendix_marker(p.raw):
            found_appendix = True

    return pages


# ── Layer 1: PDF outline / bookmarks ─────────────────────────────────────────


def _chapters_from_outline(reader: PdfReader) -> dict[int, str]:
    """Return ``{page_index: chapter_title}`` from the PDF outline, if any."""
    result: dict[int, str] = {}

    def walk(items) -> None:
        for item in items:
            if isinstance(item, list):
                walk(item)
                continue
            title = getattr(item, "title", None)
            if not title:
                continue
            try:
                page_idx = reader.get_destination_page_number(item)
            except Exception:
                continue
            if page_idx is None or page_idx < 0:
                continue
            result.setdefault(page_idx, str(title).strip())

    try:
        outline = reader.outline  # type: ignore[attr-defined]
    except Exception:
        return {}
    if not outline:
        return {}

    try:
        walk(outline)
    except Exception:
        return {}

    return {p: t for p, t in result.items() if not is_outline_junk(t)}


# ── public API ────────────────────────────────────────────────────────────────


def parse_pdf(data: bytes, filename: str) -> "ParsedBook":
    from app.services.ingest.dispatcher import ParsedBook

    reader = PdfReader(io.BytesIO(data))
    meta = reader.metadata or {}

    title = (str(meta.get("/Title") or "")).strip() or PurePath(filename).stem
    author = (str(meta.get("/Author") or "")).strip() or None

    # Guard against opaque IndirectObject string representations.
    if title and not title[0].isalpha() and not title[0].isdigit():
        title = PurePath(filename).stem

    pages = _extract_pages(reader)
    outline_chapters = _chapters_from_outline(reader)

    sections: list[str] = []
    if outline_chapters:
        # Layer 1: PDF outline drives chapter boundaries.
        for p in pages:
            if p.skip or not p.cleaned:
                continue
            if p.index in outline_chapters:
                heading = outline_chapters[p.index].strip()
                sections.append(f"## {heading}\n\n{p.cleaned}")
            else:
                sections.append(p.cleaned)
    else:
        # Layer 2: text-pattern matching on cleaned page text.
        for p in pages:
            if p.skip or not p.cleaned:
                continue
            sections.append(detect_headings_in_text(p.cleaned))

    full_text = "\n\n".join(sections).strip()
    return ParsedBook(title=title, author=author, text=full_text)
