from dataclasses import dataclass
from io import BytesIO
import re
import unicodedata

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from backend.app.contracts import ChunkRecord


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str


def _normalize_page_text(text: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", text or "").replace("\x00", "")
    lines = [re.sub(r"[\t ]+", " ", line).strip() for line in normalized.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def extract_pdf_pages(data: bytes, max_bytes: int, max_pages: int) -> list[PageText]:
    if len(data) > max_bytes:
        raise ValueError(f"PDF exceeds the {max_bytes // (1024 * 1024)} MB upload limit.")
    if not data.startswith(b"%PDF-"):
        raise ValueError("The uploaded file is not a valid PDF.")
    try:
        reader = PdfReader(BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise ValueError("Password-protected PDFs are not supported.")
        if len(reader.pages) > max_pages:
            raise ValueError(f"PDF exceeds the {max_pages}-page demo limit.")
        pages = [
            PageText(page_number=index + 1, text=_normalize_page_text(page.extract_text()))
            for index, page in enumerate(reader.pages)
        ]
    except PdfReadError as exc:
        raise ValueError("The uploaded file could not be read as a PDF.") from exc

    if not any(page.text for page in pages):
        raise ValueError(
            "This PDF has no selectable text. Scanned-PDF OCR is not supported yet; send a clear page photo instead."
        )
    return pages


def _chunk_page_text(text: str, chunk_chars: int = 3600, overlap_chars: int = 400) -> list[str]:
    if chunk_chars <= overlap_chars:
        raise ValueError("chunk_chars must exceed overlap_chars")
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_chars, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + chunk_chars * 3 // 4, end)
            if boundary > start:
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(start + 1, end - overlap_chars)
    return chunks


def make_chunks(
    pages: list[PageText], material_id: str, learner_id: str, chunk_chars: int = 3600, overlap_chars: int = 400
) -> list[ChunkRecord]:
    chunks: list[ChunkRecord] = []
    for page in pages:
        for index, text in enumerate(_chunk_page_text(page.text, chunk_chars, overlap_chars)):
            chunks.append(
                ChunkRecord(
                    chunk_id=f"{material_id}:p{page.page_number}:c{index + 1}",
                    material_id=material_id,
                    learner_id=learner_id,
                    source_type="pdf",
                    page_number=page.page_number,
                    text=text,
                )
            )
    return chunks
