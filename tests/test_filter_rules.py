"""Unit tests for filter rules."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from rfp_finder.filtering.rules import (
    apply_budget_rule,
    apply_deadline_rule,
    apply_eligibility_rule,
    apply_keywords_rule,
    apply_region_rule,
)
from rfp_finder.models.opportunity import NormalizedOpportunity
from rfp_finder.models.profile import UserProfile


def _make_opp(**kwargs) -> NormalizedOpportunity:
    """Minimal opportunity for testing."""
    defaults = {
        "id": "canadabuys:cb-1",
        "source": "canadabuys",
        "source_id": "cb-1",
        "title": "Test",
    }
    defaults.update(kwargs)
    return NormalizedOpportunity(**defaults)


def _make_profile(**kwargs) -> UserProfile:
    """Minimal profile for testing."""
    return UserProfile(profile_id="test", **kwargs)


class TestRegionRule:
    """Tests for apply_region_rule."""

    def test_no_filter_passes(self) -> None:
        """No eligible/exclude regions passes."""
        profile = _make_profile()
        passed, _, _ = apply_region_rule(_make_opp(region="QC"), profile)
        assert passed is True

    def test_matches_eligible_region(self) -> None:
        """Opp region in eligible_regions passes."""
        profile = _make_profile(eligible_regions=["ON", "National"])
        passed, exp, _ = apply_region_rule(_make_opp(region="ON"), profile)
        assert passed is True
        assert "ON" in exp or "Matches" in exp

    def test_canadabuys_region_mapping(self) -> None:
        """CanadaBuys format '*Ontario (except NCR)' maps to ON."""
        profile = _make_profile(eligible_regions=["ON", "BC"])
        passed, _, _ = apply_region_rule(_make_opp(region="*Ontario (except NCR)"), profile)
        assert passed is True

    def test_excluded_region_fails(self) -> None:
        """Opp region in exclude_regions fails."""
        profile = _make_profile(exclude_regions=["QC"])
        passed, exp, _ = apply_region_rule(_make_opp(region="QC"), profile)
        assert passed is False
        assert "exclude" in exp.lower()

    def test_not_in_eligible_fails(self) -> None:
        """Opp region not in eligible_regions fails."""
        profile = _make_profile(eligible_regions=["ON"])
        passed, _, _ = apply_region_rule(_make_opp(region="QC"), profile)
        assert passed is False

    def test_no_region_on_opp_passes(self) -> None:
        """Missing region on opp passes (not applicable)."""
        profile = _make_profile(eligible_regions=["ON"])
        passed, _, _ = apply_region_rule(_make_opp(region=None), profile)
        assert passed is True


class TestKeywordsRule:
    """Tests for apply_keywords_rule."""

    def test_no_filter_passes(self) -> None:
        """No keywords passes."""
        profile = _make_profile()
        passed, _, _ = apply_keywords_rule(_make_opp(title="Anything"), profile)
        assert passed is True

    def test_matches_keyword_in_title(self) -> None:
        """Keyword in title passes."""
        profile = _make_profile(keywords=["AI"])
        passed, exp, _ = apply_keywords_rule(_make_opp(title="AI software project"), profile)
        assert passed is True
        assert "AI" in exp

    def test_exclude_keyword_fails(self) -> None:
        """Exclude keyword in content fails."""
        profile = _make_profile(exclude_keywords=["construction"])
        passed, _, _ = apply_keywords_rule(_make_opp(title="Construction services"), profile)
        assert passed is False

    def test_no_keyword_match_fails(self) -> None:
        """No required keyword found fails when keywords_mode=required."""
        profile = _make_profile(keywords=["AI", "ML"])
        passed, _, _ = apply_keywords_rule(_make_opp(title="Office supplies"), profile)
        assert passed is False

    def test_keywords_mode_preferred_passes_without_match(self) -> None:
        """With keywords_mode=preferred, pass even without keyword match."""
        profile = _make_profile(keywords=["AI"], keywords_mode="preferred")
        passed, exp, _ = apply_keywords_rule(_make_opp(title="Office supplies"), profile)
        assert passed is True
        assert "optional" in exp.lower() or "AI" in exp


class TestDeadlineRule:
    """Tests for apply_deadline_rule."""

    def test_no_filter_passes(self) -> None:
        """No max_days_to_close passes."""
        profile = _make_profile()
        passed, _, _ = apply_deadline_rule(_make_opp(closing_at=datetime.now(timezone.utc) + timedelta(days=30)), profile)
        assert passed is True

    def test_past_closing_fails(self) -> None:
        """Past closing date fails."""
        profile = _make_profile(max_days_to_close=60)
        past = datetime.now(timezone.utc) - timedelta(days=1)
        passed, _, _ = apply_deadline_rule(_make_opp(closing_at=past), profile)
        assert passed is False

    def test_within_window_passes(self) -> None:
        """Closing within window passes."""
        profile = _make_profile(max_days_to_close=60)
        future = datetime.now(timezone.utc) + timedelta(days=30)
        passed, exp, _ = apply_deadline_rule(_make_opp(closing_at=future), profile)
        assert passed is True
        assert "30" in exp or "within" in exp.lower()

    def test_no_closing_date_passes(self) -> None:
        """Missing closing_at passes (not applicable)."""
        profile = _make_profile(max_days_to_close=30)
        passed, _, _ = apply_deadline_rule(_make_opp(closing_at=None), profile)
        assert passed is True


class TestBudgetRule:
    """Tests for apply_budget_rule."""

    def test_no_filter_passes(self) -> None:
        """No budget filter passes."""
        profile = _make_profile()
        passed, _, _ = apply_budget_rule(_make_opp(budget_max=Decimal("100000")), profile)
        assert passed is True

    def test_within_max_passes(self) -> None:
        """Opp budget within profile max passes."""
        profile = _make_profile(max_budget=Decimal("500000"))
        passed, _, _ = apply_budget_rule(_make_opp(budget_max=Decimal("100000")), profile)
        assert passed is True

    def test_above_max_fails(self) -> None:
        """Opp budget above profile max fails."""
        profile = _make_profile(max_budget=Decimal("50000"))
        passed, _, _ = apply_budget_rule(_make_opp(budget_min=Decimal("100000")), profile)
        assert passed is False

    def test_no_budget_on_opp_passes(self) -> None:
        """Missing budget on opp passes (not applicable)."""
        profile = _make_profile(max_budget=Decimal("100000"))
        passed, _, _ = apply_budget_rule(_make_opp(), profile)
        assert passed is True


class TestEligibilityRule:
    """Tests for apply_eligibility_rule."""

    def test_no_filter_returns_unknown(self) -> None:
        """No eligibility filter returns unknown."""
        profile = _make_profile()
        elig, _ = apply_eligibility_rule(_make_opp(), profile)
        assert elig == "unknown"

    def test_no_opp_fields_returns_unknown(self) -> None:
        """Opp without eligibility fields returns unknown."""
        profile = _make_profile(citizenship_required="canadian")
        elig, _ = apply_eligibility_rule(_make_opp(), profile)
        assert elig == "unknown"

    def test_matching_citizenship_returns_eligible(self) -> None:
        """Matching citizenship returns eligible."""
        profile = _make_profile(citizenship_required="canadian")
        opp = _make_opp(citizenship_required="canadian")
        elig, _ = apply_eligibility_rule(opp, profile)
        assert elig == "eligible"

    def test_conflicting_citizenship_returns_ineligible(self) -> None:
        """Conflicting citizenship returns ineligible."""
        profile = _make_profile(citizenship_required="none")
        opp = _make_opp(citizenship_required="canadian")
        elig, exp = apply_eligibility_rule(opp, profile)
        assert elig == "ineligible"
        assert "citizenship" in exp.lower()
