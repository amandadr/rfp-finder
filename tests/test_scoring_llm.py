"""Tests for LLM scoring (stub and confidence)."""

import pytest

from rfp_finder.models.opportunity import NormalizedOpportunity
from rfp_finder.models.profile import UserProfile
from rfp_finder.scoring.llm import score_with_llm


def _make_opp(**kwargs) -> NormalizedOpportunity:
    defaults = {
        "id": "canadabuys:cb-1",
        "source": "canadabuys",
        "source_id": "cb-1",
        "title": "AI Software Project",
        "summary": "Development of AI-powered analytics platform.",
    }
    defaults.update(kwargs)
    return NormalizedOpportunity(**defaults)


def test_category_match_uses_structured_categories_only() -> None:
    """Category match checks opp.categories, not summary (avoids HR 'Information Technology' false positive)."""
    # Career transition tender with "Information Technology" in summary (as department name)
    opp = _make_opp(
        summary="Career transition support. Contact Information Technology, Human Resources.",
        categories=["SRV"],  # Services, not IT
    )
    profile = UserProfile(
        profile_id="t",
        preferred_categories=["Information Technology", "Software"],
    )
    result = score_with_llm(opp, profile)
    # Should NOT get +5 for "Information Technology" (it's in summary, not categories)
    assert "Category match" not in str(result.match_reasons)


def test_confidence_insufficient_text_when_attachments_not_extracted() -> None:
    """Confidence is insufficient_text when opp has attachments but no enriched_text."""
    from rfp_finder.models.opportunity import AttachmentRef

    opp = _make_opp(summary="Short")
    opp.attachments = [AttachmentRef(url="https://example.com/doc.pdf")]
    profile = UserProfile(profile_id="t")
    result = score_with_llm(opp, profile, enriched_text=None)
    assert result.confidence == "insufficient_text"


def test_confidence_medium_when_enriched() -> None:
    """Confidence is medium when enriched_text has attachment content."""
    opp = _make_opp(summary="Short")
    enriched = "[Main]\nShort\n\n---\n\n[Attachment: doc.pdf]\nLong extracted text from PDF. " * 50
    profile = UserProfile(profile_id="t")
    result = score_with_llm(opp, profile, enriched_text=enriched)
    assert result.confidence == "medium"
