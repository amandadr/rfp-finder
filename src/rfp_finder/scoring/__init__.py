"""AI relevance scoring for Phase 4."""

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from rfp_finder.models.opportunity import NormalizedOpportunity
from rfp_finder.models.profile import UserProfile
from rfp_finder.store.example_store import ExampleStore

from .llm import LLMScoringResult, score_with_llm
from .similarity import compute_similarity_scores


def score_opportunities(
    profile: UserProfile,
    opportunities: list[NormalizedOpportunity],
    example_store: ExampleStore,
    top_k: int = 20,
    *,
    enrich_top_n: int = 0,
    cache_dir: Optional[Path] = None,
    attachment_cache_store: Optional["AttachmentCacheStore"] = None,
) -> list[dict]:
    """
    Score and rank opportunities. Pipeline:
    1. Similarity shortlist (good/bad example overlap)
    2. Optionally enrich top N with attachment text (Phase 5)
    3. LLM scoring for top_k
    4. Sort by score descending
    """
    if TYPE_CHECKING:
        from rfp_finder.store.attachment_cache import AttachmentCacheStore

    good_texts, bad_texts = example_store.get_texts_for_profile(profile.profile_id)
    opp_texts = [
        f"{o.title} {o.summary or ''} {' '.join(o.categories or [])}"
        for o in opportunities
    ]
    sim_scores = compute_similarity_scores(opp_texts, good_texts, bad_texts)

    # Pair (opp, sim_score) and sort by similarity
    paired = list(zip(opportunities, sim_scores))
    paired.sort(key=lambda x: x[1], reverse=True)
    shortlist = [p[0] for p in paired[:top_k]]

    # For enrichment: prefer opportunities with attachments (more PDF content to score)
    enrich_order = (
        sorted(
            range(len(shortlist)),
            key=lambda i: (
                not bool(shortlist[i].attachments),
                -paired[i][1],
            ),
        )[:enrich_top_n]
        if enrich_top_n
        else []
    )

    results: list[dict] = []
    can_enrich = (
        enrich_top_n > 0
        and cache_dir is not None
        and attachment_cache_store is not None
    )
    enriched_indices = set(enrich_order) if can_enrich else set()
    for i, opp in enumerate(shortlist):
        enriched_text: str | None = None
        if can_enrich and i in enriched_indices:
            from rfp_finder.attachments import enrich_opportunity

            enriched_text = enrich_opportunity(
                opp, cache_dir, attachment_cache_store, fetch_missing=True
            )

        sim = paired[i][1] if i < len(paired) else None
        llm_result = score_with_llm(
            opp,
            profile,
            enriched_text=enriched_text or None,
            similarity_score=sim,
        )
        results.append(
            {
                "opportunity": opp.model_dump(mode="json"),
                "score": llm_result.score,
                "match_reasons": llm_result.match_reasons,
                "risks_dealbreakers": llm_result.risks_dealbreakers,
                "evidence_snippets": llm_result.evidence_snippets,
                "confidence": llm_result.confidence,
            }
        )

    results.sort(key=lambda r: r["score"], reverse=True)
    return results
