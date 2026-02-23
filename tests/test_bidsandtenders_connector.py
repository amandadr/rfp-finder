"""Tests for Bids & Tenders connector."""

from unittest.mock import patch

import pytest

from rfp_finder.connectors.bidsandtenders import BidsTendersConnector
from rfp_finder.models.raw import RawOpportunity


@pytest.fixture
def connector() -> BidsTendersConnector:
    """Shared connector instance."""
    return BidsTendersConnector()


class TestBidsTendersConnectorNormalize:
    """Tests for normalize method."""

    def test_normalizes_sample_raw(self, connector: BidsTendersConnector) -> None:
        """Normalize produces valid NormalizedOpportunity from sample raw."""
        raw = RawOpportunity(
            data={
                "id": "BT-123",
                "title": "Test RFP",
                "description": "Test description",
                "url": "https://bids.bidsandtenders.ca/opp/123",
                "buyer": "City of Test",
            }
        )
        opp = connector.normalize(raw)
        assert opp.source == "bidsandtenders"
        assert opp.source_id == "BT-123"
        assert opp.title == "Test RFP"
        assert opp.summary == "Test description"
        assert opp.url == "https://bids.bidsandtenders.ca/opp/123"
        assert opp.buyer == "City of Test"

    def test_untitled_fallback(self, connector: BidsTendersConnector) -> None:
        """Empty title becomes 'Untitled'."""
        raw = RawOpportunity(data={"id": "x", "title": ""})
        opp = connector.normalize(raw)
        assert opp.title == "Untitled"


class TestBidsTendersConnectorSearch:
    """Tests for search with mocked bootstrap."""

    @patch.object(BidsTendersConnector, "_bootstrap")
    @patch.object(BidsTendersConnector, "_post_search")
    def test_search_returns_raw_list(
        self,
        mock_post: object,
        mock_bootstrap: object,
        connector: BidsTendersConnector,
    ) -> None:
        """Search fetches via bootstrap + POST and returns raw list."""
        mock_bootstrap.return_value = ("fake-token", "f10c0dda-f64a-4cc5-a4f0-f0839866ab3b")
        mock_post.return_value = {
            "success": True,
            "total": 1,
            "data": [
                {
                    "Id": "BT-123",
                    "Title": "Test RFP",
                    "Description": "Test desc",
                    "Organization": "City of Test",
                    "Url": "https://bids.bidsandtenders.ca/opp/123",
                }
            ],
        }
        raw_list = connector.search()
        assert len(raw_list) == 1
        assert raw_list[0].data["id"] == "BT-123"
        assert raw_list[0].data["title"] == "Test RFP"
        mock_bootstrap.assert_called_once()
        mock_post.assert_called_once()

    @patch.object(BidsTendersConnector, "_bootstrap")
    @patch.object(BidsTendersConnector, "_post_search")
    def test_search_returns_empty_when_no_data(
        self,
        mock_post: object,
        mock_bootstrap: object,
        connector: BidsTendersConnector,
    ) -> None:
        """Search returns empty when API returns no data."""
        mock_bootstrap.return_value = ("token", "guid")
        mock_post.return_value = {"success": True, "total": 0, "data": []}
        raw_list = connector.search()
        assert raw_list == []

    @patch.object(BidsTendersConnector, "_bootstrap")
    @patch.object(BidsTendersConnector, "_post_search")
    def test_search_filters_by_query(
        self,
        mock_post: object,
        mock_bootstrap: object,
        connector: BidsTendersConnector,
    ) -> None:
        """Search filters results by query."""
        mock_bootstrap.return_value = ("token", "guid")
        mock_post.return_value = {
            "success": True,
            "total": 2,
            "data": [
                {"Id": "1", "Title": "Construction RFP", "Description": "Build"},
                {"Id": "2", "Title": "IT Services", "Description": "Software"},
            ],
        }
        raw_list = connector.search(query="Construction")
        assert len(raw_list) == 1
        assert raw_list[0].data["title"] == "Construction RFP"


class TestBidsTendersConnectorFetchDetails:
    """Tests for fetch_details."""

    @patch.object(BidsTendersConnector, "search")
    def test_fetch_details_returns_matching_raw(
        self,
        mock_search: object,
        connector: BidsTendersConnector,
    ) -> None:
        """fetch_details returns raw when ID matches."""
        raw = RawOpportunity(data={"id": "BT-123", "title": "Test"})
        mock_search.return_value = [raw]
        result = connector.fetch_details("BT-123")
        assert result.data["id"] == "BT-123"

    @patch.object(BidsTendersConnector, "search")
    def test_fetch_details_raises_when_not_found(
        self,
        mock_search: object,
        connector: BidsTendersConnector,
    ) -> None:
        """fetch_details raises ValueError when ID not found."""
        mock_search.return_value = []
        with pytest.raises(ValueError, match="Opportunity not found"):
            connector.fetch_details("nonexistent")


class TestBidsTendersConnectorFetchAll:
    """Tests for fetch_all."""

    @patch.object(BidsTendersConnector, "search")
    def test_fetch_all_normalizes_results(
        self,
        mock_search: object,
        connector: BidsTendersConnector,
    ) -> None:
        """fetch_all returns normalized list."""
        mock_search.return_value = [
            RawOpportunity(data={"id": "1", "title": "RFP 1"}),
        ]
        opps = connector.fetch_all()
        assert len(opps) == 1
        assert opps[0].source == "bidsandtenders"
        assert opps[0].source_id == "1"
