"""AI relevance scoring for Phase 4."""

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
) -> list[dict]:
    """
    Score and rank opportunities. Pipeline:
    1. Similarity shortlist (good/bad example overlap)
    2. LLM scoring for top_k
    3. Sort by score descending
    """
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

    results: list[dict] = []
    for opp in shortlist:
        llm_result = score_with_llm(opp, profile)
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
