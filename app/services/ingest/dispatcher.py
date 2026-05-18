from dataclasses import dataclass
from pathlib import PurePath

from app.services.ingest.docx_parser import parse_docx
from app.services.ingest.epub_parser import parse_epub
from app.services.ingest.pdf_parser import parse_pdf
from app.services.ingest.txt_parser import parse_txt


class UnsupportedFormatError(ValueError):
    pass


@dataclass
class ParsedBook:
    title: str | None
    author: str | None
    text: str


_PARSERS = {
    ".epub": parse_epub,
    ".pdf": parse_pdf,
    ".docx": parse_docx,
    ".txt": parse_txt,
    ".md": parse_txt,
}


def parse_upload(filename: str, data: bytes) -> ParsedBook:
    ext = PurePath(filename).suffix.lower()
    parser = _PARSERS.get(ext)
    if parser is None:
        raise UnsupportedFormatError(
            f"Unsupported file type: {ext or '(no extension)'}. "
            f"Allowed: {', '.join(_PARSERS)}"
        )
    return parser(data, filename)
