"""Tests for Phase 5 attachment handling."""

import tempfile
from pathlib import Path

import pytest

from rfp_finder.attachments.extractor import extract_text_from_pdf
from rfp_finder.attachments.fetcher import _url_to_filename
from rfp_finder.store.attachment_cache import AttachmentCacheStore


class TestFetcher:
    def test_url_to_filename(self) -> None:
        assert _url_to_filename("https://example.com/doc.pdf").endswith(".pdf")
        assert _url_to_filename("https://example.com/page").endswith(".bin")
        assert len(_url_to_filename("https://a.com/1.pdf")) == 20  # 16 hex + .pdf


class TestExtractor:
    def test_extract_empty_pdf(self) -> None:
        """Create minimal PDF and extract (pypdf can create empty PDFs)."""
        from pypdf import PdfWriter

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = Path(f.name)
        try:
            writer = PdfWriter()
            writer.add_blank_page(100, 100)
            writer.write(path)
            text, pages, err = extract_text_from_pdf(path)
            assert err is None
            assert pages == 1
        finally:
            path.unlink()


class TestAttachmentCacheStore:
    def test_upsert_and_get(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db = Path(f.name)
        try:
            store = AttachmentCacheStore(db)
            store.upsert(
                "https://example.com/doc.pdf",
                "/cache/abc.pdf",
                extraction_status="success",
                extracted_text="Hello world",
                text_length=11,
                page_count=1,
            )
            cached = store.get_cached("https://example.com/doc.pdf")
            assert cached is not None
            assert cached.extraction_status == "success"
            assert cached.extracted_text == "Hello world"
            assert cached.page_count == 1
        finally:
            db.unlink()
