"""Parsing utilities for CanadaBuys CSV data."""

import hashlib
import json
import re
from datetime import datetime
from typing import Optional

from rfp_finder.models.opportunity import AttachmentRef
from rfp_finder.models.raw import RawOpportunity

from .constants import (
    AMENDMENT_DATE,
    ATTACHMENTS_ENG,
    CLOSING_DATE,
    DESCRIPTION_ENG,
    TITLE_ENG,
    TRADE_AGREEMENTS_ENG,
)

DATE_FORMATS = ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y/%m/%d")
URL_PATTERN = re.compile(r"https?://[^\s)\]\"']+", re.IGNORECASE)


def parse_date(value: Optional[str]) -> Optional[datetime]:
    """Parse date string from CanadaBuys format."""
    if not value or not value.strip():
        return None
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value[:19], fmt)
        except (ValueError, TypeError):
            continue
    return None


def extract_attachments(attachment_field: Optional[str]) -> list[AttachmentRef]:
    """
    Extract attachment refs from attachment field.
    Extracts http(s) URLs; sets application/pdf for .pdf URLs.
    """
    if not attachment_field:
        return []
    refs: list[AttachmentRef] = []
    seen: set[str] = set()
    for url in URL_PATTERN.findall(attachment_field):
        url = url.rstrip(".,;:")
        if url not in seen:
            seen.add(url)
            refs.append(
                AttachmentRef(
                    url=url,
                    label=None,
                    mime_type="application/pdf" if url.lower().endswith(".pdf") else None,
                    size_bytes=None,
                )
            )
    return refs


def parse_trade_agreements(value: Optional[str]) -> Optional[list[str]]:
    """Parse trade agreements from newline/asterisk-separated field."""
    if not value or not value.strip():
        return None
    items = [s.strip() for s in re.split(r"[\n*]+", value) if s.strip()]
    return items if items else None


def content_hash(raw: RawOpportunity) -> str:
    """Compute hash of key fields for change detection."""
    key_fields = (
        raw.data.get(TITLE_ENG),
        raw.data.get(DESCRIPTION_ENG),
        raw.data.get(CLOSING_DATE),
        raw.data.get(AMENDMENT_DATE),
        raw.data.get(ATTACHMENTS_ENG),
    )
    return hashlib.sha256(json.dumps(key_fields, sort_keys=True).encode()).hexdigest()
