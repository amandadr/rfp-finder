"""Unit tests for BaseConnector interface."""

from abc import abstractmethod
from unittest.mock import patch

import pytest

from rfp_finder.connectors.base import BaseConnector
from rfp_finder.models.opportunity import NormalizedOpportunity
from rfp_finder.models.raw import RawOpportunity


class ConcreteConnector(BaseConnector):
    """Concrete implementation for testing base behavior."""

    source_id = "test"

    def search(self, query=None, filters=None):
        return [
            RawOpportunity(data={"id": "1", "title": "A"}),
            RawOpportunity(data={"id": "2", "title": "B"}),
        ]

    def fetch_details(self, raw_id: str) -> RawOpportunity:
        return RawOpportunity(data={"id": raw_id, "title": "Detail"})

    def normalize(self, raw: RawOpportunity) -> NormalizedOpportunity:
        return NormalizedOpportunity(
            id=f"test:{raw.data.get('id', '?')}",
            source="test",
            source_id=raw.data.get("id", "?"),
            title=raw.data.get("title", ""),
        )


class TestBaseConnector:
    """Tests for BaseConnector default implementations."""

    def test_fetch_all_uses_search_and_normalize(self) -> None:
        """fetch_all calls search then normalizes each result."""
        connector = ConcreteConnector()
        results = connector.fetch_all()
        assert len(results) == 2
        assert results[0].title == "A"
        assert results[1].title == "B"
        assert results[0].id == "test:1"

    def test_fetch_incremental_no_since_returns_all(self) -> None:
        """fetch_incremental with no since returns all."""
        connector = ConcreteConnector()
        results = connector.fetch_incremental()
        assert len(results) == 2
