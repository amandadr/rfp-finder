"""Normalized opportunity and attachment models."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class AttachmentRef(BaseModel):
    """Reference to an attachment (document) linked from an opportunity."""

    url: str
    label: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None


class NormalizedOpportunity(BaseModel):
    """Canonical opportunity record produced by all source connectors."""

    id: str = Field(..., description="Deterministic ID: {source}:{source_id}")
    source: str = Field(..., description="Source identifier, e.g. 'canadabuys'")
    source_id: str = Field(..., description="Native tender/notice ID")

    title: str = ""
    summary: Optional[str] = None
    url: Optional[str] = None

    buyer: Optional[str] = None
    buyer_id: Optional[str] = None

    published_at: Optional[datetime] = None
    closing_at: Optional[datetime] = None
    amended_at: Optional[datetime] = None

    categories: list[str] = Field(default_factory=list)
    commodity_codes: list[str] = Field(default_factory=list)
    trade_agreements: Optional[list[str]] = None

    region: Optional[str] = None
    locations: Optional[list[str]] = None

    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    budget_currency: Optional[str] = None

    attachments: list[AttachmentRef] = Field(default_factory=list)

    status: str = "open"
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content_hash: Optional[str] = None
