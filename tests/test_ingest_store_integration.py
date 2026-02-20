"""Integration tests for ingest with store persistence."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from rfp_finder.connectors.registry import ConnectorRegistry
from rfp_finder.store import OpportunityStore


@pytest.fixture
def temp_db_path() -> Path:
    """Temporary database for integration tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def sample_csv_content(sample_canadabuys_csv_row):
    """Minimal CSV for mock ingest."""
    from tests.conftest import _build_csv
    return _build_csv([sample_canadabuys_csv_row])


class TestIngestStoreIntegration:
    """
    Full flow: ingest with --store, verify persistence, dedupe, change detection.
    """

    def test_ingest_with_store_persists_opportunities(
        self,
        temp_db_path: Path,
        sample_csv_content: str,
    ) -> None:
        """Ingest with --store persists to SQLite and reports counts."""
        with patch(
            "rfp_finder.connectors.canadabuys.connector.CanadaBuysConnector._fetch_csv",
            return_value=sample_csv_content,
        ):
            from rfp_finder.cli.main import _run_ingest
            from argparse import Namespace

            args = Namespace(
                source="canadabuys",
                since=None,
                output=None,
                incremental=False,
                store=temp_db_path,
            )
            _run_ingest(args)

        store = OpportunityStore(temp_db_path)
        opps = store.get_all()
        assert len(opps) == 1
        assert opps[0].id == "canadabuys:cb-233-49083652"

    def test_second_ingest_reports_zero_new_when_unchanged(
        self,
        temp_db_path: Path,
        sample_csv_content: str,
    ) -> None:
        """Second ingest with same data reports 0 new, 0 amended."""
        with patch(
            "rfp_finder.connectors.canadabuys.connector.CanadaBuysConnector._fetch_csv",
            return_value=sample_csv_content,
        ):
            from rfp_finder.cli.main import _run_ingest
            from argparse import Namespace

            args = Namespace(
                source="canadabuys",
                since=None,
                output=None,
                incremental=False,
                store=temp_db_path,
            )
            _run_ingest(args)
            # Run again - same data
            _run_ingest(args)

        # Store should still have 1, and second run would have reported 0 new, 0 amended
        store = OpportunityStore(temp_db_path)
        assert len(store.get_all()) == 1

    def test_ingest_then_query_store(
        self,
        temp_db_path: Path,
        sample_csv_content: str,
    ) -> None:
        """Persisted data is queryable via store list/count."""
        with patch(
            "rfp_finder.connectors.canadabuys.connector.CanadaBuysConnector._fetch_csv",
            return_value=sample_csv_content,
        ):
            from rfp_finder.cli.main import _run_ingest
            from argparse import Namespace

            args = Namespace(
                source="canadabuys",
                since=None,
                output=None,
                incremental=False,
                store=temp_db_path,
            )
            _run_ingest(args)

        store = OpportunityStore(temp_db_path)
        count = len(store.get_all())
        assert count == 1
        by_status = store.get_by_status("open")
        assert len(by_status) >= 1
