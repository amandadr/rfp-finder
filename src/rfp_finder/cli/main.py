"""Main CLI entry point."""

import argparse
import json
from datetime import datetime
from pathlib import Path


def main() -> None:
    """Parse args and dispatch to subcommands."""
    parser = argparse.ArgumentParser(prog="rfp-finder", description="Canadian AI-driven RFP finder")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ingest
    ingest_parser = subparsers.add_parser("ingest", help="Ingest opportunities from a source")
    ingest_parser.add_argument(
        "--source",
        default="canadabuys",
        choices=["canadabuys"],
        help="Source to ingest from",
    )
    ingest_parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="Only fetch items published on/after this date (YYYY-MM-DD). Uses new tenders feed when possible.",
    )
    ingest_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write normalized JSON to file (default: stdout)",
    )
    ingest_parser.add_argument(
        "--incremental",
        action="store_true",
        help="Use incremental fetch (new tenders feed)",
    )

    args = parser.parse_args()

    if args.command == "ingest":
        _run_ingest(args)
    else:
        parser.print_help()


def _run_ingest(args: argparse.Namespace) -> None:
    """Run ingest command."""
    from rfp_finder.connectors.registry import ConnectorRegistry

    connector = ConnectorRegistry.get(args.source)
    since_dt = None
    if args.since:
        try:
            since_dt = datetime.strptime(args.since, "%Y-%m-%d")
        except ValueError:
            raise SystemExit(f"Invalid --since format. Use YYYY-MM-DD.")

    if args.incremental or since_dt:
        opportunities = connector.fetch_incremental(since=since_dt)
    else:
        opportunities = connector.fetch_all()

    output = json.dumps(
        [o.model_dump(mode="json") for o in opportunities],
        indent=2,
        default=str,
    )

    if args.output:
        args.output.write_text(output, encoding="utf-8")
        print(f"Wrote {len(opportunities)} opportunities to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
