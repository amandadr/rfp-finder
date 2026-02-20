"""Filter engine with pluggable rules and explanation trail."""

from datetime import datetime, timezone
from typing import Callable, Optional

from pydantic import BaseModel, Field

from rfp_finder.models.opportunity import NormalizedOpportunity
from rfp_finder.models.profile import UserProfile

from .rules import (
    apply_budget_rule,
    apply_deadline_rule,
    apply_eligibility_rule,
    apply_keywords_rule,
    apply_region_rule,
)


class FilterResult(BaseModel):
    """Result of filtering an opportunity against a profile."""

    passed: bool = Field(..., description="All hard filters passed")
    explanations: list[str] = Field(default_factory=list)
    eligibility: str = Field(..., description="eligible | ineligible | unknown")
    opportunity: NormalizedOpportunity = Field(..., description="The opportunity that was filtered")
    excluded_by_rule: Optional[str] = Field(
        default=None,
        description="First rule that excluded (region|keywords|deadline|budget)",
    )


RuleFn = Callable[[NormalizedOpportunity, UserProfile], tuple[bool, str, str]]


class FilterEngine:
    """
    Applies profile-based filters to opportunities.
    Each rule returns (passed, explanation); hard filters can exclude;
    eligibility is separate (unknown does not exclude).
    """

    def __init__(self, profile: UserProfile):
        self.profile = profile
        self._hard_rules: list[RuleFn] = [
            apply_region_rule,
            apply_keywords_rule,
            apply_deadline_rule,
            apply_budget_rule,
        ]

    def filter(self, opp: NormalizedOpportunity) -> FilterResult:
        """Apply all rules and return FilterResult with explanation trail."""
        explanations: list[str] = []
        all_passed = True
        excluded_by: Optional[str] = None

        for rule_fn in self._hard_rules:
            passed, explanation, rule_id = rule_fn(opp, self.profile)
            explanations.append(explanation)
            if not passed:
                all_passed = False
                if excluded_by is None:
                    excluded_by = rule_id

        eligibility, elig_explanation = apply_eligibility_rule(opp, self.profile)
        explanations.append(elig_explanation)

        return FilterResult(
            passed=all_passed,
            explanations=explanations,
            eligibility=eligibility,
            opportunity=opp,
            excluded_by_rule=excluded_by,
        )

    def filter_many(
        self,
        opportunities: list[NormalizedOpportunity],
    ) -> list[FilterResult]:
        """Filter multiple opportunities; returns all with full results."""
        return [self.filter(opp) for opp in opportunities]

    def filter_passed(
        self,
        opportunities: list[NormalizedOpportunity],
    ) -> list[FilterResult]:
        """Filter and return only results that passed hard filters."""
        results = self.filter_many(opportunities)
        return [r for r in results if r.passed]
