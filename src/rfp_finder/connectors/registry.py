"""Registry for discovering and instantiating connectors."""

from typing import Type

from rfp_finder.connectors.base import BaseConnector
from rfp_finder.connectors.bidsandtenders import BidsTendersConnector
from rfp_finder.connectors.canadabuys import CanadaBuysConnector


class ConnectorRegistry:
    """Discovers and provides source connectors."""

    _connectors: dict[str, Type[BaseConnector]] = {
        "canadabuys": CanadaBuysConnector,
        "bidsandtenders": BidsTendersConnector,
    }

    @classmethod
    def get(cls, source_id: str, **kwargs) -> BaseConnector:
        """Get a connector instance for the given source. kwargs passed to connector __init__."""
        connector_cls = cls._connectors.get(source_id.lower())
        if not connector_cls:
            raise ValueError(f"Unknown source: {source_id}. Available: {list(cls._connectors.keys())}")
        return connector_cls(**kwargs)

    @classmethod
    def available_sources(cls) -> list[str]:
        """Return list of available source identifiers."""
        return list(cls._connectors.keys())
