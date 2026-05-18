import io
from pathlib import PurePath
from typing import TYPE_CHECKING

from pypdf import PdfReader

if TYPE_CHECKING:
    from app.services.ingest.dispatcher import ParsedBook


def parse_pdf(data: bytes, filename: str) -> "ParsedBook":
    from app.services.ingest.dispatcher import ParsedBook

    reader = PdfReader(io.BytesIO(data))
    meta = reader.metadata or {}

    title = (meta.get("/Title") or "").strip() or PurePath(filename).stem
    author = (meta.get("/Author") or "").strip() or None

    pages: list[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        text = text.strip()
        if text:
            pages.append(text)

    return ParsedBook(title=title, author=author, text="\n\n".join(pages))
