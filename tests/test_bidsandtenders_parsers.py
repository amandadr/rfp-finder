"""Tests for Bids & Tenders parsers."""

import pytest

from rfp_finder.connectors.bidsandtenders.parsers import (
    extract_csrf_token,
    extract_search_guid,
    raw_from_search_item,
)


class TestExtractCsrfToken:
    """Tests for extract_csrf_token."""

    def test_extracts_token_from_standard_markup(self) -> None:
        html = """<form>
            <input name="__RequestVerificationToken" type="hidden" value="abc123xyz" />
        </form>"""
        assert extract_csrf_token(html) == "abc123xyz"

    def test_extracts_token_value_before_name(self) -> None:
        html = """<input type="hidden" value="token-value-here" name="__RequestVerificationToken" />"""
        assert extract_csrf_token(html) == "token-value-here"

    def test_raises_when_token_missing(self) -> None:
        html = "<html><body>No token here</body></html>"
        with pytest.raises(RuntimeError, match="Could not find __RequestVerificationToken"):
            extract_csrf_token(html)


class TestExtractSearchGuid:
    """Tests for extract_search_guid."""

    def test_extracts_guid_from_node_id(self) -> None:
        """Primary: NodeId hidden input (used by site's index.js)."""
        html = '<input type="hidden" id="NodeId" value="f10c0dda-f64a-4cc5-a4f0-f0839866ab3b" />'
        assert extract_search_guid(html) == "f10c0dda-f64a-4cc5-a4f0-f0839866ab3b"

    def test_extracts_guid_from_url_fallback(self) -> None:
        html = 'url: "/Module/Tenders/en/Tender/Search/f10c0dda-f64a-4cc5-a4f0-f0839866ab3b"'
        assert extract_search_guid(html) == "f10c0dda-f64a-4cc5-a4f0-f0839866ab3b"

    def test_returns_none_when_no_guid(self) -> None:
        html = "<html><body>No search URL or NodeId</body></html>"
        assert extract_search_guid(html) is None


class TestRawFromSearchItem:
    """Tests for raw_from_search_item."""

    def test_maps_pascal_case_fields(self) -> None:
        item = {
            "Id": "BT-123",
            "Title": "Test RFP",
            "Description": "Test description",
            "Organization": "City of Test",
            "Url": "https://bids.bidsandtenders.ca/opp/123",
            "ReferenceNumber": "BT-123",
        }
        raw = raw_from_search_item(item)
        assert raw["id"] == "BT-123"
        assert raw["title"] == "Test RFP"
        assert raw["description"] == "Test description"
        assert raw["buyer"] == "City of Test"
        assert raw["url"] == "https://bids.bidsandtenders.ca/opp/123"
        assert raw["reference_number"] == "BT-123"

    def test_maps_snake_case_fields(self) -> None:
        item = {
            "id": "123",
            "title": "Snake Case",
            "description": "Desc",
            "organization": "Org",
        }
        raw = raw_from_search_item(item)
        assert raw["id"] == "123"
        assert raw["title"] == "Snake Case"
        assert raw["buyer"] == "Org"

    def test_preserves_raw_item(self) -> None:
        item = {"Id": "x", "CustomField": "value"}
        raw = raw_from_search_item(item)
        assert raw["_raw"] == item
