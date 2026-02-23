"""Unit tests for ConnectorRegistry."""

import pytest

from rfp_finder.connectors.registry import ConnectorRegistry


class TestConnectorRegistry:
    """Tests for ConnectorRegistry."""

    def test_get_canadabuys(self) -> None:
        """Registry returns CanadaBuys connector for 'canadabuys'."""
        connector = ConnectorRegistry.get("canadabuys")
        assert connector.source_id == "canadabuys"

    def test_get_case_insensitive(self) -> None:
        """Registry is case-insensitive."""
        c1 = ConnectorRegistry.get("CanadaBuys")
        c2 = ConnectorRegistry.get("canadabuys")
        assert c1.source_id == c2.source_id

    def test_unknown_source_raises(self) -> None:
        """Unknown source raises ValueError."""
        with pytest.raises(ValueError, match="Unknown source: merx"):
            ConnectorRegistry.get("merx")

    def test_available_sources(self) -> None:
        """available_sources returns canadabuys and bidsandtenders."""
        sources = ConnectorRegistry.available_sources()
        assert "canadabuys" in sources
        assert "bidsandtenders" in sources

    def test_get_bidsandtenders(self) -> None:
        """Registry returns BidsTenders connector for 'bidsandtenders'."""
        connector = ConnectorRegistry.get("bidsandtenders")
        assert connector.source_id == "bidsandtenders"
