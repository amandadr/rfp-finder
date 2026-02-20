"""Local storage for opportunities and run history."""

from rfp_finder.store.sqlite_store import OpportunityStore, RunRecord

__all__ = ["OpportunityStore", "RunRecord"]
