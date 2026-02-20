"""Integration test for full ingest flow."""

import json

import pytest

from rfp_finder.connectors.registry import ConnectorRegistry
from rfp_finder.models.opportunity import NormalizedOpportunity


class TestIngestIntegration:
    """
    Integration tests for the full ingest pipeline.
    Tests the complete flow: registry -> connector -> fetch -> normalize -> output.
    Uses mocked CSV to avoid network dependency and ensure deterministic results.
    """

    def test_full_ingest_produces_normalized_opportunities(
        self,
        canadabuys_connector_patched,
    ) -> None:
        """Full flow: registry -> connector -> fetch_all -> verify normalized output."""
        with canadabuys_connector_patched:
            connector = ConnectorRegistry.get("canadabuys")
            opportunities = connector.fetch_all()

        assert len(opportunities) > 0, "Should fetch at least one opportunity"

        for opp in opportunities:
            assert isinstance(opp, NormalizedOpportunity)
            assert opp.id.startswith("canadabuys:")
            assert opp.source == "canadabuys"
            assert opp.source_id
            assert opp.title
            assert opp.first_seen_at is not None
            assert opp.last_seen_at is not None
            assert opp.content_hash is not None

    def test_ingest_output_serializable(
        self,
        canadabuys_connector_patched,
    ) -> None:
        """Normalized opportunities serialize to JSON (for CLI output)."""
        with canadabuys_connector_patched:
            connector = ConnectorRegistry.get("canadabuys")
            opportunities = connector.fetch_all()

        assert len(opportunities) > 0
        output = json.dumps(
            [o.model_dump(mode="json") for o in opportunities],
            indent=2,
            default=str,
        )
        parsed = json.loads(output)
        assert len(parsed) == len(opportunities)
        assert all("id" in p and "title" in p for p in parsed)

    def test_incremental_fetch_returns_valid_list(
        self,
        canadabuys_connector_patched,
    ) -> None:
        """Incremental fetch returns valid normalized opportunities."""
        with canadabuys_connector_patched:
            connector = ConnectorRegistry.get("canadabuys")
            incremental = connector.fetch_incremental()

        for opp in incremental:
            assert isinstance(opp, NormalizedOpportunity)
            assert opp.source == "canadabuys"
