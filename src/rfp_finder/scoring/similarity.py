"""Text similarity for relevance shortlisting. Uses bag-of-words overlap (no heavy deps)."""

import re
from collections import Counter


def _tokenize(text: str) -> list[str]:
    """Lowercase, extract word tokens (alphanumeric)."""
    return re.findall(r"\b[a-z0-9]{2,}\b", (text or "").lower())


def _tf(text: str) -> Counter:
    """Term frequency for text."""
    return Counter(_tokenize(text))


def overlap_score(
    query_tf: Counter,
    positive_tfs: list[Counter],
    negative_tfs: list[Counter],
) -> float:
    """
    Score how much query overlaps with positive examples vs negative.
    Higher = more like good examples, less like bad.
    Returns 0-1 range (can exceed 1 if very strong match).
    """
    if not positive_tfs and not negative_tfs:
        return 0.5  # No examples: neutral

    pos_score = 0.0
    for ptf in positive_tfs:
        common = sum(query_tf[t] * ptf[t] for t in query_tf if t in ptf)
        total_ptf = sum(ptf.values()) or 1
        pos_score += common / total_ptf
    pos_score = pos_score / len(positive_tfs) if positive_tfs else 0.0

    neg_score = 0.0
    for ntf in negative_tfs:
        common = sum(query_tf[t] * ntf[t] for t in query_tf if t in ntf)
        total_ntf = sum(ntf.values()) or 1
        neg_score += common / total_ntf
    neg_score = neg_score / len(negative_tfs) if negative_tfs else 0.0

    # Positive boost, negative penalty. Normalize to ~0-1.
    raw = pos_score - neg_score * 1.5  # Penalize bad overlap more
    return max(0.0, min(1.0, 0.5 + raw))


def compute_similarity_scores(
    opportunity_texts: list[str],
    good_texts: list[str],
    bad_texts: list[str],
) -> list[float]:
    """Compute similarity score for each opportunity text."""
    good_tfs = [_tf(t) for t in good_texts if t.strip()]
    bad_tfs = [_tf(t) for t in bad_texts if t.strip()]
    scores: list[float] = []
    for text in opportunity_texts:
        qtf = _tf(text)
        s = overlap_score(qtf, good_tfs, bad_tfs)
        scores.append(s)
    return scores
