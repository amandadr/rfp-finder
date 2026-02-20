"""Pipeline orchestration: filter → score with optional enrichment."""

from pathlib import Path
from typing import Optional

from rfp_finder.filtering import FilterEngine
from rfp_finder.models.opportunity import NormalizedOpportunity
from rfp_finder.models.profile import UserProfile
from rfp_finder.scoring import score_opportunities
from rfp_finder.store import AttachmentCacheStore, ExampleStore, OpportunityStore


def run_pipeline(
    profile: UserProfile,
    *,
    db_path: Path,
    status: str = "open",
    top_k: int = 20,
    enrich_top_n: int = 5,
    cache_dir: Optional[Path] = None,
    return_filter_results: bool = False,
):
    """
    Run the full pipeline: load opportunities → filter → score.
    Returns scored results sorted by score descending.
    When return_filter_results=True, returns (scored, filter_results).
    """
    store = OpportunityStore(db_path)
    opportunities = store.get_by_status(status) if status else store.get_all()

    if not opportunities:
        return ([], []) if return_filter_results else []

    engine = FilterEngine(profile)
    results = engine.filter_many(opportunities)
    passed = [r.opportunity for r in results if r.passed]

    if not passed:
        return ([], results) if return_filter_results else []

    ex_store = ExampleStore(db_path)
    cache_store = AttachmentCacheStore(db_path) if enrich_top_n > 0 else None

    scored = score_opportunities(
        profile=profile,
        opportunities=passed,
        example_store=ex_store,
        top_k=top_k,
        enrich_top_n=enrich_top_n,
        cache_dir=cache_dir,
        attachment_cache_store=cache_store,
    )

    if return_filter_results:
        return scored, results
    return scored


def run_filter_only(
    profile: UserProfile,
    *,
    db_path: Path,
    status: str = "open",
) -> tuple[list[NormalizedOpportunity], list]:
    """
    Run filter only. Returns (passed_opportunities, full_filter_results).
    """
    store = OpportunityStore(db_path)
    opportunities = store.get_by_status(status) if status else store.get_all()

    if not opportunities:
        return [], []

    engine = FilterEngine(profile)
    results = engine.filter_many(opportunities)
    passed = [r.opportunity for r in results if r.passed]
    return passed, results
