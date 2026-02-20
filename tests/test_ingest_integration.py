"""Integration test for full ingest flow."""

import csv
import json
from io import StringIO

from rfp_finder.connectors.registry import ConnectorRegistry
from rfp_finder.models.opportunity import NormalizedOpportunity


def _build_integration_csv(rows: list[dict]) -> str:
    """Build CSV string from list of row dicts."""
    if not rows:
        return ""
    out = StringIO()
    writer = csv.DictWriter(out, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


# Realistic CanadaBuys CSV structure (subset of columns)
SAMPLE_CSV_ROW = {
    "title-titre-eng": "TSPS Ongoing strategic advisory support",
    "referenceNumber-numeroReference": "cb-233-49083652",
    "solicitationNumber-numeroSollicitation": "20260220",
    "publicationDate-datePublication": "2026-02-20",
    "tenderClosingDate-appelOffresDateCloture": "2026-03-09T14:00:00",
    "amendmentDate-dateModification": "",
    "tenderStatus-appelOffresStatut-eng": "Open",
    "unspsc": "*80101500",
    "procurementCategory-categorieApprovisionnement": "*SRV",
    "regionsOfOpportunity-regionAppelOffres-eng": "National",
    "contractingEntityName-nomEntitContractante-eng": "Financial Consumer Agency of Canada",
    "noticeURL-URLavis-eng": "https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-233-49083652",
    "attachment-piecesJointes-eng": "https://example.com/doc.pdf",
    "tenderDescription-descriptionAppelOffres-eng": "Strategic advisory support services.",
}


class TestIngestIntegration:
    """
    Integration tests for the full ingest pipeline.
    Tests the complete flow: registry -> connector -> fetch -> normalize -> output.
    Uses mocked CSV to avoid network dependency and ensure deterministic results.
    """

    def test_full_ingest_produces_normalized_opportunities(self) -> None:
        """
        Full flow: registry -> connector -> fetch_all -> verify normalized output.
        """
        from unittest.mock import patch

        csv_content = _build_integration_csv([SAMPLE_CSV_ROW])

        with patch(
            "rfp_finder.connectors.canadabuys.connector.CanadaBuysConnector._fetch_csv",
            return_value=csv_content,
        ):
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

    def test_ingest_output_serializable(self) -> None:
        """Normalized opportunities serialize to JSON (for CLI output)."""
        from unittest.mock import patch

        csv_content = _build_integration_csv([SAMPLE_CSV_ROW])

        with patch(
            "rfp_finder.connectors.canadabuys.connector.CanadaBuysConnector._fetch_csv",
            return_value=csv_content,
        ):
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

    def test_incremental_fetch_returns_valid_list(self) -> None:
        """Incremental fetch returns valid normalized opportunities."""
        from unittest.mock import patch

        csv_content = _build_integration_csv([SAMPLE_CSV_ROW])

        with patch(
            "rfp_finder.connectors.canadabuys.connector.CanadaBuysConnector._fetch_csv",
            return_value=csv_content,
        ):
            connector = ConnectorRegistry.get("canadabuys")
            incremental = connector.fetch_incremental()

        for opp in incremental:
            assert isinstance(opp, NormalizedOpportunity)
            assert opp.source == "canadabuys"
