"""Unit tests for CanadaBuys connector."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from rfp_finder.connectors.canadabuys import CanadaBuysConnector
from rfp_finder.models.raw import RawOpportunity


class TestCanadaBuysConnectorParseDate:
    """Tests for _parse_date helper."""

    def test_iso_datetime(self) -> None:
        """Parses ISO datetime format."""
        connector = CanadaBuysConnector()
        result = connector._parse_date("2026-03-09T14:00:00")
        assert result == datetime(2026, 3, 9, 14, 0, 0)

    def test_date_only(self) -> None:
        """Parses date-only format."""
        connector = CanadaBuysConnector()
        result = connector._parse_date("2026-02-20")
        assert result == datetime(2026, 2, 20, 0, 0, 0)

    def test_empty_string(self) -> None:
        """Returns None for empty string."""
        connector = CanadaBuysConnector()
        assert connector._parse_date("") is None
        assert connector._parse_date("   ") is None

    def test_none(self) -> None:
        """Returns None for None."""
        connector = CanadaBuysConnector()
        assert connector._parse_date(None) is None


class TestCanadaBuysConnectorExtractAttachments:
    """Tests for _extract_attachments helper."""

    def test_extracts_urls(self) -> None:
        """Extracts http(s) URLs from attachment field."""
        connector = CanadaBuysConnector()
        text = "See https://example.com/doc1.pdf and https://example.com/spec.pdf"
        refs = connector._extract_attachments(text, None)
        assert len(refs) == 2
        urls = [r.url for r in refs]
        assert "https://example.com/doc1.pdf" in urls
        assert "https://example.com/spec.pdf" in urls

    def test_pdf_mime_type(self) -> None:
        """Sets application/pdf for .pdf URLs."""
        connector = CanadaBuysConnector()
        refs = connector._extract_attachments("https://x.com/file.pdf", None)
        assert refs[0].mime_type == "application/pdf"

    def test_empty_field(self) -> None:
        """Returns empty list for empty/None field."""
        connector = CanadaBuysConnector()
        assert connector._extract_attachments(None, None) == []
        assert connector._extract_attachments("", None) == []


class TestCanadaBuysConnectorParseTradeAgreements:
    """Tests for _parse_trade_agreements helper."""

    def test_asterisk_separated(self) -> None:
        """Parses asterisk-separated agreements."""
        connector = CanadaBuysConnector()
        text = "*CFTA\n*CCFTA\n*CPTPP"
        result = connector._parse_trade_agreements(text)
        assert result is not None
        assert "CFTA" in result
        assert "CCFTA" in result
        assert "CPTPP" in result

    def test_empty_returns_none(self) -> None:
        """Returns None for empty input."""
        connector = CanadaBuysConnector()
        assert connector._parse_trade_agreements(None) is None
        assert connector._parse_trade_agreements("") is None


class TestCanadaBuysConnectorContentHash:
    """Tests for _content_hash helper."""

    def test_deterministic(self) -> None:
        """Same input produces same hash."""
        connector = CanadaBuysConnector()
        raw = RawOpportunity(data={"title-titre-eng": "Foo", "tenderDescription-descriptionAppelOffres-eng": "Bar"})
        h1 = connector._content_hash(raw)
        h2 = connector._content_hash(raw)
        assert h1 == h2
        assert len(h1) == 64
        assert all(c in "0123456789abcdef" for c in h1)

    def test_different_input_different_hash(self) -> None:
        """Different input produces different hash."""
        connector = CanadaBuysConnector()
        raw1 = RawOpportunity(data={"title-titre-eng": "Foo"})
        raw2 = RawOpportunity(data={"title-titre-eng": "Bar"})
        assert connector._content_hash(raw1) != connector._content_hash(raw2)


class TestCanadaBuysConnectorNormalize:
    """Tests for normalize method."""

    def test_normalizes_sample_row(
        self,
        raw_opportunity_from_csv: RawOpportunity,
    ) -> None:
        """Normalize produces valid NormalizedOpportunity from sample CSV row."""
        connector = CanadaBuysConnector()
        opp = connector.normalize(raw_opportunity_from_csv)

        assert opp.id == "canadabuys:cb-233-49083652"
        assert opp.source == "canadabuys"
        assert opp.source_id == "cb-233-49083652"
        assert opp.title == "TSPS Ongoing strategic advisory support"
        assert "Strategic advisory" in (opp.summary or "")
        assert opp.buyer == "Financial Consumer Agency of Canada (FCAC)"
        assert opp.region == "National"
        assert opp.status == "open"
        assert opp.published_at == datetime(2026, 2, 20, 0, 0, 0)
        assert opp.closing_at == datetime(2026, 3, 9, 14, 0, 0)
        assert "SRV" in opp.categories
        assert "80101500" in opp.commodity_codes
        assert opp.content_hash is not None
        assert len(opp.attachments) >= 2  # doc1.pdf and spec.pdf from fixture

    def test_untitled_fallback(self) -> None:
        """Empty title becomes 'Untitled'."""
        connector = CanadaBuysConnector()
        raw = RawOpportunity(data={
            "referenceNumber-numeroReference": "cb-123",
            "title-titre-eng": "",
        })
        opp = connector.normalize(raw)
        assert opp.title == "Untitled"

    def test_uses_solicitation_when_ref_empty(self) -> None:
        """Uses solicitation number when reference is empty."""
        connector = CanadaBuysConnector()
        raw = RawOpportunity(data={
            "referenceNumber-numeroReference": "",
            "solicitationNumber-numeroSollicitation": "S12345",
            "title-titre-eng": "Test",
        })
        opp = connector.normalize(raw)
        assert opp.source_id == "S12345"
        assert opp.id == "canadabuys:S12345"


class TestCanadaBuysConnectorSearch:
    """Tests for search with mocked HTTP."""

    @patch("rfp_finder.connectors.canadabuys.connector.CanadaBuysConnector._fetch_csv")
    def test_search_returns_normalized(
        self,
        mock_fetch: MagicMock,
        sample_canadabuys_csv_content: str,
    ) -> None:
        """Search fetches CSV and parses rows."""
        mock_fetch.return_value = sample_canadabuys_csv_content
        connector = CanadaBuysConnector()
        raw_list = connector.search()
        assert len(raw_list) == 1
        assert raw_list[0].data.get("referenceNumber-numeroReference") == "cb-233-49083652"
