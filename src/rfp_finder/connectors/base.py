"""Abstract base class for source connectors."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from rfp_finder.models.opportunity import NormalizedOpportunity
from rfp_finder.models.raw import RawOpportunity


class BaseConnector(ABC):
    """
    Standard interface for RFP source connectors.
    All connectors must implement search/list, fetch details, and normalize.
    """

    source_id: str = ""

    @abstractmethod
    def search(self, query: Optional[str] = None, filters: Optional[dict] = None) -> list[RawOpportunity]:
        """
        List or search opportunities; returns raw format from source.
        """
        pass

    @abstractmethod
    def fetch_details(self, raw_id: str) -> RawOpportunity:
        """
        Fetch full details for one opportunity by its source-native ID.
        """
        pass

    @abstractmethod
    def normalize(self, raw: RawOpportunity) -> NormalizedOpportunity:
        """
        Convert raw record to NormalizedOpportunity.
        """
        pass

    def fetch_all(self) -> list[NormalizedOpportunity]:
        """
        Fetch all opportunities and return normalized list.
        Default implementation: search (no filters), then normalize each.
        Override for sources that support bulk normalized fetch (e.g. CSV).
        """
        raw_list = self.search()
        return [self.normalize(r) for r in raw_list]

    def fetch_incremental(self, since: Optional[datetime] = None) -> list[NormalizedOpportunity]:
        """
        Fetch only new/changed opportunities since a given datetime.
        Override for sources with incremental APIs (e.g. RSS, new-tenders CSV).
        Default: fetch all and filter by since (client-side).
        """
        all_opps = self.fetch_all()
        if since is None:
            return all_opps
        return [o for o in all_opps if o.published_at and o.published_at >= since]
