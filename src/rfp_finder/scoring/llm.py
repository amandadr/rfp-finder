"""LLM-based scoring and rationale. Supports Ollama (local) and OpenAI API."""

import os
from dataclasses import dataclass

from rfp_finder.matching import positive_keyword_matches
from rfp_finder.models.opportunity import NormalizedOpportunity
from rfp_finder.models.profile import UserProfile


@dataclass
class LLMScoringResult:
    """Result from LLM relevance scoring."""

    score: int  # 0-100
    match_reasons: list[str]
    risks_dealbreakers: list[str]
    evidence_snippets: list[str]
    confidence: str  # high | medium | low | insufficient_text | unknown_eligibility


def score_with_llm(
    opp: NormalizedOpportunity,
    profile: UserProfile,
    *,
    enriched_text: str | None = None,
    similarity_score: float | None = None,
) -> LLMScoringResult:
    """
    Score one opportunity with LLM. Uses RFP_FINDER_LLM_PROVIDER env:
    - "ollama" -> Ollama local
    - "openai" -> OpenAI API (needs OPENAI_API_KEY)
    - unset/other -> stub (returns heuristic score)
    enriched_text: when set, used instead of opp.summary for context (includes attachment text).
    """
    provider = (os.environ.get("RFP_FINDER_LLM_PROVIDER") or "").lower()
    if provider == "ollama":
        return _score_ollama(opp, profile, enriched_text=enriched_text)
    if provider == "openai":
        return _score_openai(opp, profile, enriched_text=enriched_text)
    return _score_stub(
        opp, profile, enriched_text=enriched_text, similarity_score=similarity_score
    )


# Lead window for keyword matching (title + first N chars)
_KEYWORD_LEAD_CHARS = 300

# CanadaBuys category codes
_CAT_SRV = "SRV"  # Services
_CAT_CNST = "CNST"  # Construction
# Commodity code prefixes that indicate clearly non-tech (CNST handled separately)
_NON_TECH_PREFIXES = ("56", "90")  # furniture, cleaning (72=construction via CNST)

# Title/lead phrases that indicate non-tech procurement (penalize)
_NON_TECH_TITLE_PHRASES = (
    "office furniture",
    "commercial office furniture",
    "furniture and related",
    "gpu hardware",
    "hardware or equivalent",
    "hardware bundle",
    "flasharray hardware",
    "alternate transportation",
    "transportation services",
)


def _keyword_in_lead(title: str, content: str, keyword: str) -> bool:
    """True if keyword appears in title or first 300 chars of content."""
    title_lower = (title or "").lower()
    content_lower = (content or "").lower()
    lead = content_lower[:_KEYWORD_LEAD_CHARS]
    return positive_keyword_matches(title_lower, keyword) or positive_keyword_matches(
        lead, keyword
    )


def _is_non_tech_category(opp: NormalizedOpportunity) -> bool:
    """True if commodity codes suggest clearly non-tech (CNST handled separately)."""
    for code in opp.commodity_codes or []:
        code = (code or "").replace("*", "").strip()
        if any(code.startswith(p) for p in _NON_TECH_PREFIXES):
            return True
    return False


def _is_non_tech_title_lead(title: str, content: str) -> bool:
    """True if title or first 300 chars indicate non-tech procurement."""
    text = f"{title or ''} {(content or '')[:300]}".lower()
    return any(phrase in text for phrase in _NON_TECH_TITLE_PHRASES)


def _score_stub(
    opp: NormalizedOpportunity,
    profile: UserProfile,
    *,
    enriched_text: str | None = None,
    similarity_score: float | None = None,
) -> LLMScoringResult:
    """Stub: small cumulative boosts, no free-text deal-breaker matching."""
    content = enriched_text or opp.summary or ""
    score = 50
    reasons: list[str] = []
    risks: list[str] = []

    # Similarity to good/bad examples: -15 to +15
    if similarity_score is not None:
        sim_bonus = int((similarity_score - 0.5) * 30)
        sim_bonus = max(-15, min(15, sim_bonus))
        if sim_bonus > 0:
            score += sim_bonus
            reasons.append("Similar to good-fit examples")
        elif sim_bonus < 0:
            score += sim_bonus

    # +3 if PDF present
    if enriched_text and "[Attachment:" in enriched_text:
        score += 3
        reasons.append("PDF attachment content available")

    # +4 if category == SRV (Services) — but not for non-tech services (transportation, etc.)
    cats = [c.upper() for c in (opp.categories or [])]
    if _CAT_SRV in cats and not _is_non_tech_title_lead(opp.title or "", content):
        score += 4
        reasons.append("Category: Services (SRV)")

    # +5 per keyword in first 300 chars (title + lead), max 3 matches
    kw_matches = 0
    if profile.keywords:
        for kw in profile.keywords[:30]:
            if kw_matches >= 3:
                break
            if _keyword_in_lead(opp.title or "", content, kw):
                score += 5
                reasons.append(f"Keyword in scope: {kw}")
                kw_matches += 1

    # -8 if category == CNST (Construction)
    if _CAT_CNST in cats:
        score -= 8
        risks.append("Category: Construction (CNST)")

    # -10 if category/commodity clearly non-tech
    if _is_non_tech_category(opp):
        score -= 10
        risks.append("Category/commodity: non-tech")

    # -10 if title/lead indicates non-tech (furniture, hardware procurement, transportation)
    if _is_non_tech_title_lead(opp.title or "", content):
        score -= 10
        risks.append("Title/scope: non-tech procurement")

    # Dampen score by confidence (low confidence = less trust in the signal)
    conf = _confidence_from_content(opp, content, enriched_text)
    dampen = {"high": 0, "medium": -3, "low": -8, "insufficient_text": -15}.get(
        conf, -5
    )
    score += dampen

    score = max(0, min(100, score))
    evidence = [opp.title[:100]] if opp.title and opp.title != "Untitled" else []
    if content:
        evidence.append(content[:150].replace("\n", " ").strip() + ("..." if len(content) > 150 else ""))
    return LLMScoringResult(
        score=score,
        match_reasons=reasons or ["Heuristic match (no LLM configured)"],
        risks_dealbreakers=risks,
        evidence_snippets=evidence[:3],
        confidence=conf,
    )


def _confidence_from_content(
    opp: NormalizedOpportunity, content: str, enriched_text: str | None
) -> str:
    """Tie confidence to extraction quality: PDF enriched -> higher confidence."""
    if enriched_text and "[Attachment:" in enriched_text:
        return "medium" if len(content) > 500 else "low"
    if opp.attachments and not enriched_text:
        return "insufficient_text"  # Has PDFs but none extracted
    if content and len(content) > 200:
        return "medium"
    return "low"


def _score_ollama(
    opp: NormalizedOpportunity, profile: UserProfile, *, enriched_text: str | None = None
) -> LLMScoringResult:
    """Score using local Ollama. Requires ollama running with compatible model."""
    try:
        import json

        import httpx
    except ImportError:
        return _score_stub(opp, profile, enriched_text=enriched_text)
    model = os.environ.get("RFP_FINDER_LLM_MODEL", "llama3.2")
    prompt = _build_prompt(opp, profile, enriched_text=enriched_text)
    try:
        resp = httpx.post(
            "http://localhost:11434/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        resp.raise_for_status()
        out = resp.json()
        return _parse_llm_response(out.get("response", ""), opp)
    except Exception:
        return _score_stub(opp, profile)


def _score_openai(
    opp: NormalizedOpportunity, profile: UserProfile, *, enriched_text: str | None = None
) -> LLMScoringResult:
    """Score using OpenAI API."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return _score_stub(opp, profile, enriched_text=enriched_text)
    try:
        from openai import OpenAI
    except ImportError:
        return _score_stub(opp, profile, enriched_text=enriched_text)
    client = OpenAI(api_key=api_key)
    prompt = _build_prompt(opp, profile, enriched_text=enriched_text)
    try:
        response = client.chat.completions.create(
            model=os.environ.get("RFP_FINDER_LLM_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        text = response.choices[0].message.content or ""
        return _parse_llm_response(text, opp)
    except Exception:
        return _score_stub(opp, profile)


def _build_prompt(
    opp: NormalizedOpportunity, profile: UserProfile, *, enriched_text: str | None = None
) -> str:
    """Build scoring prompt."""
    kw = ", ".join(profile.keywords[:15]) if profile.keywords else "N/A"
    cats = ", ".join(profile.preferred_categories[:5]) if profile.preferred_categories else "N/A"
    exc = ", ".join(profile.exclude_keywords[:5]) if profile.exclude_keywords else "None"
    content = (enriched_text or opp.summary or "")[:8000]  # Larger limit when enriched
    return f"""Score this RFP opportunity 0-100 for relevance. Reply with ONLY valid JSON:
{{"score": <0-100>, "match_reasons": ["..."], "risks": ["..."], "evidence": ["..."], "confidence": "high|medium|low"}}

Profile: keywords=[{kw}], categories=[{cats}], exclude=[{exc}]
Opportunity: title="{opp.title}"
Content: {content}

JSON:"""


def _parse_llm_response(text: str, opp: NormalizedOpportunity) -> LLMScoringResult:
    """Parse LLM JSON response into LLMScoringResult."""
    import json
    import re

    # Extract JSON block if wrapped in markdown
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    raw = match.group(0) if match else "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return LLMScoringResult(
            score=50,
            match_reasons=["Could not parse LLM response"],
            risks_dealbreakers=[],
            evidence_snippets=[opp.title[:100]] if opp.title else [],
            confidence="low",
        )
    return LLMScoringResult(
        score=int(data.get("score", 50)),
        match_reasons=data.get("match_reasons", []),
        risks_dealbreakers=data.get("risks", []),
        evidence_snippets=data.get("evidence", []),
        confidence=data.get("confidence", "medium"),
    )
