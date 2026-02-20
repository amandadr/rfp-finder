"""Data models for normalized opportunities and attachments."""

from rfp_finder.models.opportunity import AttachmentRef, NormalizedOpportunity
from rfp_finder.models.raw import RawOpportunity

__all__ = ["AttachmentRef", "NormalizedOpportunity", "RawOpportunity"]
