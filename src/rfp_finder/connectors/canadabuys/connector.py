"""CanadaBuys connector using official open data CSV files."""

import csv
from datetime import datetime, timezone
from io import StringIO
from typing import Optional
from urllib.parse import urljoin

import httpx

from rfp_finder.connectors.base import BaseConnector
from rfp_finder.models.opportunity import NormalizedOpportunity
from rfp_finder.models.raw import RawOpportunity

from .constants import (
    AMENDMENT_DATE,
    ATTACHMENTS_ENG,
    CLOSING_DATE,
    CONTRACTING_ENTITY_ENG,
    DESCRIPTION_ENG,
    GSIN,
    NOTICE_URL_ENG,
    PROCUREMENT_CATEGORY,
    PUBLICATION_DATE,
    REFERENCE_NUMBER,
    REGIONS_DELIVERY_ENG,
    REGIONS_OPPORTUNITY_ENG,
    SOLICITATION_NUMBER,
    TENDER_STATUS_ENG,
    TITLE_ENG,
    TRADE_AGREEMENTS_ENG,
    UNSPSC,
)
from .parsers import content_hash, extract_attachments, parse_date, parse_trade_agreements


class CanadaBuysConnector(BaseConnector):
    """
    Connector for CanadaBuys tender notices.
    Fetches data from official open data CSV files.
    """

    source_id = "canadabuys"

    BASE_URL = "https://canadabuys.canada.ca"
    OPEN_TENDERS_CSV = "https://canadabuys.canada.ca/opendata/pub/openTenderNotice-ouvertAvisAppelOffres.csv"
    NEW_TENDERS_CSV = "https://canadabuys.canada.ca/opendata/pub/newTenderNotice-nouvelAvisAppelOffres.csv"

    DEFAULT_HEADERS = {
        "User-Agent": "rfp-finder/0.1 (Canadian RFP finder; compatible with Open Government Licence)",
        "Accept": "text/csv, text/plain, */*",
    }

    def __init__(self, client: Optional[httpx.Client] = None):
        self._client = client or httpx.Client(
            timeout=60.0,
            follow_redirects=True,
            headers=self.DEFAULT_HEADERS,
        )

    def _fetch_csv(self, url: str) -> str:
        """Fetch CSV content from URL."""
        response = self._client.get(url)
        response.raise_for_status()
        return response.text

    def _parse_csv_rows(self, csv_content: str) -> list[dict[str, str]]:
        """Parse CSV with proper handling of quoted multiline fields."""
        return list(csv.DictReader(StringIO(csv_content)))

    def search(
        self,
        query: Optional[str] = None,
        filters: Optional[dict] = None,
    ) -> list[RawOpportunity]:
        """
        Fetch opportunities from CanadaBuys.
        query: optional keyword filter (applied client-side to title/summary)
        filters: optional dict with 'source' key: 'open' | 'new' (default: 'open')
        """
        source = (filters or {}).get("source", "open")
        url = self.NEW_TENDERS_CSV if source == "new" else self.OPEN_TENDERS_CSV
        content = self._fetch_csv(url)
        rows = self._parse_csv_rows(content)
        raw_list = [RawOpportunity(data=dict(row)) for row in rows]

        if query:
            q = query.lower()
            raw_list = [
                r
                for r in raw_list
                if q in (r.data.get(TITLE_ENG) or "").lower()
                or q in (r.data.get(DESCRIPTION_ENG) or "").lower()
            ]
        return raw_list

    def fetch_details(self, raw_id: str) -> RawOpportunity:
        """
        Fetch one opportunity by reference number.
        CanadaBuys CSV has no per-item fetch; we search and filter.
        """
        for r in self.search(filters={"source": "open"}):
            ref = r.data.get(REFERENCE_NUMBER)
            if ref and ref.strip() == raw_id.strip():
                return r
        raise ValueError(f"Opportunity not found: {raw_id}")

    def _get_source_id(self, d: dict[str, str]) -> str:
        """Extract stable source ID from row."""
        ref = (d.get(REFERENCE_NUMBER) or "").strip()
        return ref or d.get(SOLICITATION_NUMBER) or "unknown"

    def _get_title(self, d: dict[str, str]) -> str:
        """Extract title with fallback."""
        return (d.get(TITLE_ENG) or "").strip() or "Untitled"

    def _get_url(self, d: dict[str, str]) -> Optional[str]:
        """Extract and normalize notice URL."""
        url = (d.get(NOTICE_URL_ENG) or "").strip() or None
        if url and not url.startswith("http"):
            url = urljoin(self.BASE_URL, url)
        return url

    def _get_categories(self, d: dict[str, str]) -> list[str]:
        """Extract procurement categories."""
        proc_cat = (d.get(PROCUREMENT_CATEGORY) or "").strip()
        if not proc_cat:
            return []
        return [c.strip() for c in proc_cat.replace("*", "").split() if c.strip()]

    def _get_commodity_codes(self, d: dict[str, str]) -> list[str]:
        """Extract commodity codes (GSIN, UNSPSC)."""
        codes: list[str] = []
        if gsin := (d.get(GSIN) or "").strip():
            codes.append(gsin)
        if unspsc := (d.get(UNSPSC) or "").strip():
            codes.append(unspsc.replace("*", ""))
        return codes

    def _get_status(self, d: dict[str, str], amended_at: Optional[datetime]) -> str:
        """Determine lifecycle status."""
        tend_status = (d.get(TENDER_STATUS_ENG) or "").strip().lower()
        if tend_status in ("cancelled", "expired"):
            return tend_status
        return "amended" if amended_at else "open"

    def normalize(self, raw: RawOpportunity) -> NormalizedOpportunity:
        """Convert CanadaBuys CSV row to NormalizedOpportunity."""
        d = raw.data
        source_id = self._get_source_id(d)
        opp_id = f"{self.source_id}:{source_id}"
        now = datetime.now(timezone.utc)

        published_at = parse_date(d.get(PUBLICATION_DATE))
        closing_at = parse_date(d.get(CLOSING_DATE))
        amended_at = parse_date(d.get(AMENDMENT_DATE))

        region = (d.get(REGIONS_OPPORTUNITY_ENG) or "").strip() or None
        regions_delivery = (d.get(REGIONS_DELIVERY_ENG) or "").strip()
        locations = [r.strip() for r in regions_delivery.split(",") if r.strip()] if regions_delivery else None

        return NormalizedOpportunity(
            id=opp_id,
            source=self.source_id,
            source_id=source_id,
            title=self._get_title(d),
            summary=(d.get(DESCRIPTION_ENG) or "").strip() or None,
            url=self._get_url(d),
            buyer=(d.get(CONTRACTING_ENTITY_ENG) or "").strip() or None,
            buyer_id=None,
            published_at=published_at,
            closing_at=closing_at,
            amended_at=amended_at,
            categories=self._get_categories(d),
            commodity_codes=self._get_commodity_codes(d),
            trade_agreements=parse_trade_agreements(d.get(TRADE_AGREEMENTS_ENG)),
            region=region,
            locations=locations,
            budget_min=None,
            budget_max=None,
            budget_currency=None,
            attachments=extract_attachments(d.get(ATTACHMENTS_ENG)),
            status=self._get_status(d, amended_at),
            first_seen_at=now,
            last_seen_at=now,
            content_hash=content_hash(raw),
        )

    def fetch_all(self) -> list[NormalizedOpportunity]:
        """Fetch all open tenders and return normalized list."""
        return [self.normalize(r) for r in self.search(filters={"source": "open"})]

    def fetch_incremental(self, since: Optional[datetime] = None) -> list[NormalizedOpportunity]:
        """
        Fetch new tenders only (uses new tenders CSV, smaller file).
        If since is provided, also filter by publication date.
        """
        normalized = [self.normalize(r) for r in self.search(filters={"source": "new"})]
        if since:
            normalized = [o for o in normalized if o.published_at and o.published_at >= since]
        return normalized
