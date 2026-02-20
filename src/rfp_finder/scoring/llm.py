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
) -> LLMScoringResult:
    """
    Score one opportunity with LLM. Uses RFP_FINDER_LLM_PROVIDER env:
    - "ollama" -> Ollama local
    - "openai" -> OpenAI API (needs OPENAI_API_KEY)
    - unset/other -> stub (returns heuristic score)
    """
    provider = (os.environ.get("RFP_FINDER_LLM_PROVIDER") or "").lower()
    if provider == "ollama":
        return _score_ollama(opp, profile)
    if provider == "openai":
        return _score_openai(opp, profile)
    return _score_stub(opp, profile)


def _score_stub(opp: NormalizedOpportunity, profile: UserProfile) -> LLMScoringResult:
    """Stub: heuristic score when no LLM configured."""
    text = f"{opp.title} {opp.summary or ''} {' '.join(opp.categories or [])}".lower()
    score = 50
    reasons: list[str] = []
    risks: list[str] = []
    if profile.keywords:
        for kw in profile.keywords[:5]:
            if kw.lower() in text:
                score += 8
                reasons.append(f"Matches keyword: {kw}")
    if profile.preferred_categories:
        for cat in profile.preferred_categories[:3]:
            if cat.lower() in text:
                score += 5
                reasons.append(f"Category match: {cat}")
    for exc in profile.exclude_keywords:
        if exc.lower() in text:
            score -= 20
            risks.append(f"Deal-breaker: {exc}")
    score = max(0, min(100, score))
    conf = "medium" if (opp.summary and len(opp.summary) > 100) else "low"
    return LLMScoringResult(
        score=score,
        match_reasons=reasons or ["Heuristic match (no LLM configured)"],
        risks_dealbreakers=risks,
        evidence_snippets=[opp.title[:100]] if opp.title else [],
        confidence=conf,
    )


def _score_ollama(opp: NormalizedOpportunity, profile: UserProfile) -> LLMScoringResult:
    """Score using local Ollama. Requires ollama running with compatible model."""
    try:
        import json

        import httpx
    except ImportError:
        return _score_stub(opp, profile)
    model = os.environ.get("RFP_FINDER_LLM_MODEL", "llama3.2")
    prompt = _build_prompt(opp, profile)
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


def _score_openai(opp: NormalizedOpportunity, profile: UserProfile) -> LLMScoringResult:
    """Score using OpenAI API."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return _score_stub(opp, profile)
    try:
        from openai import OpenAI
    except ImportError:
        return _score_stub(opp, profile)
    client = OpenAI(api_key=api_key)
    prompt = _build_prompt(opp, profile)
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


def _build_prompt(opp: NormalizedOpportunity, profile: UserProfile) -> str:
    """Build scoring prompt."""
    kw = ", ".join(profile.keywords[:15]) if profile.keywords else "N/A"
    cats = ", ".join(profile.preferred_categories[:5]) if profile.preferred_categories else "N/A"
    exc = ", ".join(profile.exclude_keywords[:5]) if profile.exclude_keywords else "None"
    summary = (opp.summary or "")[:1500]
    return f"""Score this RFP opportunity 0-100 for relevance. Reply with ONLY valid JSON:
{{"score": <0-100>, "match_reasons": ["..."], "risks": ["..."], "evidence": ["..."], "confidence": "high|medium|low"}}

Profile: keywords=[{kw}], categories=[{cats}], exclude=[{exc}]
Opportunity: title="{opp.title}"
Summary: {summary}

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
