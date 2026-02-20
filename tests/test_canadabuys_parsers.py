"""Unit tests for CanadaBuys parsers."""

from datetime import datetime

import pytest

from rfp_finder.connectors.canadabuys.parsers import (
    content_hash,
    extract_attachments,
    parse_date,
    parse_trade_agreements,
)
from rfp_finder.models.raw import RawOpportunity


class TestParseDate:
    """Tests for parse_date."""

    def test_iso_datetime(self) -> None:
        """Parses ISO datetime format."""
        assert parse_date("2026-03-09T14:00:00") == datetime(2026, 3, 9, 14, 0, 0)

    def test_date_only(self) -> None:
        """Parses date-only format."""
        assert parse_date("2026-02-20") == datetime(2026, 2, 20, 0, 0, 0)

    def test_empty_string(self) -> None:
        """Returns None for empty string."""
        assert parse_date("") is None
        assert parse_date("   ") is None

    def test_none(self) -> None:
        """Returns None for None."""
        assert parse_date(None) is None


class TestExtractAttachments:
    """Tests for extract_attachments."""

    def test_extracts_urls(self) -> None:
        """Extracts http(s) URLs from attachment field."""
        text = "See https://example.com/doc1.pdf and https://example.com/spec.pdf"
        refs = extract_attachments(text)
        assert len(refs) == 2
        urls = [r.url for r in refs]
        assert "https://example.com/doc1.pdf" in urls
        assert "https://example.com/spec.pdf" in urls

    def test_pdf_mime_type(self) -> None:
        """Sets application/pdf for .pdf URLs."""
        refs = extract_attachments("https://x.com/file.pdf")
        assert refs[0].mime_type == "application/pdf"

    def test_empty_field(self) -> None:
        """Returns empty list for empty/None field."""
        assert extract_attachments(None) == []
        assert extract_attachments("") == []


class TestParseTradeAgreements:
    """Tests for parse_trade_agreements."""

    def test_asterisk_separated(self) -> None:
        """Parses asterisk-separated agreements."""
        result = parse_trade_agreements("*CFTA\n*CCFTA\n*CPTPP")
        assert result is not None
        assert "CFTA" in result
        assert "CCFTA" in result
        assert "CPTPP" in result

    def test_empty_returns_none(self) -> None:
        """Returns None for empty input."""
        assert parse_trade_agreements(None) is None
        assert parse_trade_agreements("") is None


class TestContentHash:
    """Tests for content_hash."""

    def test_deterministic(self) -> None:
        """Same input produces same hash."""
        raw = RawOpportunity(data={"title-titre-eng": "Foo", "tenderDescription-descriptionAppelOffres-eng": "Bar"})
        h1 = content_hash(raw)
        h2 = content_hash(raw)
        assert h1 == h2
        assert len(h1) == 64
        assert all(c in "0123456789abcdef" for c in h1)

    def test_different_input_different_hash(self) -> None:
        """Different input produces different hash."""
        raw1 = RawOpportunity(data={"title-titre-eng": "Foo"})
        raw2 = RawOpportunity(data={"title-titre-eng": "Bar"})
        assert content_hash(raw1) != content_hash(raw2)
