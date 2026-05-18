import io
from pathlib import PurePath
from typing import TYPE_CHECKING

from docx import Document

if TYPE_CHECKING:
    from app.services.ingest.dispatcher import ParsedBook


def parse_docx(data: bytes, filename: str) -> "ParsedBook":
    from app.services.ingest.dispatcher import ParsedBook

    doc = Document(io.BytesIO(data))
    props = doc.core_properties

    title = (props.title or "").strip() or PurePath(filename).stem
    author = (props.author or "").strip() or None

    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
    return ParsedBook(title=title, author=author, text="\n\n".join(paragraphs))
