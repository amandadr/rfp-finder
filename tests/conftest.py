"""Pytest fixtures for rfp-finder tests."""

import csv
from io import StringIO
from unittest.mock import patch

import pytest

from rfp_finder.models.raw import RawOpportunity


def _build_csv(rows: list[dict]) -> str:
    """Build CSV string from list of row dicts."""
    if not rows:
        return ""
    out = StringIO()
    writer = csv.DictWriter(out, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


@pytest.fixture
def sample_canadabuys_csv_row() -> dict[str, str]:
    """Sample CanadaBuys CSV row for testing normalization."""
    return {
        "title-titre-eng": "TSPS Ongoing strategic advisory support",
        "title-titre-fra": "SPTS Soutien consultatif stratégique continu",
        "referenceNumber-numeroReference": "cb-233-49083652",
        "amendmentNumber-numeroModification": "000",
        "solicitationNumber-numeroSollicitation": "20260220",
        "publicationDate-datePublication": "2026-02-20",
        "tenderClosingDate-appelOffresDateCloture": "2026-03-09T14:00:00",
        "amendmentDate-dateModification": "",
        "expectedContractStartDate-dateDebutContratPrevue": "2026-04-01",
        "expectedContractEndDate-dateFinContratPrevue": "2026-12-31",
        "tenderStatus-appelOffresStatut-eng": "Open",
        "tenderStatus-appelOffresStatut-fra": "Ouvert",
        "gsin-nibs": "",
        "gsinDescription-nibsDescription-eng": "",
        "gsinDescription-nibsDescription-fra": "",
        "unspsc": "*80101500",
        "unspscDescription-eng": "Business and corporate management consultation services",
        "unspscDescription-fra": "Services de conseils en gestion des entreprises",
        "procurementCategory-categorieApprovisionnement": "*SRV",
        "noticeType-avisType-eng": "RFP against Supply Arrangement",
        "tradeAgreements-accordsCommerciaux-eng": "*Canadian Free Trade Agreement (CFTA)\n*Canada-Colombia",
        "regionsOfOpportunity-regionAppelOffres-eng": "National",
        "regionsOfDelivery-regionsLivraison-eng": "National Capital Region",
        "contractingEntityName-nomEntitContractante-eng": "Financial Consumer Agency of Canada (FCAC)",
        "noticeURL-URLavis-eng": "https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-233-49083652",
        "attachment-piecesJointes-eng": "https://example.com/doc1.pdf, https://example.com/spec.pdf",
        "tenderDescription-descriptionAppelOffres-eng": "Strategic advisory support services for FCAC.",
    }


@pytest.fixture
def raw_opportunity_from_csv(sample_canadabuys_csv_row: dict[str, str]) -> RawOpportunity:
    """RawOpportunity built from sample CSV row."""
    return RawOpportunity(data=sample_canadabuys_csv_row)


@pytest.fixture
def sample_canadabuys_csv_content(sample_canadabuys_csv_row: dict[str, str]) -> str:
    """Full CSV content with header and one data row."""
    return _build_csv([sample_canadabuys_csv_row])


@pytest.fixture
def canadabuys_connector_patched(sample_canadabuys_csv_content: str):
    """Context manager that patches CanadaBuysConnector._fetch_csv with sample data."""
    return patch(
        "rfp_finder.connectors.canadabuys.connector.CanadaBuysConnector._fetch_csv",
        return_value=sample_canadabuys_csv_content,
    )
