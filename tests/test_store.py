"""Unit tests for OpportunityStore."""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from rfp_finder.models.opportunity import NormalizedOpportunity
from rfp_finder.store import OpportunityStore, RunRecord


def _make_opp(
    opp_id: str = "canadabuys:cb-123",
    source: str = "canadabuys",
    source_id: str = "cb-123",
    title: str = "Test Tender",
    content_hash: str = "abc123",
    status: str = "open",
    closing_at: datetime | None = None,
) -> NormalizedOpportunity:
    now = datetime.now(timezone.utc)
    return NormalizedOpportunity(
        id=opp_id,
        source=source,
        source_id=source_id,
        title=title,
        summary="Test summary",
        content_hash=content_hash,
        status=status,
        first_seen_at=now,
        last_seen_at=now,
        closing_at=closing_at,
    )


@pytest.fixture
def temp_db() -> Path:
    """Temporary database path for isolated tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def store(temp_db: Path) -> OpportunityStore:
    """OpportunityStore with temporary database."""
    return OpportunityStore(temp_db)


class TestOpportunityStoreUpsert:
    """Tests for upsert."""

    def test_upsert_new_returns_true_for_new(self, store: OpportunityStore) -> None:
        """First upsert returns (was_new=True, was_amended=False)."""
        opp = _make_opp()
        was_new, was_amended = store.upsert(opp)
        assert was_new is True
        assert was_amended is False

    def test_upsert_existing_same_hash_returns_both_false(self, store: OpportunityStore) -> None:
        """Second upsert with same content returns (False, False)."""
        opp = _make_opp(content_hash="same")
        store.upsert(opp)
        was_new, was_amended = store.upsert(opp)
        assert was_new is False
        assert was_amended is False

    def test_upsert_existing_different_hash_returns_amended(self, store: OpportunityStore) -> None:
        """Upsert with changed content returns (False, True)."""
        opp1 = _make_opp(content_hash="hash1", title="Original")
        opp2 = _make_opp(content_hash="hash2", title="Amended")
        store.upsert(opp1)
        was_new, was_amended = store.upsert(opp2)
        assert was_new is False
        assert was_amended is True

    def test_upsert_deduplicates_by_source_and_source_id(self, store: OpportunityStore) -> None:
        """Same (source, source_id) updates existing; different id inserts new."""
        opp1 = _make_opp(opp_id="canadabuys:cb-1", source_id="cb-1")
        opp2 = _make_opp(opp_id="canadabuys:cb-2", source_id="cb-2")
        store.upsert(opp1)
        store.upsert(opp2)
        all_opps = store.get_all()
        assert len(all_opps) == 2


class TestOpportunityStoreQueries:
    """Tests for get_all, get_by_status, get_modified_since, get."""

    def test_get_all_returns_inserted(self, store: OpportunityStore) -> None:
        """get_all returns all upserted opportunities."""
        store.upsert(_make_opp(opp_id="canadabuys:a", source_id="a"))
        store.upsert(_make_opp(opp_id="canadabuys:b", source_id="b"))
        opps = store.get_all()
        assert len(opps) == 2
        ids = {o.id for o in opps}
        assert "canadabuys:a" in ids
        assert "canadabuys:b" in ids

    def test_get_by_status_filters(self, store: OpportunityStore) -> None:
        """get_by_status returns only matching status."""
        store.upsert(_make_opp(opp_id="canadabuys:1", source_id="1", status="open"))
        store.upsert(_make_opp(opp_id="canadabuys:2", source_id="2", status="closed"))
        store.upsert(_make_opp(opp_id="canadabuys:3", source_id="3", status="open"))
        open_opps = store.get_by_status("open")
        assert len(open_opps) == 2
        closed_opps = store.get_by_status("closed")
        assert len(closed_opps) == 1

    def test_get_by_status_respects_resolved_status(self, store: OpportunityStore) -> None:
        """Opportunities with past closing_at are stored as closed."""
        past = datetime.now(timezone.utc) - timedelta(days=1)
        opp = _make_opp(opp_id="canadabuys:past", source_id="past", status="open", closing_at=past)
        store.upsert(opp)
        closed = store.get_by_status("closed")
        assert any(o.id == "canadabuys:past" for o in closed)

    def test_get_modified_since(self, store: OpportunityStore) -> None:
        """get_modified_since returns opps modified after given time."""
        store.upsert(_make_opp(opp_id="1"))
        opps = store.get_modified_since(datetime.now(timezone.utc) - timedelta(minutes=5))
        assert len(opps) >= 1

    def test_get_single(self, store: OpportunityStore) -> None:
        """get returns single opportunity by id."""
        opp = _make_opp(opp_id="canadabuys:cb-xyz")
        store.upsert(opp)
        found = store.get("canadabuys:cb-xyz")
        assert found is not None
        assert found.title == "Test Tender"

    def test_get_nonexistent_returns_none(self, store: OpportunityStore) -> None:
        """get returns None for unknown id."""
        assert store.get("canadabuys:nonexistent") is None


class TestOpportunityStoreRuns:
    """Tests for run tracking."""

    def test_start_run_returns_record(self, store: OpportunityStore) -> None:
        """start_run returns RunRecord with id."""
        run = store.start_run("canadabuys")
        assert isinstance(run, RunRecord)
        assert run.id > 0
        assert run.source == "canadabuys"
        assert run.status == "running"

    def test_finish_run_updates_record(self, store: OpportunityStore) -> None:
        """finish_run persists run completion."""
        run = store.start_run("canadabuys")
        store.finish_run(
            run.id,
            items_fetched=10,
            items_new=5,
            items_amended=2,
            status="completed",
        )
        with store._connection() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run.id,)).fetchone()
        assert row is not None
        assert row["status"] == "completed"
        assert row["items_fetched"] == 10
        assert row["items_new"] == 5
        assert row["items_amended"] == 2
