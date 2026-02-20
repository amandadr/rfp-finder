"""User profile model for filtering and preferences."""

from decimal import Decimal
from pathlib import Path
from typing import Optional

try:
    import yaml
except ModuleNotFoundError as e:
    raise ModuleNotFoundError(
        "PyYAML is required for profile loading. Run: poetry install"
    ) from e
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
        """Load profile from YAML file. Supports nested (filters/eligibility) or flat structure."""
        data = yaml.safe_load(Path(path).read_text()) or {}
        flat: dict = {"profile_id": data.get("profile_id", "default")}
        filters = data.get("filters", {})
        elig = data.get("eligibility", {})

        def _get(key: str, nested: dict, top: dict, default=None):
            return nested.get(key, top.get(key, default))

        flat["keywords"] = _get("keywords", filters, data) or []
        flat["exclude_keywords"] = _get("exclude_keywords", filters, data) or []
        flat["preferred_categories"] = _get("preferred_categories", filters, data) or []
        raw_regions = _get("regions", filters, data) or _get("eligible_regions", filters, data) or []
        flat["eligible_regions"] = [str(r) for r in raw_regions]
        flat["exclude_regions"] = _get("exclude_regions", filters, data) or []
        flat["max_days_to_close"] = _get("max_days_to_close", filters, data)
        flat["min_budget"] = _get("min_budget", filters, data)
        flat["max_budget"] = _get("max_budget", filters, data)
        flat["citizenship_required"] = _get("citizenship_required", elig, data)
        flat["security_clearance"] = _get("security_clearance", elig, data)
        flat["local_vendor_only"] = _get("local_vendor_only", elig, data)
        return cls.model_validate(flat)
