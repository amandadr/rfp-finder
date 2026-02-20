"""Raw opportunity representation before normalization."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RawOpportunity(BaseModel):
    """
    Flexible raw record from a source connector.
    Connectors populate this from CSV rows, API responses, etc.
    """

    model_config = ConfigDict(extra="allow")

    data: dict[str, Any] = Field(default_factory=dict)
