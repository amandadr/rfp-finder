"""LLM-based scoring and rationale. Supports Ollama (local) and OpenAI API."""

import os
from dataclasses import dataclass

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
    return _score_stub(opp, profile, enriched_text=enriched_text)


def _keyword_matches(text: str, keyword: str) -> bool:
    """Full phrase match, or word-level match for multi-word keywords."""
    kw_lower = keyword.lower()
    if kw_lower in text:
        return True
    words = kw_lower.split()
    if len(words) <= 1:
        return False
    # Multi-word: match if any significant word appears (partial relevance)
    return sum(1 for w in words if len(w) > 2 and w in text) >= min(2, len(words))


def _score_stub(
    opp: NormalizedOpportunity, profile: UserProfile, *, enriched_text: str | None = None
) -> LLMScoringResult:
    """Stub: heuristic score when no LLM configured."""
    content = enriched_text or opp.summary or ""
    text = f"{opp.title} {content}".lower()
    cats_str = " ".join(opp.categories or []).lower()
    score = 50
    reasons: list[str] = []
    risks: list[str] = []
    # Check up to 30 keywords; use word-level matching for multi-word phrases
    if profile.keywords:
        for kw in profile.keywords[:30]:
            if _keyword_matches(text, kw):
                score += 4
                reasons.append(f"Matches keyword: {kw}")
    # Match preferred_categories only against structured categories (avoid HR dept "IT" false positives)
    if profile.preferred_categories and opp.categories:
        for cat in profile.preferred_categories[:5]:
            if cat.lower() in cats_str:
                score += 5
                reasons.append(f"Category match: {cat}")
    # Boost when PDF content was successfully extracted (enrichment worked)
    if enriched_text and "[Attachment:" in enriched_text:
        score += 10
        reasons.append("PDF attachment content available")
    for exc in profile.exclude_keywords:
        if exc.lower() in text:
            score -= 20
            risks.append(f"Deal-breaker: {exc}")
    score = max(0, min(100, score))
    conf = _confidence_from_content(opp, content, enriched_text)
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
