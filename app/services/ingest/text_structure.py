"""Shared, format-agnostic text-structure helpers used by every parser.

Three concerns live here:

1. **Cleanliness gauges** — ``printable_ratio`` / ``word_ratio`` to detect
   pages or sections that contain only encoded gibberish (some publisher
   blurbs in EPUB-exported PDFs come out as base64-shifted ASCII).
2. **Front-matter detection** — heuristic that flags cover / copyright /
   dedication blocks so they can be dropped before the first real chapter.
3. **Heading detection** — a multi-language, conservative classifier that
   promotes "Chapter 1", "Bölüm 5", "PART ONE", "I.", "1", ALL-CAPS short
   lines, etc. to Markdown ``## …`` headings.  It is the *last-resort* layer
   used by every parser when format-native heading signals are absent
   (PDF outline, EPUB ``<h1>``, DOCX "Heading 1" style).

None of these helpers are PDF-specific — they operate on plain strings.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

# ── tuneable constants ────────────────────────────────────────────────────────
MIN_PRINTABLE_RATIO = 0.60
MIN_WORD_RATIO = 0.40
MAX_HEADING_LEN = 80

# ── regex catalogue ───────────────────────────────────────────────────────────

_WORD_TOKEN = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿĞİıŞşÇçÖöÜü'’ʼ\-]{1,20}$")

# A line ending with sentence-ending punctuation is almost certainly prose,
# not a heading.  (Numeric headings like "1." are checked before this guard.)
_SENTENCE_END = re.compile(r"[.!?…,:;\"”’)]\s*$")

# Multi-language explicit chapter / part / section keywords.
_HEADING_KEYWORDS = (
    r"chapter|chap\.?|chapters|part|book|section|prologue|epilogue|prolog|epilog"
    r"|interlude|preface|foreword|introduction|appendix"
    r"|bölüm|kısım|önsöz|giriş|sonuç|son söz"  # Turkish
    r"|capítulo|capitulo|parte"                   # Spanish/Portuguese
    r"|kapitel|teil|abschnitt"                    # German
    r"|chapitre|partie"                            # French
    r"|глава|часть"                                # Russian
)
_KEYWORD_HEADING = re.compile(
    rf"^\s*(?:{_HEADING_KEYWORDS})\b[\s\d\w:.\-–—']*$",
    re.IGNORECASE,
)

# Bare numeric / Roman heading: "1", "10", "IV", " 3 ", "1.", "I."
_NUMERIC_HEADING = re.compile(r"^\s*(?:\d{1,3}|[IVXivx]{1,6})\.?\s*$")

# Front-matter signals
_APPENDIX_MARKER = re.compile(
    r"^\s*(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December|Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|"
    r"Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)\s+\d{1,2},?\s+\d{4}",
    re.IGNORECASE,
)
# Pages that are clearly non-fiction trailers ("Back Cover", "About the
# Author", "Yazar Hakkında", etc.) — treated like an appendix marker so the
# rest of the document is dropped too.
_TRAILER_HEADING = re.compile(
    r"^\s*(?:ARKA\s+KAPAK|BACK\s+COVER|ABOUT\s+THE\s+AUTHOR"
    r"|YAZAR\s+HAKKINDA|AUTHOR\s+BIO(?:GRAPHY)?|YAZAR\s+B[İI]YOGRAF[İI]S[İI]"
    r"|ACKNOWLEDG(?:E)?MENTS|TE[ŞS]EKK[ÜU]RLER|NOTLAR)\s*$",
    re.IGNORECASE,
)
_DEDICATION_LINE = re.compile(
    r"^\s*(?:TO|FOR|İTHAF|ITHAF)\s+[A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ\s,.\-']+\s*$"
)
_BOILERPLATE_KW = re.compile(
    r"\b(copyright|©|all rights reserved|isbn|library of congress|"
    r"first published|printed in|tüm hakları saklıdır)\b",
    re.IGNORECASE,
)
# Author bio: an UPPERCASE NAME followed by birth year ("X 1966'da doğdu",
# "X was born in 1966"). Very strong signal — author pages on Turkish and
# English publisher templates both fit this shape.
_AUTHOR_BIO = re.compile(
    r"\b[A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ\s']{4,40}\b.{0,40}"
    r"(?:\bdo[ğg]du\b|\bwas\s+born\b|\bborn\s+in\s+\d{4}\b|\b\d{4}\s*['’ʼ]?\s*da\s+do[ğg]du\b)",
    re.IGNORECASE | re.DOTALL,
)

# Bookmark / outline entries that should never be treated as a chapter.
_OUTLINE_JUNK = re.compile(
    r"^(cover|contents|table of contents|copyright|title page|"
    r"front\s*matter|back\s*matter|index|bibliography|"
    r"içindekiler|kapak|telif|kaynakça)$",
    re.IGNORECASE,
)


# ── cleanliness gauges ───────────────────────────────────────────────────────


def printable_ratio(text: str) -> float:
    """Fraction of characters that are printable (non-control, non-garbage)."""
    if not text:
        return 0.0
    printable = sum(
        1
        for ch in text
        if unicodedata.category(ch) not in ("Cc", "Cs", "Co", "Cn")
        and ch not in "\x00\xff"
    )
    return printable / len(text)


def word_ratio(text: str) -> float:
    """Fraction of whitespace-split tokens that look like real words.

    A token is "word-like" if it is 1–20 chars of letters (plus apostrophes
    and hyphens).  Publisher blurb pages encoded with character-shifting
    produce tokens like ``!"#$%&'#%()*&%+#`` that fail this check.
    """
    tokens = text.split()
    if not tokens:
        return 0.0
    word_count = sum(1 for t in tokens if _WORD_TOKEN.match(t))
    return word_count / len(tokens)


# ── front-matter detection ───────────────────────────────────────────────────


def looks_like_front_matter(text: str) -> bool:
    """True if a section looks like cover / publisher / copyright / dedication.

    Works on a single page (PDF), a single EPUB document, or any other
    bounded chunk of text that might be a non-content prelude.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return True

    if word_ratio(text) < MIN_WORD_RATIO:
        return True

    if any(_DEDICATION_LINE.match(ln) for ln in lines):
        return True

    # Author bio page: typically a short text with "AUTHOR_NAME ... was born
    # in YEAR" / "doğdu" pattern. Common at the front of Turkish editions.
    if _AUTHOR_BIO.search(text) and len(text) < 2000:
        return True

    long_lines = [ln for ln in lines if len(ln) > 60]
    if any(_BOILERPLATE_KW.search(ln) for ln in lines) and len(long_lines) < 3:
        return True

    # Decorative cover page: lots of single-punctuation lines.
    single_punct = sum(1 for ln in lines if len(ln) == 1 and not ln.isalnum())
    if lines and single_punct / len(lines) > 0.40:
        return True

    # Title page: very few lines, none of them prose-length.
    if not long_lines and len(lines) <= 10:
        return True

    return False


def is_appendix_marker(text: str) -> bool:
    """True if the first few lines of `text` look like an addendum start.

    Used to drop afterwords / news clippings / "about the author" sections
    that follow the last chapter.  ``## …`` Markdown prefixes are stripped
    before matching so the check works on sections that already had a TOC
    title prepended by an earlier layer.
    """
    first_lines = [
        re.sub(r"^#{1,6}\s+", "", ln.strip())
        for ln in text.splitlines()[:4]
    ]
    if any(_APPENDIX_MARKER.match(ln) for ln in first_lines):
        return True
    if any(_TRAILER_HEADING.match(ln) for ln in first_lines):
        return True
    return False


def is_outline_junk(title: str) -> bool:
    """True if a bookmark / TOC entry is a non-chapter (Cover, Contents…)."""
    return bool(_OUTLINE_JUNK.match(title.strip()))


# ── heading detection (last-resort layer) ────────────────────────────────────


def looks_like_heading(
    line: str, *, prev_blank: bool, next_blank: bool
) -> bool:
    """Conservative classifier: is this line a chapter heading?

    Requires multiple signals to fire so that ordinary prose isn't promoted.
    `prev_blank` / `next_blank` describe whether the adjacent lines are
    empty — most genuine headings sit on their own line in their own paragraph.
    """
    stripped = line.strip()
    if not stripped or len(stripped) > MAX_HEADING_LEN:
        return False

    # Numeric headings ("1", "1.", "IV", "IV.") are checked first so the
    # trailing period doesn't trip the sentence-end guard below.
    if prev_blank and next_blank and _NUMERIC_HEADING.match(stripped):
        return True

    if _SENTENCE_END.search(stripped):
        return False

    # Explicit chapter/part keyword.
    if _KEYWORD_HEADING.match(stripped):
        return True

    # ALL-CAPS short line surrounded by blanks (titled chapters).
    has_letters = any(ch.isalpha() for ch in stripped)
    if (
        prev_blank
        and next_blank
        and has_letters
        and stripped == stripped.upper()
        and len(stripped) >= 4
        and (" " in stripped or len(stripped) >= 8)
    ):
        return True

    return False


def normalise_heading(line: str) -> str:
    """Convert a detected heading line into ``## …`` Markdown form.

    Bare numbers/roman numerals are prefixed with ``Chapter `` for readability,
    so a downstream UI shows "Chapter 1" instead of just "1".
    """
    text = line.strip()
    if _NUMERIC_HEADING.match(text):
        text = f"Chapter {text.rstrip('.').strip()}"
    return f"## {text}"


def detect_headings_in_text(text: str) -> str:
    """Scan `text` line-by-line; promote heading-looking lines to ``## …``.

    This is the fallback path used by every parser when format-native heading
    signals are unavailable (PDF without an outline, plain TXT, EPUB / DOCX
    that don't use proper heading tags / styles).
    """
    if not text:
        return text

    lines = text.splitlines()
    out: list[str] = []
    n = len(lines)
    for i, line in enumerate(lines):
        prev_blank = i == 0 or not lines[i - 1].strip()
        next_blank = i == n - 1 or not lines[i + 1].strip()
        if line.strip() and looks_like_heading(
            line, prev_blank=prev_blank, next_blank=next_blank
        ):
            # Ensure heading is in its own paragraph.
            if out and out[-1].strip():
                out.append("")
            out.append(normalise_heading(line))
            out.append("")
        else:
            out.append(line)
    return "\n".join(out)


# ── shared building blocks ───────────────────────────────────────────────────


def collapse_blank_lines(text: str) -> str:
    """Collapse runs of blank lines into a single blank line; trim ends."""
    if not text:
        return ""
    cleaned: list[str] = []
    prev_blank = False
    for ln in text.splitlines():
        is_blank = not ln.strip()
        if is_blank and prev_blank:
            continue
        cleaned.append(ln)
        prev_blank = is_blank
    return "\n".join(cleaned).strip()


def drop_front_matter(
    sections: Iterable[str], max_lookahead: int = 12
) -> list[str]:
    """Drop leading sections that look like front matter.

    Returns the input list starting from the first section that *isn't*
    front-matter.  Stops looking after ``max_lookahead`` sections — once a
    book gets that deep, the front matter is presumed already over.
    """
    sections_list = list(sections)
    first_content: int | None = None
    for idx, sec in enumerate(sections_list[:max_lookahead]):
        if not sec.strip():
            continue
        if looks_like_front_matter(sec):
            continue
        first_content = idx
        break
    if first_content is None:
        return sections_list
    return sections_list[first_content:]


def drop_appendix(sections: Iterable[str]) -> list[str]:
    """Drop the first section that starts with an addendum marker and all
    subsequent sections."""
    out: list[str] = []
    for sec in sections:
        if is_appendix_marker(sec):
            break
        out.append(sec)
    return out
