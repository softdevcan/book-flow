"""EPUB ingestion with chapter-aware extraction.

Layered chapter detection:

  1. HTML heading tags (``<h1>``..``<h6>``) inside each document — the most
     reliable signal in well-formed EPUBs.  Tag text is promoted to a
     Markdown ``## …`` heading regardless of its original level (we don't
     preserve depth — the chunker only needs boundaries).
  2. EPUB navigation document / NCX TOC titles — used when documents have
     no heading tags but the EPUB ships a navigation tree.
  3. Multi-language text-pattern matching (shared classifier) on the
     extracted plain text — last-resort fallback.

Front matter (cover / copyright / dedication sections) is dropped via the
same heuristic shared with the PDF parser.
"""

from __future__ import annotations

import io
import re
from pathlib import PurePath
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup
from ebooklib import ITEM_DOCUMENT, ITEM_NAVIGATION, epub

from app.services.ingest.text_structure import (
    collapse_blank_lines,
    detect_headings_in_text,
    drop_appendix,
    drop_front_matter,
    is_outline_junk,
)

if TYPE_CHECKING:
    from app.services.ingest.dispatcher import ParsedBook

_HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
# Block-level tags that should produce paragraph breaks after .get_text().
_BLOCK_TAGS = ("p", "div", "section", "article", "li", "blockquote", "br")


def parse_epub(data: bytes, filename: str) -> "ParsedBook":
    from app.services.ingest.dispatcher import ParsedBook

    book = epub.read_epub(io.BytesIO(data))

    title = _first_meta(book, "title") or PurePath(filename).stem
    author = _first_meta(book, "creator")

    # Pre-fetch list of nav documents so we never treat them as content.
    nav_ids = {it.id for it in book.get_items_of_type(ITEM_NAVIGATION)}

    # ── Layer 1: extract each document, promoting <h1>..<h6> tags ────────────
    sections: list[str] = []
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        if item.id in nav_ids or _is_nav_document(item):
            continue
        section_text = _extract_document(item)
        if section_text:
            sections.append(section_text)

    # ── Layer 2: NCX / nav TOC titles — overlay onto sections WITHOUT a
    # heading so we benefit from TOC even if only some documents have <h1>.
    toc_titles = _toc_titles_by_href(book)
    if toc_titles:
        sections = _overlay_toc_titles(book, nav_ids, toc_titles, sections)

    # Drop front matter and trailing addenda.
    sections = drop_front_matter(sections)
    sections = drop_appendix(sections)

    # ── Layer 3: text-pattern detection — ALWAYS run, even when layers 1/2
    # produced some headings. The classifier is idempotent on existing
    # `## …` lines, and per-document fallback catches books where only the
    # first few chapters used <h1> tags (a common Sigil/Calibre quirk).
    sections = [detect_headings_in_text(s) for s in sections]

    full_text = "\n\n".join(s.strip() for s in sections if s.strip())
    return ParsedBook(title=title, author=author, text=full_text)


# ── helpers ───────────────────────────────────────────────────────────────────


def _first_meta(book: epub.EpubBook, name: str) -> str | None:
    items = book.get_metadata("DC", name)
    if not items:
        return None
    value = items[0][0]
    return value.strip() if isinstance(value, str) and value.strip() else None


def _is_nav_document(item) -> bool:
    """True if the document declares itself as an EPUB3 nav doc.

    ebooklib sometimes returns nav documents under ITEM_DOCUMENT in addition
    to ITEM_NAVIGATION, so we double-check by looking for ``<nav epub:type=…>``.
    """
    try:
        content = item.get_content()
    except Exception:
        return False
    # Cheap byte-level check before parsing.
    if b"epub:type=\"toc\"" in content or b"epub:type='toc'" in content:
        return True
    if b"<nav" not in content:
        return False
    try:
        soup = BeautifulSoup(content, "lxml")
    except Exception:
        return False
    return bool(soup.find("nav"))


def _html_to_text(content: bytes) -> str:
    """Convert HTML bytes to plain text preserving paragraph breaks."""
    soup = BeautifulSoup(content, "lxml")
    for tag in soup(["script", "style", "head", "meta", "link", "nav"]):
        tag.decompose()
    # Insert paragraph markers after block-level tags so the resulting plain
    # text has blank lines between paragraphs (essential for the pattern
    # classifier which keys off prev_blank / next_blank).
    for tag in soup.find_all(_BLOCK_TAGS):
        tag.append("\n\n")
    text = soup.get_text(separator="\n").strip()
    return collapse_blank_lines(text)


def _extract_document(item) -> str:
    """Extract plain text from a single EPUB document.

    Native ``<h1>``..``<h6>`` tags are rewritten to Markdown ``## …`` lines
    BEFORE plain-text extraction so the heading text survives ``get_text``.
    Block-level tags get a trailing blank line so paragraph boundaries are
    preserved for the downstream pattern classifier.
    """
    content = item.get_content()
    soup = BeautifulSoup(content, "lxml")

    for tag in soup(["script", "style", "head", "meta", "link", "nav"]):
        tag.decompose()

    for tag in soup.find_all(_HEADING_TAGS):
        heading_text = tag.get_text(separator=" ", strip=True)
        if not heading_text or is_outline_junk(heading_text):
            tag.decompose()
            continue
        tag.replace_with(f"\n\n## {heading_text}\n\n")

    for tag in soup.find_all(_BLOCK_TAGS):
        tag.append("\n\n")

    text = soup.get_text(separator="\n").strip()
    return collapse_blank_lines(text)


def _normalise_href(href: str) -> str:
    """Strip fragment and leading 'OEBPS/'-style prefixes for matching."""
    href = href.split("#", 1)[0].strip()
    # The TOC may reference 'Text/chap_0.xhtml' while items report just
    # 'chap_0.xhtml' — match on the basename as the most-portable key.
    return href.rsplit("/", 1)[-1].lower()


def _toc_titles_by_href(book: epub.EpubBook) -> dict[str, str]:
    """Return ``{normalised_href: title}`` from the EPUB nav doc / NCX, if any.

    Both EPUB3 nav documents and EPUB2 NCX flatten to the same shape here.
    Keys are basename-only (lower-case) for robust matching.
    """
    out: dict[str, str] = {}

    def walk(items) -> None:
        for entry in items:
            if isinstance(entry, tuple):
                _section, children = entry
                walk(children)
                continue
            href = getattr(entry, "href", None) or ""
            title = (getattr(entry, "title", None) or "").strip()
            if not href or not title or is_outline_junk(title):
                continue
            out.setdefault(_normalise_href(href), title)

    try:
        walk(book.toc or [])
    except Exception:
        pass

    if out:
        return out

    # Fallback: parse the EPUB3 nav document directly.
    for nav_item in book.get_items_of_type(ITEM_NAVIGATION):
        try:
            soup = BeautifulSoup(nav_item.get_content(), "lxml")
        except Exception:
            continue
        for a in soup.find_all("a", href=True):
            title = a.get_text(strip=True)
            href = a["href"]
            if not title or not href or is_outline_junk(title):
                continue
            out.setdefault(_normalise_href(href), title)

    return out


def _overlay_toc_titles(
    book: epub.EpubBook,
    nav_ids: set,
    toc_titles: dict[str, str],
    sections: list[str],
) -> list[str]:
    """Prepend TOC titles to sections that don't already start with a heading.

    Iterates in the same order as ``_extract_document`` so positional pairing
    is correct.  Sections that already begin with ``## …`` (from a native
    ``<h1>`` tag) are left untouched — TOC and inline headings shouldn't
    duplicate each other.

    If the section's first non-blank line is itself the chapter label (e.g.
    a centred ``<p>3</p>`` that the publisher used instead of ``<h1>``), the
    duplicate is dropped so the TOC heading and the body label don't both
    survive into the final text.
    """
    iterator = (
        item
        for item in book.get_items_of_type(ITEM_DOCUMENT)
        if item.id not in nav_ids and not _is_nav_document(item)
    )
    out: list[str] = []
    for item, section in zip(iterator, sections):
        if section.lstrip().startswith("## "):
            out.append(section)
            continue
        href_key = _normalise_href(
            getattr(item, "file_name", "") or getattr(item, "href", "")
        )
        title = toc_titles.get(href_key)
        if not title:
            out.append(section)
            continue
        body = _strip_leading_duplicate_label(section, title)
        out.append(f"## {title}\n\n{body}")
    return out


def _strip_leading_duplicate_label(section: str, title: str) -> str:
    """Drop a leading paragraph that just repeats the chapter label.

    Many EPUBs render the chapter number both in the TOC and as a centred
    standalone paragraph at the top of the chapter body (``<p>3</p>``).  If
    we keep both, the chunker sees two consecutive headings for the same
    chapter.  Compare on a normalised form (whitespace, punctuation, case
    stripped) so "3", "3 ", " 3." all match a TOC title of "3".
    """

    def norm(s: str) -> str:
        return re.sub(r"[\s.]+", "", s).casefold()

    target = norm(title)
    if not target:
        return section

    lines = section.splitlines()
    # Find the first non-blank line.
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines):
        return section
    if norm(lines[i]) != target:
        return section

    # Drop that line + the immediate blank lines that follow it.
    j = i + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    return "\n".join(lines[:i] + lines[j:]).strip()
