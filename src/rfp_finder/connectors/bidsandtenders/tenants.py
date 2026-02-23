"""Bids & Tenders tenant configuration.

Each tenant uses a subdomain: https://{subdomain}.bidsandtenders.ca/
Bootstrap: /module/tenders/en/
Search: /Module/Tenders/en/Tender/Search/{GUID}
Detail: /Module/Tenders/en/Tender/Detail/{TENDER_ID}

Sources: web research, bidsandtenders.com supplier pages, municipality procurement sites.
List is extensible — add tenants as discovered.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TenantInfo:
    """Metadata for a Bids & Tenders tenant."""

    subdomain: str
    name: str
    province: Optional[str] = None  # Two-letter province code
    region: Optional[str] = None  # Human-readable region


# fmt: off
TENANTS: dict[str, TenantInfo] = {
    # Shared / catch-all
    "bids": TenantInfo("bids", "BidsAndTenders (shared)", region="National"),

    # Atlantic — Nova Scotia
    "halifax": TenantInfo("halifax", "Halifax Regional Municipality", province="NS"),
    # Atlantic — New Brunswick
    "moncton": TenantInfo("moncton", "City of Moncton", province="NB"),
    "dieppe": TenantInfo("dieppe", "City of Dieppe", province="NB"),
    # Atlantic — Newfoundland & Labrador
    "nlhydro": TenantInfo("nlhydro", "NL Hydro", province="NL"),
    # Atlantic — Prince Edward Island
    "princeedwardisland": TenantInfo("princeedwardisland", "Prince Edward Island", province="PE"),

    # Ontario — municipalities
    "vaughan": TenantInfo("vaughan", "City of Vaughan", province="ON"),
    "mississauga": TenantInfo("mississauga", "City of Mississauga", province="ON"),
    "guelph": TenantInfo("guelph", "City of Guelph", province="ON"),
    "belleville": TenantInfo("belleville", "City of Belleville", province="ON"),
    "burlington": TenantInfo("burlington", "City of Burlington", province="ON"),
    "owensound": TenantInfo("owensound", "City of Owen Sound", province="ON"),
    "kitchener": TenantInfo("kitchener", "City of Kitchener", province="ON"),
    "london": TenantInfo("london", "City of London", province="ON"),
    "whitby": TenantInfo("whitby", "Town of Whitby", province="ON"),
    "regionofwaterloo": TenantInfo("regionofwaterloo", "Region of Waterloo", province="ON"),

    # Saskatchewan
    "saskatoon": TenantInfo("saskatoon", "City of Saskatoon", province="SK"),
    "regina": TenantInfo("regina", "City of Regina", province="SK"),

    # British Columbia
    "burnaby": TenantInfo("burnaby", "City of Burnaby", province="BC"),
    "metrovancouver": TenantInfo("metrovancouver", "Metro Vancouver", province="BC"),
    "astsbc": TenantInfo("astsbc", "ASTSBC", province="BC"),
    "interiorpurchasing": TenantInfo("interiorpurchasing", "Interior Purchasing Office", province="BC"),

    # Associated Engineering (multi-province)
    "ae-bc": TenantInfo("ae-bc", "Associated Engineering (BC, YK, NWT)", province="BC"),
    "ae-ab": TenantInfo("ae-ab", "Associated Engineering - Alberta", province="AB"),
    "ae-sk": TenantInfo("ae-sk", "Associated Engineering - Saskatchewan", province="SK"),
    "ae-mb": TenantInfo("ae-mb", "Associated Engineering - Manitoba", province="MB"),

    # Manitoba
    "mwsb": TenantInfo("mwsb", "Manitoba Water Services Board", province="MB"),

    # Multi-tenant / aggregate portals
    "bidcentral": TenantInfo("bidcentral", "Bid Central", region="National"),
}
# fmt: on


def get_tenant_subdomains(
    tenants: Optional[list[str]] = None,
    province: Optional[str] = None,
    default_all: bool = False,
) -> list[str]:
    """
    Return subdomains to query.

    Args:
        tenants: Explicit tenant keys (subdomain or key). If None, use province or all.
        province: Filter by two-letter province code (e.g. ON, BC).
        default_all: If True and no tenants/province, return all. Else default to ["bids"].
    """
    if tenants:
        if "all" in tenants or "*" in [t.strip().lower() for t in tenants]:
            return [ti.subdomain for ti in TENANTS.values()]
        subdomains: list[str] = []
        for t in tenants:
            key = t.lower().replace("_", "-").strip()
            if key in TENANTS:
                subdomains.append(TENANTS[key].subdomain)
            else:
                subdomains.append(key)
        return subdomains

    if province:
        prov = province.upper()
        return [ti.subdomain for ti in TENANTS.values() if ti.province == prov]

    if default_all:
        return [ti.subdomain for ti in TENANTS.values()]
    return ["bids"]  # Backward compat: shared tenant only


def base_url_for_tenant(subdomain: str) -> str:
    """Build full base URL for a tenant subdomain."""
    return f"https://{subdomain}.bidsandtenders.ca"
