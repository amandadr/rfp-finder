#!/usr/bin/env python3
"""Quick live test of Bids & Tenders bootstrap + POST flow.

Run:
  poetry run python scripts/test_bidsandtenders_live.py           # shared bids tenant
  poetry run python scripts/test_bidsandtenders_live.py halifax  # Halifax only
  poetry run python scripts/test_bidsandtenders_live.py all     # all tenants (slow)
"""

import sys

from rfp_finder.connectors.bidsandtenders import BidsTendersConnector


def main() -> None:
    tenant_arg = sys.argv[1] if len(sys.argv) > 1 else None
    if tenant_arg == "all":
        connector = BidsTendersConnector(tenants=["all"])
        print("Fetching from ALL tenants (this may take a while)...")
    elif tenant_arg:
        connector = BidsTendersConnector(tenant=tenant_arg)
        print(f"Fetching from tenant: {tenant_arg}...")
    else:
        connector = BidsTendersConnector()
        print("Fetching from default tenant (bids)...")

    raw_list = connector.search(filters={"limit": 5, "max_results": 5})
    print(f"Got {len(raw_list)} raw opportunities")
    for i, r in enumerate(raw_list[:5], 1):
        tenant = r.data.get("_tenant", "?")
        print(f"  {i}. [{tenant}] {r.data.get('title', 'N/A')} (id={r.data.get('id', 'N/A')})")
    if raw_list:
        print("\n✅ Bootstrap + POST flow succeeded.")
    else:
        print("\n⚠️ No data returned. Check logs for redirect/error.")


if __name__ == "__main__":
    main()
