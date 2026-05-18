import io
from pathlib import PurePath
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup
from ebooklib import ITEM_DOCUMENT, epub

if TYPE_CHECKING:
    from app.services.ingest.dispatcher import ParsedBook


def parse_epub(data: bytes, filename: str) -> "ParsedBook":
    from app.services.ingest.dispatcher import ParsedBook

    book = epub.read_epub(io.BytesIO(data))

    title = _first_meta(book, "title") or PurePath(filename).stem
    author = _first_meta(book, "creator")

    parts: list[str] = []
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "lxml")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(separator="\n").strip()
        if text:
            parts.append(text)

    full_text = "\n\n".join(parts)
    return ParsedBook(title=title, author=author, text=full_text)


def _first_meta(book: epub.EpubBook, name: str) -> str | None:
    items = book.get_metadata("DC", name)
    if not items:
        return None
    value = items[0][0]
    return value.strip() if isinstance(value, str) and value.strip() else None
