"""User profile model for filtering and preferences."""

from decimal import Decimal
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """User profile with filters and eligibility constraints."""

    profile_id: str = Field(..., description="Unique identifier")

    keywords: list[str] = Field(default_factory=list, description="Must-have terms")
    exclude_keywords: list[str] = Field(default_factory=list, description="Deal-breakers")
    preferred_categories: list[str] = Field(default_factory=list)

    eligible_regions: list[str] = Field(
        default_factory=list,
        description="e.g. ['ON', 'National']",
    )
    exclude_regions: list[str] = Field(default_factory=list)

    citizenship_required: Optional[str] = None  # "canadian" | "none"
    security_clearance: Optional[str] = None  # "secret" | "reliability"
    local_vendor_only: Optional[bool] = None

    min_budget: Optional[Decimal] = None
    max_budget: Optional[Decimal] = None
    max_days_to_close: Optional[int] = Field(
        default=None,
        description="Only include if closing >= N days out",
    )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "UserProfile":
        """Load profile from YAML file."""
        data = yaml.safe_load(Path(path).read_text())
        flat: dict = {"profile_id": data.get("profile_id", "default")}
        filters = data.get("filters", {})
        elig = data.get("eligibility", {})
        flat["keywords"] = filters.get("keywords", [])
        flat["exclude_keywords"] = filters.get("exclude_keywords", [])
        flat["preferred_categories"] = filters.get("preferred_categories", [])
        raw_regions = filters.get("regions", [])
        flat["eligible_regions"] = [str(r) for r in raw_regions]  # YAML may parse ON as bool
        flat["exclude_regions"] = filters.get("exclude_regions", [])
        flat["max_days_to_close"] = filters.get("max_days_to_close")
        flat["min_budget"] = filters.get("min_budget")
        flat["max_budget"] = filters.get("max_budget")
        flat["citizenship_required"] = elig.get("citizenship_required")
        flat["security_clearance"] = elig.get("security_clearance")
        flat["local_vendor_only"] = elig.get("local_vendor_only")
        return cls.model_validate(flat)
