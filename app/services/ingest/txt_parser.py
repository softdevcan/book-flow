from pathlib import PurePath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.ingest.dispatcher import ParsedBook


def parse_txt(data: bytes, filename: str) -> "ParsedBook":
    from app.services.ingest.dispatcher import ParsedBook

    text = data.decode("utf-8", errors="replace").strip()
    return ParsedBook(title=PurePath(filename).stem, author=None, text=text)
