"""Integration test for filter flow."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from rfp_finder.filtering import FilterEngine
from rfp_finder.models.opportunity import NormalizedOpportunity
from rfp_finder.models.profile import UserProfile
from rfp_finder.store import OpportunityStore


@pytest.fixture
def sample_opps() -> list[NormalizedOpportunity]:
    """Sample opportunities for filtering."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    future = now + timedelta(days=30)
    return [
        NormalizedOpportunity(
            id="canadabuys:1",
            source="canadabuys",
            source_id="1",
            title="AI and Machine Learning Services",
            region="National",
            closing_at=future,
        ),
        NormalizedOpportunity(
            id="canadabuys:2",
            source="canadabuys",
            source_id="2",
            title="Construction Services",
            region="QC",
            closing_at=future,
        ),
        NormalizedOpportunity(
            id="canadabuys:3",
            source="canadabuys",
            source_id="3",
            title="Software Development RFP",
            region="ON",
            closing_at=future,
        ),
    ]


@pytest.fixture
def profile_yaml(tmp_path: Path) -> Path:
    """Create temp profile YAML. Use quoted ON to avoid YAML parsing as bool."""
    path = tmp_path / "profile.yaml"
    path.write_text("""
profile_id: test
filters:
  regions: ["ON", "National"]
  keywords: [AI, software]
  exclude_keywords: [construction]
  max_days_to_close: 90
eligibility:
  citizenship_required: null
""")
    return path


class TestFilterIntegration:
    """Integration tests for filter pipeline."""

    def test_filter_pipeline_with_profile(
        self,
        sample_opps: list[NormalizedOpportunity],
        profile_yaml: Path,
    ) -> None:
        """Full pipeline: load profile, filter opps, get passed + explanations."""
        profile = UserProfile.from_yaml(profile_yaml)
        engine = FilterEngine(profile)
        results = engine.filter_many(sample_opps)

        assert len(results) == 3
        passed = [r for r in results if r.passed]
        assert len(passed) == 2  # AI/software and Software; Construction excluded
        assert all(r.opportunity.id != "canadabuys:2" for r in passed)

    def test_filter_with_store(
        self,
        sample_opps: list[NormalizedOpportunity],
        profile_yaml: Path,
    ) -> None:
        """Filter reads from store and produces filtered output."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        try:
            store = OpportunityStore(db_path)
            for opp in sample_opps:
                store.upsert(opp)

            profile = UserProfile.from_yaml(profile_yaml)
            engine = FilterEngine(profile)
            from_store = store.get_all()
            results = engine.filter_passed(from_store)

            assert len(results) >= 1
        finally:
            db_path.unlink(missing_ok=True)
