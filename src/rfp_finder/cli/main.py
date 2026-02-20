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
    ingest_parser.add_argument(
        "--store",
        type=Path,
        default=None,
        metavar="DB_PATH",
        help="Persist to SQLite store at given path (e.g. rfp_finder.db)",
    )

    # store
    store_parser = subparsers.add_parser("store", help="Query the opportunity store")
    store_parser.add_argument(
        "--db",
        type=Path,
        default=Path("rfp_finder.db"),
        help="Path to SQLite database",
    )
    store_parser.add_argument(
        "action",
        choices=["list", "count"],
        help="List opportunities or show count",
    )
    store_parser.add_argument(
        "--status",
        type=str,
        default=None,
        help="Filter by status (open, closed, amended)",
    )

    # filter
    filter_parser = subparsers.add_parser("filter", help="Filter opportunities by profile")
    filter_parser.add_argument(
        "--profile",
        type=Path,
        required=True,
        help="Path to profile YAML",
    )
    filter_parser.add_argument(
        "--db",
        type=Path,
        default=Path("rfp_finder.db"),
        help="Read opportunities from store",
    )
    filter_parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Read opportunities from JSON file (alternative to --db)",
    )
    filter_parser.add_argument(
        "--status",
        type=str,
        default="open",
        help="Store status filter when using --db (default: open)",
    )
    filter_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write filtered results to file",
    )
    filter_parser.add_argument(
        "--show-explanations",
        action="store_true",
        help="Include filter explanations in output",
    )

    args = parser.parse_args()

    if args.command == "ingest":
        _run_ingest(args)
    elif args.command == "store":
        _run_store(args)
    elif args.command == "filter":
        _run_filter(args)
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
            raise SystemExit("Invalid --since format. Use YYYY-MM-DD.")

    if args.incremental or since_dt:
        opportunities = connector.fetch_incremental(since=since_dt)
    else:
        opportunities = connector.fetch_all()

    store = None
    run_record = None
    if args.store is not None:
        from rfp_finder.store import OpportunityStore

        store = OpportunityStore(args.store)
        run_record = store.start_run(args.source)

    items_new = 0
    items_amended = 0
    if store and run_record:
        for opp in opportunities:
            was_new, was_amended = store.upsert(opp)
            if was_new:
                items_new += 1
            if was_amended:
                items_amended += 1
        store.finish_run(
            run_record.id,
            items_fetched=len(opportunities),
            items_new=items_new,
            items_amended=items_amended,
        )
        print(f"Store: {len(opportunities)} fetched, {items_new} new, {items_amended} amended")

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


def _run_store(args: argparse.Namespace) -> None:
    """Run store command."""
    from rfp_finder.store import OpportunityStore

    store = OpportunityStore(args.db)
    if args.action == "list":
        opps = store.get_by_status(args.status) if args.status else store.get_all()
        output = json.dumps(
            [o.model_dump(mode="json") for o in opps],
            indent=2,
            default=str,
        )
        print(output)
    elif args.action == "count":
        opps = store.get_by_status(args.status) if args.status else store.get_all()
        print(len(opps))


def _run_filter(args: argparse.Namespace) -> None:
    """Run filter command."""
    from rfp_finder.filtering import FilterEngine
    from rfp_finder.models.opportunity import NormalizedOpportunity
    from rfp_finder.models.profile import UserProfile
    from rfp_finder.store import OpportunityStore

    profile = UserProfile.from_yaml(args.profile)
    engine = FilterEngine(profile)

    if args.input:
        data = json.loads(args.input.read_text())
        opportunities = [NormalizedOpportunity.model_validate(o) for o in data]
    else:
        store = OpportunityStore(args.db)
        opportunities = store.get_by_status(args.status) if args.status else store.get_all()

    results = engine.filter_many(opportunities)
    passed = [r for r in results if r.passed]

    if args.show_explanations:
        output_data = [
            {
                "opportunity": r.opportunity.model_dump(mode="json"),
                "passed": r.passed,
                "eligibility": r.eligibility,
                "explanations": r.explanations,
            }
            for r in results
        ]
    else:
        output_data = [r.opportunity.model_dump(mode="json") for r in passed]

    output = json.dumps(output_data, indent=2, default=str)

    if args.output:
        args.output.write_text(output, encoding="utf-8")
        print(f"Filtered: {len(passed)} passed of {len(opportunities)} (wrote to {args.output})")
    else:
        print(output)


if __name__ == "__main__":
    main()
