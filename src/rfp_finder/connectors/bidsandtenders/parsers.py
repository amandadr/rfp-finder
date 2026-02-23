"""Parsers for Bids & Tenders HTML and JSON responses."""

import re
from typing import Optional


def extract_csrf_token(html: str) -> str:
    """
    Extract __RequestVerificationToken from listing page HTML.
    ASP.NET MVC uses this for CSRF protection.
    """
    # Prefer regex for minimal dependency; markup may vary
    m = re.search(
        r'name="__RequestVerificationToken"[^>]*value="([^"]+)"',
        html,
        re.IGNORECASE,
    )
    if m:
        return m.group(1)
    # Alternate: value before name
    m = re.search(
        r'value="([^"]+)"[^>]*name="__RequestVerificationToken"',
        html,
        re.IGNORECASE,
    )
    if m:
        return m.group(1)
    raise RuntimeError(
        "Could not find __RequestVerificationToken in listing page HTML."
    )


def extract_search_guid(html: str) -> Optional[str]:
    """
    Extract the ephemeral search context GUID (NodeId) from listing page HTML.
    The site uses id="NodeId" value="{guid}" for the Search endpoint.
    Fallback: look for /Tender/Search/{guid} in URLs.
    """
    # Primary: NodeId hidden input (used by index.js)
    m = re.search(
        r'id="NodeId"[^>]*value="([0-9a-fA-F-]{36})"',
        html,
        re.IGNORECASE,
    )
    if m:
        return m.group(1)
    m = re.search(
        r'value="([0-9a-fA-F-]{36})"[^>]*id="NodeId"',
        html,
        re.IGNORECASE,
    )
    if m:
        return m.group(1)
    # Fallback: /Tender/Search/{guid} in URLs
    m = re.search(
        r"/Tender/Search/([0-9a-fA-F-]{36})",
        html,
    )
    return m.group(1) if m else None


def raw_from_search_item(item: dict) -> dict:
    """
    Map a single item from the Search JSON response to our raw data shape.
    Field names may vary; use flexible lookups.
    """
    # Common ASP.NET/JS naming patterns
    raw: dict = {}
    raw["id"] = (
        item.get("Id")
        or item.get("id")
        or item.get("ReferenceNumber")
        or item.get("reference_number")
        or ""
    )
    raw["title"] = (
        item.get("Title")
        or item.get("title")
        or item.get("Name")
        or item.get("name")
        or ""
    )
    raw["description"] = (
        item.get("Description")
        or item.get("description")
        or item.get("Summary")
        or item.get("summary")
        or ""
    )
    raw["buyer"] = (
        item.get("Organization")
        or item.get("organization")
        or item.get("Buyer")
        or item.get("buyer")
        or item.get("ContractingEntity")
        or item.get("contracting_entity")
        or ""
    )
    raw["url"] = (
        item.get("Url")
        or item.get("url")
        or item.get("Link")
        or item.get("link")
        or ""
    )
    raw["reference_number"] = (
        item.get("ReferenceNumber")
        or item.get("reference_number")
        or raw.get("id")
        or ""
    )
    raw["date_closing"] = (
        item.get("DateClosing")
        or item.get("date_closing")
        or item.get("ClosingDate")
        or item.get("closing_date")
    )
    raw["date_published"] = (
        item.get("DatePublished")
        or item.get("date_published")
        or item.get("PublicationDate")
        or item.get("publication_date")
    )
    # Preserve full item for debugging and future field mapping
    raw["_raw"] = item
    return raw
