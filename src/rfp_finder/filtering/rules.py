"""Filter rules: each returns (passed, explanation)."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from rfp_finder.models.opportunity import NormalizedOpportunity
from rfp_finder.models.profile import UserProfile


def _normalize_for_match(text: Optional[str]) -> str:
    """Lowercase and strip for matching; empty string if None."""
    return (text or "").lower().strip()


# Map CanadaBuys region substring -> province/territory code (check in order)
_REGION_MAP: list[tuple[str, str]] = [
    ("alberta", "AB"),
    ("british columbia", "BC"),
    ("manitoba", "MB"),
    ("new brunswick", "NB"),
    ("moncton", "NB"),
    ("newfoundland", "NL"),
    ("labrador", "NL"),
    ("nova scotia", "NS"),
    ("ontario", "ON"),
    ("ottawa", "ON"),
    ("ncr", "ON"),
    ("toronto", "ON"),
    ("quebec", "QC"),
    ("montreal", "QC"),
    ("shawinigan", "QC"),
    ("saskatchewan", "SK"),
    ("regina", "SK"),
    ("prince edward", "PE"),
    ("northwest territories", "NT"),
    ("nunavut", "NU"),
    ("yukon", "YT"),
    ("canada", "National"),
    ("national", "National"),
    ("world", "National"),
    ("north america", "National"),
    ("remote offsite", "National"),
    ("unspecified", "National"),
]


def _region_to_code(region: str) -> str:
    """Map CanadaBuys region string (e.g. '*Ontario (except NCR)') to province code."""
    r = region.lower().strip().replace("*", "")
    for substr, code in _REGION_MAP:
        if substr in r:
            return code
    return r.upper()[:2] if len(r) >= 2 else r.upper()


def apply_region_rule(opp: NormalizedOpportunity, profile: UserProfile) -> tuple[bool, str]:
    """
    Region filter: opp.region in profile.eligible_regions or "National".
    Maps CanadaBuys region strings (e.g. "*Ontario (except NCR)") to province codes.
    """
    if not profile.eligible_regions and not profile.exclude_regions:
        return True, "Region filter not set"

    opp_region = (opp.region or "").strip()
    if not opp_region:
        return True, "Region not applicable (no region on opportunity)"

    opp_code = _region_to_code(opp_region)
    eligible_norm = [r.upper().strip() for r in profile.eligible_regions]
    exclude_norm = [r.upper().strip() for r in profile.exclude_regions]

    if opp_code.upper() in exclude_norm:
        return False, f"Excluded: region {opp_region} in exclude_regions"

    if not eligible_norm:
        return True, f"Region {opp_region} (no eligible_regions restriction)"

    if opp_code.upper() in eligible_norm or opp_code == "NATIONAL":
        return True, f"Matches region: {opp_region}"

    return False, f"Excluded: region {opp_region} not in eligible_regions"


def apply_keywords_rule(opp: NormalizedOpportunity, profile: UserProfile) -> tuple[bool, str]:
    """
    Keywords: exclude_keywords always apply (deal-breakers).
    When keywords_mode=required: must match at least one keyword.
    When keywords_mode=preferred or exclude_only: no keyword requirement (pass more to AI).
    """
    if not profile.keywords and not profile.exclude_keywords:
        return True, "Keywords filter not set"

    searchable = " ".join(
        [
            opp.title,
            opp.summary or "",
            " ".join(opp.categories or []),
            " ".join(opp.commodity_codes or []),
        ]
    ).lower()

    for exc in profile.exclude_keywords:
        if exc.lower() in searchable:
            return False, f"Excluded: deal-breaker keyword '{exc}' found"

    mode = getattr(profile, "keywords_mode", "required") or "required"
    if mode in ("preferred", "exclude_only"):
        return True, "Keywords optional (mode: pass to AI)"

    if not profile.keywords:
        return True, "No required keywords"

    for kw in profile.keywords:
        if kw.lower() in searchable:
            return True, f"Matches keyword: {kw}"

    return False, f"No required keywords found (need one of: {profile.keywords})"


def apply_deadline_rule(opp: NormalizedOpportunity, profile: UserProfile) -> tuple[bool, str]:
    """
    Deadline window: closing_at >= today and <= today + max_days_to_close.
    If max_days_to_close not set, no filter. If closing_at missing, pass through.
    """
    if profile.max_days_to_close is None:
        return True, "Deadline filter not set"

    if opp.closing_at is None:
        return True, "Deadline not applicable (no closing date on opportunity)"

    now = datetime.now(timezone.utc)
    closing = opp.closing_at
    if closing.tzinfo is None:
        closing = closing.replace(tzinfo=timezone.utc)

    if closing < now:
        return False, f"Excluded: closing date {opp.closing_at} has passed"

    days_out = (closing - now).days
    if days_out > profile.max_days_to_close:
        return False, f"Excluded: closing in {days_out} days (max {profile.max_days_to_close})"

    return True, f"Closing in {days_out} days (within window)"


def apply_budget_rule(opp: NormalizedOpportunity, profile: UserProfile) -> tuple[bool, str]:
    """
    Budget: opp within profile min_budget/max_budget when both present.
    If profile or opp lacks budget, pass through.
    """
    if profile.min_budget is None and profile.max_budget is None:
        return True, "Budget filter not set"

    opp_min = opp.budget_min
    opp_max = opp.budget_max
    if opp_min is None and opp_max is None:
        return True, "Budget not applicable (no budget on opportunity)"

    if profile.min_budget is not None:
        upper_bound = opp_max if opp_max is not None else opp_min
        if upper_bound is not None and upper_bound < profile.min_budget:
            return False, f"Excluded: max budget {upper_bound} below profile min {profile.min_budget}"

    if profile.max_budget is not None:
        lower_bound = opp_min if opp_min is not None else opp_max
        if lower_bound is not None and lower_bound > profile.max_budget:
            return False, f"Excluded: min budget {lower_bound} above profile max {profile.max_budget}"

    return True, "Within budget range"


def apply_eligibility_rule(opp: NormalizedOpportunity, profile: UserProfile) -> tuple[str, str]:
    """
    Eligibility (explicit only): compare citizenship, security_clearance, local_vendor_only.
    Returns (eligibility, explanation). Unknown does not exclude.
    """
    if (
        profile.citizenship_required is None
        and profile.security_clearance is None
        and profile.local_vendor_only is None
    ):
        return "unknown", "Eligibility filter not set"

    opp_cit = getattr(opp, "citizenship_required", None)
    opp_sec = getattr(opp, "security_clearance", None)
    opp_local = getattr(opp, "local_vendor_only", None)

    if opp_cit is None and opp_sec is None and opp_local is None:
        return "unknown", "Eligibility unknown (no eligibility fields on opportunity)"

    reasons_ineligible: list[str] = []
    reasons_eligible: list[str] = []

    if profile.citizenship_required is not None and opp_cit is not None:
        if opp_cit.lower() != profile.citizenship_required.lower():
            reasons_ineligible.append(
                f"Citizenship: opp requires {opp_cit}, profile has {profile.citizenship_required}"
            )
        else:
            reasons_eligible.append("Citizenship matches")

    if profile.security_clearance is not None and opp_sec is not None:
        if opp_sec.lower() != profile.security_clearance.lower():
            reasons_ineligible.append(
                f"Security clearance: opp requires {opp_sec}, profile has {profile.security_clearance}"
            )
        else:
            reasons_eligible.append("Security clearance matches")

    if profile.local_vendor_only is not None and opp_local is not None:
        if opp_local != profile.local_vendor_only:
            reasons_ineligible.append(
                f"Local vendor: opp={opp_local}, profile={profile.local_vendor_only}"
            )
        else:
            reasons_eligible.append("Local vendor requirement matches")

    if reasons_ineligible:
        return "ineligible", "; ".join(reasons_ineligible)
    if reasons_eligible:
        return "eligible", "; ".join(reasons_eligible)
    return "unknown", "Eligibility unknown (partial field overlap)"
