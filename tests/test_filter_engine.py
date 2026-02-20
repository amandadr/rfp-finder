"""Unit tests for FilterEngine."""

from datetime import datetime, timedelta, timezone

import pytest

from rfp_finder.filtering import FilterEngine, FilterResult
from rfp_finder.models.opportunity import NormalizedOpportunity
from rfp_finder.models.profile import UserProfile


def _make_opp(**kwargs) -> NormalizedOpportunity:
    defaults = {
        "id": "canadabuys:cb-1",
        "source": "canadabuys",
        "source_id": "cb-1",
        "title": "AI Software Development",
        "region": "National",
    }
    defaults.update(kwargs)
    return NormalizedOpportunity(**defaults)


@pytest.fixture
def permissive_profile() -> UserProfile:
    """Profile that passes most opps."""
    return UserProfile(
        profile_id="test",
        eligible_regions=["ON", "National"],
        keywords=[],
    )


class TestFilterEngine:
    """Tests for FilterEngine."""

    def test_filter_returns_filter_result(self, permissive_profile: UserProfile) -> None:
        """filter returns FilterResult with opportunity and explanations."""
        engine = FilterEngine(permissive_profile)
        opp = _make_opp()
        result = engine.filter(opp)
        assert isinstance(result, FilterResult)
        assert result.opportunity == opp
        assert len(result.explanations) >= 4

    def test_filter_passed_includes_matching_opp(self, permissive_profile: UserProfile) -> None:
        """filter_passed returns only results that passed."""
        engine = FilterEngine(permissive_profile)
        opp1 = _make_opp(id="1", title="AI project", region="National")
        opp2 = _make_opp(id="2", title="Office supplies", region="QC")
        profile = UserProfile(profile_id="t", eligible_regions=["National"], keywords=["AI"])
        engine = FilterEngine(profile)
        passed = engine.filter_passed([opp1, opp2])
        assert len(passed) == 1
        assert passed[0].opportunity.id == "1"

    def test_filter_many_returns_all_results(self, permissive_profile: UserProfile) -> None:
        """filter_many returns one result per opportunity."""
        engine = FilterEngine(permissive_profile)
        opps = [_make_opp(id="a"), _make_opp(id="b")]
        results = engine.filter_many(opps)
        assert len(results) == 2
        assert results[0].opportunity.id == "a"
        assert results[1].opportunity.id == "b"
