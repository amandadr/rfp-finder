"""Parsing utilities for CanadaBuys CSV data."""

import hashlib
import json
import re
from datetime import datetime
from typing import Optional

from rfp_finder.models.opportunity import AttachmentRef
from rfp_finder.models.raw import RawOpportunity

# Region substring -> province/territory code (for display normalization)
_REGION_MAP: list[tuple[str, str]] = [
    ("alberta", "AB"),
    ("british columbia", "BC"),
    ("manitoba", "MB"),
    ("new brunswick", "NB"),
    ("moncton", "NB"),
    ("nova scotia", "NS"),
    ("ncr", "ON"),  # Before "national" so "*National Capital Region (NCR)" -> ON
    ("ontario", "ON"),
    ("ottawa", "ON"),
    ("quebec", "QC"),
    ("saskatchewan", "SK"),
    ("prince edward", "PE"),
    ("northwest territories", "NT"),
    ("nunavut", "NU"),
    ("yukon", "YT"),
    ("canada", "National"),
    ("national capital", "National"),  # "National Capital Region" without NCR match
    ("national", "National"),
    ("world", "National"),
    ("remote offsite", "National"),
    ("unspecified", "National"),
]


def normalize_region(region: Optional[str]) -> Optional[str]:
    """Map CanadaBuys region string to clean province code or National."""
    if not region or not region.strip():
        return None
    r = region.lower().strip().replace("*", "")
    for substr, code in _REGION_MAP:
        if substr in r:
            return code
    return r[:2].upper() if len(r) >= 2 else r.upper()


# Boilerplate prefixes to strip when deriving title from summary
_TITLE_SKIP_PREFIXES = (
    "NOTICE OF PROPOSED PROCUREMENT (NPP)",
    "NOTICE OF PROPOSED PROCUREMENT",
    "Solicitation Number:",
    "Organization Name:",
    "Reference Number:",
    "Tendering Procedure:",
    "This requirement is for:",
)

from .constants import (
    AMENDMENT_DATE,
    ATTACHMENTS_ENG,
    CLOSING_DATE,
    DESCRIPTION_ENG,
    TITLE_ENG,
    TRADE_AGREEMENTS_ENG,
)

DATE_FORMATS = ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y/%m/%d")
# Match a single URL; stop at comma, whitespace, or next "https://"
URL_PATTERN = re.compile(r"https?://[^\s,)\]\"']+", re.IGNORECASE)
# Split concatenated URLs: "url1,url2" or "url1, url2" or "url1https://url2"
URL_SEP = re.compile(r",\s*(?=https?://)", re.IGNORECASE)


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


def derive_title_from_summary(summary: Optional[str]) -> str:
    """
    Derive a usable title from summary when title field is empty/Untitled.
    Skips boilerplate paragraphs, takes first substantive one, truncates to ~100 chars.
    """
    if not summary or not summary.strip():
        return "Untitled"
    paragraphs = re.split(r"\r?\n\r?\n", summary.strip())
    for para in paragraphs:
        para = re.sub(r"&nbsp;", " ", para).strip()
        for prefix in _TITLE_SKIP_PREFIXES:
            if para.upper().startswith(prefix.upper()):
                para = para[len(prefix) :].strip().lstrip(":").strip()
                break
        if para and len(para) > 15:  # Skip short remnants
            if len(para) > 100:
                para = para[:97] + "..."
            return para
    return "Untitled"


def extract_attachments(attachment_field: Optional[str]) -> list[AttachmentRef]:
    """
    Extract attachment refs from attachment field.
    Handles: comma-separated "url1,url2", concatenated "url1https://url2", newlines.
    """
    if not attachment_field:
        return []
    refs: list[AttachmentRef] = []
    seen: set[str] = set()

    def add_url(url: str) -> None:
        url = url.rstrip(".,;:").strip()
        if url and url not in seen:
            seen.add(url)
            refs.append(
                AttachmentRef(
                    url=url,
                    label=None,
                    mime_type="application/pdf" if url.lower().endswith(".pdf") else None,
                    size_bytes=None,
                )
            )

    # Split by comma when followed by http (preserves commas in query params)
    for segment in URL_SEP.split(attachment_field):
        # Also split concatenated URLs without separator: "url1https://url2"
        subsegments = re.split(r"(?=https?://)", segment, flags=re.IGNORECASE)
        for sub in subsegments:
            for url in URL_PATTERN.findall(sub):
                add_url(url)
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
