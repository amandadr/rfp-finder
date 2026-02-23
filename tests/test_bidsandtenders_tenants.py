"""Tests for Bids & Tenders tenants."""

import re

import pytest

from rfp_finder.connectors.bidsandtenders.tenants import (
    TENANTS,
    base_url_for_tenant,
    get_tenant_subdomains,
)

# Subdomain must be lowercase alphanumeric, hyphens only (no spaces, dots)
SUBDOMAIN_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")
VALID_PROVINCES = frozenset({"NS", "NB", "NL", "PE", "ON", "SK", "BC", "AB", "MB", "NT", "YT", "QC"})


class TestEachTenant:
    """Per-tenant validation — every tenant must pass these tests."""

    @pytest.mark.parametrize("tenant_key", list(TENANTS.keys()), ids=lambda k: k)
    def test_tenant_has_valid_subdomain(self, tenant_key: str) -> None:
        """Each tenant subdomain is valid (lowercase alphanumeric/hyphen)."""
        ti = TENANTS[tenant_key]
        assert ti.subdomain, f"{tenant_key}: subdomain must be non-empty"
        assert SUBDOMAIN_PATTERN.match(ti.subdomain), (
            f"{tenant_key}: subdomain '{ti.subdomain}' must match [a-z0-9-]+"
        )

    @pytest.mark.parametrize("tenant_key", list(TENANTS.keys()), ids=lambda k: k)
    def test_tenant_has_non_empty_name(self, tenant_key: str) -> None:
        """Each tenant has a human-readable name."""
        ti = TENANTS[tenant_key]
        assert ti.name and ti.name.strip(), f"{tenant_key}: name must be non-empty"

    @pytest.mark.parametrize("tenant_key", list(TENANTS.keys()), ids=lambda k: k)
    def test_tenant_province_valid_if_present(self, tenant_key: str) -> None:
        """If province is set, it must be a valid two-letter code."""
        ti = TENANTS[tenant_key]
        if ti.province:
            assert len(ti.province) == 2, f"{tenant_key}: province must be 2 chars, got {ti.province}"
            assert ti.province.upper() in VALID_PROVINCES, (
                f"{tenant_key}: province '{ti.province}' not in known provinces"
            )

    @pytest.mark.parametrize("tenant_key", list(TENANTS.keys()), ids=lambda k: k)
    def test_get_tenant_subdomains_resolves_single_tenant(self, tenant_key: str) -> None:
        """get_tenant_subdomains(tenants=[key]) returns correct subdomain for each tenant."""
        subdomains = get_tenant_subdomains(tenants=[tenant_key])
        assert len(subdomains) == 1, f"{tenant_key}: should resolve to one subdomain"
        assert subdomains[0] == TENANTS[tenant_key].subdomain

    @pytest.mark.parametrize("tenant_key", list(TENANTS.keys()), ids=lambda k: k)
    def test_base_url_for_tenant_produces_valid_url(self, tenant_key: str) -> None:
        """base_url_for_tenant produces valid https URL for each subdomain."""
        subdomain = TENANTS[tenant_key].subdomain
        url = base_url_for_tenant(subdomain)
        assert url.startswith("https://"), f"{tenant_key}: URL must use https"
        assert f"{subdomain}.bidsandtenders.ca" in url
        assert " " not in url

    @pytest.mark.parametrize("tenant_key", list(TENANTS.keys()), ids=lambda k: k)
    def test_connector_instantiates_with_tenant(self, tenant_key: str) -> None:
        """BidsTendersConnector can be instantiated with each tenant (no network)."""
        from rfp_finder.connectors.bidsandtenders import BidsTendersConnector

        connector = BidsTendersConnector(tenant=tenant_key)
        assert connector._base_urls == [
            (TENANTS[tenant_key].subdomain, base_url_for_tenant(TENANTS[tenant_key].subdomain))
        ]


class TestGetTenantSubdomains:
    """Tests for get_tenant_subdomains."""

    def test_default_returns_bids_only(self) -> None:
        """Without args, returns shared bids tenant (backward compat)."""
        subdomains = get_tenant_subdomains()
        assert subdomains == ["bids"]

    def test_explicit_tenants(self) -> None:
        """Explicit tenants list returns those subdomains."""
        subdomains = get_tenant_subdomains(tenants=["halifax", "moncton"])
        assert subdomains == ["halifax", "moncton"]

    def test_all_returns_all_subdomains(self) -> None:
        """tenants=['all'] returns all known subdomains."""
        subdomains = get_tenant_subdomains(tenants=["all"])
        assert "bids" in subdomains
        assert "halifax" in subdomains
        assert "ae-ab" in subdomains

    def test_province_filter(self) -> None:
        """province filters to that province's tenants."""
        subdomains = get_tenant_subdomains(province="ON")
        assert "vaughan" in subdomains
        assert "mississauga" in subdomains
        assert "halifax" not in subdomains

    def test_tenant_key_resolution(self) -> None:
        """Tenant keys resolve to subdomains from TENANTS."""
        subdomains = get_tenant_subdomains(tenants=["ae-ab"])
        assert subdomains == ["ae-ab"]


class TestBaseUrlForTenant:
    """Tests for base_url_for_tenant."""

    def test_builds_url(self) -> None:
        """Base URL uses https and subdomain."""
        assert base_url_for_tenant("halifax") == "https://halifax.bidsandtenders.ca"
        assert base_url_for_tenant("ae-ab") == "https://ae-ab.bidsandtenders.ca"


class TestTenantsConfig:
    """Tests for TENANTS config."""

    def test_has_atlantic_tenants(self) -> None:
        """Atlantic tenants from plan are present."""
        assert "halifax" in TENANTS
        assert "moncton" in TENANTS
        assert "dieppe" in TENANTS
        assert "nlhydro" in TENANTS
        assert "princeedwardisland" in TENANTS

    def test_has_associated_engineering(self) -> None:
        """AE multi-province tenants present."""
        assert "ae-bc" in TENANTS
        assert "ae-ab" in TENANTS
        assert "ae-sk" in TENANTS
        assert "ae-mb" in TENANTS
