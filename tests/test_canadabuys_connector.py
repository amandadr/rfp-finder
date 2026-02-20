"""Unit tests for CanadaBuys connector."""

from datetime import datetime
from unittest.mock import patch

import pytest

from rfp_finder.connectors.canadabuys import CanadaBuysConnector
from rfp_finder.models.raw import RawOpportunity


@pytest.fixture
def connector() -> CanadaBuysConnector:
    """Shared connector instance."""
    return CanadaBuysConnector()


class TestCanadaBuysConnectorNormalize:
    """Tests for normalize method."""

    def test_normalizes_sample_row(
        self,
        connector: CanadaBuysConnector,
        raw_opportunity_from_csv: RawOpportunity,
    ) -> None:
        """Normalize produces valid NormalizedOpportunity from sample CSV row."""
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

    def test_untitled_fallback(self, connector: CanadaBuysConnector) -> None:
        """Empty title becomes 'Untitled'."""
        raw = RawOpportunity(data={
            "referenceNumber-numeroReference": "cb-123",
            "title-titre-eng": "",
        })
        opp = connector.normalize(raw)
        assert opp.title == "Untitled"

    def test_uses_solicitation_when_ref_empty(self, connector: CanadaBuysConnector) -> None:
        """Uses solicitation number when reference is empty."""
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
    def test_search_returns_raw_list(
        self,
        mock_fetch,
        connector: CanadaBuysConnector,
        sample_canadabuys_csv_content: str,
    ) -> None:
        """Search fetches CSV and parses rows."""
        mock_fetch.return_value = sample_canadabuys_csv_content
        raw_list = connector.search()
        assert len(raw_list) == 1
        assert raw_list[0].data.get("referenceNumber-numeroReference") == "cb-233-49083652"
