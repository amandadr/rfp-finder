"""Bids & Tenders connector for Canadian municipal/provincial eProcurement.

bids&tenders (bidsandtenders.ca) is a digital eProcurement platform used by
municipalities, provinces, and organizations across Canada. The platform does
not expose a public API; this connector uses the same XHR flow as the web UI:

1. Bootstrap: GET listing page to obtain session cookies and CSRF token
2. Search: POST to /Module/Tenders/en/Tender/Search/{guid} with token
3. The search GUID is ephemeral and must be extracted from the listing HTML
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

from rfp_finder.connectors.base import BaseConnector
from rfp_finder.models.opportunity import NormalizedOpportunity
from rfp_finder.models.raw import RawOpportunity

from .parsers import extract_csrf_token, extract_search_guid, raw_from_search_item

logger = logging.getLogger(__name__)


class BidsTendersConnector(BaseConnector):
    """
    Connector for Bids & Tenders (bidsandtenders.ca).
    Uses bootstrap + POST flow to fetch tender listings via XHR JSON.
    """

    source_id = "bidsandtenders"

    DEFAULT_BASE_URL = "https://bids.bidsandtenders.ca"

    LISTING_PATH = "/module/tenders/en/"
    SEARCH_PATH_TEMPLATE = "/Module/Tenders/en/Tender/Search/{guid}"

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (compatible; rfp-finder/0.1; Canadian RFP finder)",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Accept-Language": "en-CA,en;q=0.9",
    }

    def __init__(
        self,
        base_url: Optional[str] = None,
        client: Optional[httpx.Client] = None,
    ):
        self._base_url = (
            base_url
            or os.environ.get("BIDS_TENDERS_BASE_URL")
            or self.DEFAULT_BASE_URL
        ).rstrip("/")
        self._client = client or httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers=self.DEFAULT_HEADERS,
        )

    def _bootstrap(self) -> tuple[str, str]:
        """
        Fetch listing page, extract CSRF token and search GUID.
        Returns (token, guid).
        """
        url = self._base_url + self.LISTING_PATH
        resp = self._client.get(url)
        resp.raise_for_status()
        html = resp.text

        token = extract_csrf_token(html)
        guid = extract_search_guid(html)
        if not guid:
            raise RuntimeError(
                "Could not find search GUID in listing page. "
                "The site may have changed its structure."
            )
        return token, guid

    def _post_search(
        self,
        token: str,
        guid: str,
        *,
        status: str = "Open",
        limit: int = 25,
        start: int = 0,
    ) -> dict:
        """POST search request with CSRF token."""
        url = self._base_url + self.SEARCH_PATH_TEMPLATE.format(guid=guid)
        params = {
            "status": status,
            "limit": limit,
            "start": start,
            "dir": "ASC",
            "from": "",
            "to": "",
            "sort": "DateClosing ASC,Id",
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": self._base_url,
            "Referer": self._base_url + "/",
        }
        data = {"__RequestVerificationToken": token}

        resp = self._client.post(url, params=params, data=data, headers=headers)
        resp.raise_for_status()

        # Expect JSON; redirect to Error page returns HTML
        content_type = resp.headers.get("content-type", "")
        if "application/json" not in content_type and "javascript" not in content_type:
            logger.warning(
                "Search returned non-JSON (content-type=%s). "
                "Possible redirect to error page.",
                content_type,
            )
            raise ValueError(
                "Search endpoint returned HTML instead of JSON. "
                "Bootstrap may have failed or GUID is invalid."
            )

        return resp.json()

    def search(
        self,
        query: Optional[str] = None,
        filters: Optional[dict] = None,
    ) -> list[RawOpportunity]:
        """
        Search opportunities via bootstrap + POST flow.
        Supports pagination by fetching all pages when limit/start not specified.
        """
        token, guid = self._bootstrap()

        status = (filters or {}).get("status", "Open")
        limit = (filters or {}).get("limit", 25)
        max_results = (filters or {}).get("max_results")  # None = fetch all

        all_raw: list[RawOpportunity] = []
        start = 0
        total_seen = 0

        while True:
            payload = self._post_search(
                token, guid,
                status=status,
                limit=limit,
                start=start,
            )

            if not payload.get("success"):
                logger.warning("Search returned success=false: %s", payload)
                break

            data_list = payload.get("data") or []
            total = payload.get("total", 0)

            for item in data_list:
                raw_data = raw_from_search_item(item)
                # Build detail URL when API doesn't provide it
                if not raw_data.get("url") and raw_data.get("id"):
                    raw_data["url"] = (
                        f"{self._base_url}/Module/Tenders/en/Tender/Detail/{raw_data['id']}"
                    )
                all_raw.append(RawOpportunity(data=raw_data))

            total_seen += len(data_list)
            if not data_list or total_seen >= total:
                break
            start += limit
            if max_results is not None and total_seen >= max_results:
                break

        if query:
            q = query.lower()
            all_raw = [
                r
                for r in all_raw
                if q in (r.data.get("title") or "").lower()
                or q in (r.data.get("description") or "").lower()
                or q in (r.data.get("reference_number") or "").lower()
            ]

        return all_raw

    def fetch_details(self, raw_id: str) -> RawOpportunity:
        """
        Fetch one opportunity by ID.
        Bids & Tenders search returns list data; we search and filter by ID.
        """
        for r in self.search():
            sid = r.data.get("id") or r.data.get("reference_number")
            if sid and str(sid).strip() == str(raw_id).strip():
                return r
        raise ValueError(f"Opportunity not found: {raw_id}")

    def normalize(self, raw: RawOpportunity) -> NormalizedOpportunity:
        """Convert raw record to NormalizedOpportunity."""
        d = raw.data
        source_id = (d.get("id") or d.get("reference_number") or "unknown").strip()
        opp_id = f"{self.source_id}:{source_id}"
        now = datetime.now(timezone.utc)

        return NormalizedOpportunity(
            id=opp_id,
            source=self.source_id,
            source_id=source_id,
            title=(d.get("title") or "").strip() or "Untitled",
            summary=(d.get("description") or d.get("summary") or "").strip() or None,
            url=(d.get("url") or "").strip() or None,
            buyer=(d.get("buyer") or d.get("contracting_entity") or "").strip() or None,
            buyer_id=None,
            published_at=None,
            closing_at=None,
            amended_at=None,
            categories=[],
            commodity_codes=[],
            trade_agreements=None,
            region=None,
            locations=None,
            budget_min=None,
            budget_max=None,
            budget_currency=None,
            attachments=[],
            status="open",
            first_seen_at=now,
            last_seen_at=now,
            content_hash=None,
        )

    def fetch_all(self) -> list[NormalizedOpportunity]:
        """Fetch all open opportunities and return normalized list."""
        return [self.normalize(r) for r in self.search()]

    def fetch_incremental(self, since: Optional[datetime] = None) -> list[NormalizedOpportunity]:
        """Fetch opportunities; filter by since if provided (client-side)."""
        all_opps = self.fetch_all()
        if since is None:
            return all_opps
        return [o for o in all_opps if o.published_at and o.published_at >= since]
