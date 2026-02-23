"""PDF text extraction for attachment enrichment."""

from pathlib import Path
from typing import Optional


def extract_text_from_pdf(path: Path) -> tuple[str, int, Optional[str]]:
    """
    Extract text from PDF. Returns (text, page_count, error_message).
    On success, error_message is None.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        return ("", 0, "pypdf not installed")

    try:
        reader = PdfReader(path)
        page_count = len(reader.pages)
        chunks: list[str] = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                chunks.append(text)
        return ("\n\n".join(chunks), page_count, None)
    except Exception as e:
        return ("", 0, str(e))


def extract_text_from_file(path: Path, mime_type: Optional[str] = None) -> tuple[str, int, Optional[str]]:
    """
    Extract text from file. Supports PDF. Returns (text, page_count, error_message).
    Tries PDF when extension is .pdf, mime_type indicates PDF, or file has PDF magic bytes.
    """
    suffix = path.suffix.lower()
    is_pdf = (
        suffix == ".pdf"
        or (mime_type and "pdf" in (mime_type or ""))
        or _is_pdf_file(path)
    )
    if is_pdf:
        return extract_text_from_pdf(path)
    return ("", 0, "Unsupported format (only PDF supported)")


def _is_pdf_file(path: Path) -> bool:
    """Check if file has PDF magic bytes (%PDF)."""
    try:
        return path.read_bytes()[:5] == b"%PDF-"
    except (OSError, IndexError):
        return False
