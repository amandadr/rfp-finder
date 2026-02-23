#!/usr/bin/env python3
"""Quick live test of Bids & Tenders bootstrap + POST flow.

Run: poetry run python scripts/test_bidsandtenders_live.py

Expected: JSON with success=true, data=[...], total=N
If you get HTML redirect to /Error, the GUID may be ephemeral or bootstrap failed.
"""

from rfp_finder.connectors.bidsandtenders import BidsTendersConnector


def main() -> None:
    connector = BidsTendersConnector()
    print("Fetching tenders via bootstrap + POST...")
    raw_list = connector.search(filters={"limit": 5, "max_results": 5})
    print(f"Got {len(raw_list)} raw opportunities")
    for i, r in enumerate(raw_list[:3], 1):
        print(f"  {i}. {r.data.get('title', 'N/A')} (id={r.data.get('id', 'N/A')})")
    if raw_list:
        print("\n✅ Bootstrap + POST flow succeeded.")
    else:
        print("\n⚠️ No data returned. Check logs for redirect/error.")


if __name__ == "__main__":
    main()
