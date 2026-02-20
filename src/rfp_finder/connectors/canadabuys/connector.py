"""CanadaBuys connector using official open data CSV files."""

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from io import StringIO
from typing import Optional
from urllib.parse import urljoin

import httpx

from rfp_finder.connectors.base import BaseConnector
from rfp_finder.models.opportunity import AttachmentRef, NormalizedOpportunity
from rfp_finder.models.raw import RawOpportunity


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
        reader = csv.DictReader(StringIO(csv_content))
        return list(reader)

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
        url = (
            self.NEW_TENDERS_CSV
            if source == "new"
            else self.OPEN_TENDERS_CSV
        )
        content = self._fetch_csv(url)
        rows = self._parse_csv_rows(content)
        raw_list = [RawOpportunity(data=dict(row)) for row in rows]

        if query:
            q = query.lower()
            raw_list = [
                r
                for r in raw_list
                if q in (r.data.get("title-titre-eng") or "").lower()
                or q in (r.data.get("tenderDescription-descriptionAppelOffres-eng") or "").lower()
            ]
        return raw_list

    def fetch_details(self, raw_id: str) -> RawOpportunity:
        """
        Fetch one opportunity by reference number.
        CanadaBuys CSV has no per-item fetch; we search and filter.
        """
        raw_list = self.search(filters={"source": "open"})
        for r in raw_list:
            ref = r.data.get("referenceNumber-numeroReference")
            if ref and ref.strip() == raw_id.strip():
                return r
        raise ValueError(f"Opportunity not found: {raw_id}")

    def _parse_date(self, value: Optional[str]) -> Optional[datetime]:
        """Parse date string from CanadaBuys format."""
        if not value or not value.strip():
            return None
        value = value.strip()
        for fmt in (
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d",
        ):
            try:
                return datetime.strptime(value[:19], fmt)  # type: ignore
            except (ValueError, TypeError):
                continue
        return None

    def _extract_attachments(self, attachment_field: Optional[str], notice_url: Optional[str]) -> list[AttachmentRef]:
        """
        Extract attachment refs from attachment field and notice URL.
        CanadaBuys may list URLs or labels; we extract http(s) URLs.
        """
        refs: list[AttachmentRef] = []
        if not attachment_field:
            return refs

        url_pattern = re.compile(
            r"https?://[^\s)\]\"']+",
            re.IGNORECASE,
        )
        urls = url_pattern.findall(attachment_field)
        seen = set()
        for u in urls:
            u = u.rstrip(".,;:")
            if u not in seen:
                seen.add(u)
                refs.append(
                    AttachmentRef(
                        url=u,
                        label=None,
                        mime_type="application/pdf" if u.lower().endswith(".pdf") else None,
                        size_bytes=None,
                    )
                )
        return refs

    def _parse_trade_agreements(self, value: Optional[str]) -> Optional[list[str]]:
        """Parse trade agreements from newline/asterisk-separated field."""
        if not value or not value.strip():
            return None
        items = [
            s.strip()
            for s in re.split(r"[\n*]+", value)
            if s.strip()
        ]
        return items if items else None

    def _content_hash(self, raw: RawOpportunity) -> str:
        """Compute hash of key fields for change detection."""
        key_fields = (
            raw.data.get("title-titre-eng"),
            raw.data.get("tenderDescription-descriptionAppelOffres-eng"),
            raw.data.get("tenderClosingDate-appelOffresDateCloture"),
            raw.data.get("amendmentDate-dateModification"),
            raw.data.get("attachment-piecesJointes-eng"),
        )
        payload = json.dumps(key_fields, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def normalize(self, raw: RawOpportunity) -> NormalizedOpportunity:
        """Convert CanadaBuys CSV row to NormalizedOpportunity."""
        d = raw.data
        ref_num = (d.get("referenceNumber-numeroReference") or "").strip()
        if not ref_num:
            ref_num = d.get("solicitationNumber-numeroSollicitation") or "unknown"
        source_id = ref_num
        opp_id = f"{self.source_id}:{source_id}"

        title = (d.get("title-titre-eng") or "").strip() or "Untitled"
        summary = (d.get("tenderDescription-descriptionAppelOffres-eng") or "").strip() or None
        notice_url = (d.get("noticeURL-URLavis-eng") or "").strip() or None
        if notice_url and not notice_url.startswith("http"):
            notice_url = urljoin(self.BASE_URL, notice_url)

        buyer = (d.get("contractingEntityName-nomEntitContractante-eng") or "").strip() or None

        published_at = self._parse_date(d.get("publicationDate-datePublication"))
        closing_at = self._parse_date(d.get("tenderClosingDate-appelOffresDateCloture"))
        amended_at = self._parse_date(d.get("amendmentDate-dateModification"))

        categories: list[str] = []
        proc_cat = (d.get("procurementCategory-categorieApprovisionnement") or "").strip()
        if proc_cat:
            categories = [c.strip() for c in proc_cat.replace("*", "").split() if c.strip()]

        commodity_codes: list[str] = []
        gsin = (d.get("gsin-nibs") or "").strip()
        unspsc = (d.get("unspsc") or "").strip()
        if gsin:
            commodity_codes.append(gsin)
        if unspsc:
            commodity_codes.append(unspsc.replace("*", ""))

        trade_agreements = self._parse_trade_agreements(d.get("tradeAgreements-accordsCommerciaux-eng"))

        region = (d.get("regionsOfOpportunity-regionAppelOffres-eng") or "").strip() or None
        regions_delivery = (d.get("regionsOfDelivery-regionsLivraison-eng") or "").strip()
        locations = [r.strip() for r in regions_delivery.split(",") if r.strip()] if regions_delivery else None

        attachments = self._extract_attachments(
            d.get("attachment-piecesJointes-eng"),
            notice_url,
        )

        status = "open"
        tend_status = (d.get("tenderStatus-appelOffresStatut-eng") or "").strip().lower()
        if tend_status in ("cancelled", "expired"):
            status = tend_status
        elif amended_at:
            status = "amended"

        now = datetime.now(timezone.utc)
        content_hash = self._content_hash(raw)

        return NormalizedOpportunity(
            id=opp_id,
            source=self.source_id,
            source_id=source_id,
            title=title,
            summary=summary,
            url=notice_url,
            buyer=buyer,
            buyer_id=None,
            published_at=published_at,
            closing_at=closing_at,
            amended_at=amended_at,
            categories=categories,
            commodity_codes=commodity_codes,
            trade_agreements=trade_agreements,
            region=region,
            locations=locations,
            budget_min=None,
            budget_max=None,
            budget_currency=None,
            attachments=attachments,
            status=status,
            first_seen_at=now,
            last_seen_at=now,
            content_hash=content_hash,
        )

    def fetch_all(self) -> list[NormalizedOpportunity]:
        """Fetch all open tenders and return normalized list."""
        raw_list = self.search(filters={"source": "open"})
        return [self.normalize(r) for r in raw_list]

    def fetch_incremental(self, since: Optional[datetime] = None) -> list[NormalizedOpportunity]:
        """
        Fetch new tenders only (uses new tenders CSV, smaller file).
        If since is provided, also filter by publication date.
        """
        raw_list = self.search(filters={"source": "new"})
        normalized = [self.normalize(r) for r in raw_list]
        if since:
            normalized = [
                o for o in normalized
                if o.published_at and o.published_at >= since
            ]
        return normalized
