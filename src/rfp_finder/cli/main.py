"""Main CLI entry point."""

import argparse
import json
from datetime import datetime
from pathlib import Path

# Load .env into os.environ before any commands run (keeps OPENAI_API_KEY etc. out of code)
def _load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


def main() -> None:
    """Parse args and dispatch to subcommands."""
    _load_env()
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
    filter_parser.add_argument(
        "--stats",
        action="store_true",
        help="Show exclusion breakdown (keyword, region, deadline, budget)",
    )

    # examples (Phase 4)
    examples_parser = subparsers.add_parser("examples", help="Manage good/bad fit examples for AI scoring")
    examples_parser.add_argument(
        "action",
        choices=["add", "list", "sync"],
        help="Add example, list examples, or sync from profile YAML",
    )
    examples_parser.add_argument(
        "--profile",
        type=Path,
        required=True,
        help="Path to profile YAML (for sync) or profile_id (for add/list)",
    )
    examples_parser.add_argument(
        "--db",
        type=Path,
        default=Path("rfp_finder.db"),
        help="Path to SQLite database",
    )
    examples_parser.add_argument("--url", type=str, help="Example URL (for add)")
    examples_parser.add_argument(
        "--label",
        type=str,
        choices=["good", "bad"],
        help="Label: good or bad fit (for add)",
    )

    # score (Phase 4)
    score_parser = subparsers.add_parser("score", help="AI relevance scoring of filtered opportunities")
    score_parser.add_argument(
        "--profile",
        type=Path,
        required=True,
        help="Path to profile YAML",
    )
    score_parser.add_argument(
        "--db",
        type=Path,
        default=Path("rfp_finder.db"),
        help="Read from store",
    )
    score_parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Read filtered JSON (alternative to --db)",
    )
    score_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write scored results",
    )
    score_parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Max opportunities to score with LLM (default: 20)",
    )
    score_parser.add_argument(
        "--enrich-top",
        type=int,
        default=5,
        metavar="N",
        help="Enrich top N with PDF attachment text before LLM (default: 5, use 0 to disable)",
    )
    score_parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("cache/attachments"),
        help="Attachment cache directory (default: cache/attachments)",
    )

    # run (full pipeline: filter → score)
    run_parser = subparsers.add_parser(
        "run",
        help="Run full pipeline: filter opportunities by profile, then score (filter → score)",
    )
    run_parser.add_argument(
        "--profile",
        type=Path,
        required=True,
        help="Path to profile YAML",
    )
    run_parser.add_argument(
        "--db",
        type=Path,
        default=Path("rfp_finder.db"),
        help="Path to SQLite database",
    )
    run_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write scored results to file",
    )
    run_parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Max opportunities to score (default: 20)",
    )
    run_parser.add_argument(
        "--enrich-top",
        type=int,
        default=5,
        metavar="N",
        help="Enrich top N with PDF attachment text (default: 5, use 0 to disable)",
    )
    run_parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("cache/attachments"),
        help="Attachment cache directory",
    )
    run_parser.add_argument(
        "--stats",
        action="store_true",
        help="Show filter exclusion breakdown",
    )

    # enrich (Phase 5)
    enrich_parser = subparsers.add_parser("enrich", help="Fetch and extract PDF attachments")
    enrich_parser.add_argument(
        "--db",
        type=Path,
        default=Path("rfp_finder.db"),
        help="Database path",
    )
    enrich_parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("cache/attachments"),
        help="Attachment cache directory",
    )
    enrich_parser.add_argument(
        "--top",
        type=int,
        default=50,
        help="Max opportunities to process (default: 50)",
    )

    args = parser.parse_args()

    if args.command == "ingest":
        _run_ingest(args)
    elif args.command == "store":
        _run_store(args)
    elif args.command == "filter":
        _run_filter(args)
    elif args.command == "examples":
        _run_examples(args)
    elif args.command == "score":
        _run_score(args)
    elif args.command == "run":
        _run_run(args)
    elif args.command == "enrich":
        _run_enrich(args)
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

    if not opportunities:
        print(
            "No opportunities in store. Run ingest first:\n"
            "  poetry run rfp-finder ingest --source canadabuys --store rfp_finder.db",
            file=__import__("sys").stderr,
        )
        raise SystemExit(1)

    results = engine.filter_many(opportunities)
    passed = [r for r in results if r.passed]

    if getattr(args, "stats", False):
        _print_filter_stats(results)

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


def _print_filter_stats(results: list) -> None:
    """Print exclusion breakdown by first-failing rule."""
    from collections import Counter

    passed = sum(1 for r in results if r.passed)
    excluded = [r for r in results if not r.passed]
    reasons: Counter[str] = Counter()
    for r in excluded:
        rule = getattr(r, "excluded_by_rule", None) or "other"
        reasons[rule] += 1
    total = len(results)
    print(f"\n--- Filter stats: {passed}/{total} passed ---")
    for rule, count in reasons.most_common():
        pct = 100 * count / total
        print(f"  Excluded by {rule}: {count} ({pct:.1f}%)")
    if reasons:
        print()


def _run_examples(args: argparse.Namespace) -> None:
    """Run examples command."""
    from rfp_finder.models.profile import UserProfile
    from rfp_finder.store import ExampleStore, OpportunityStore

    profile = UserProfile.from_yaml(args.profile)
    ex_store = ExampleStore(args.db)

    if args.action == "add":
        if not args.url or not args.label:
            raise SystemExit("examples add requires --url and --label")
        ex = ex_store.add(profile.profile_id, args.url, args.label)
        print(f"Added {args.label} example: {ex.url} (id={ex.id})")
    elif args.action == "list":
        for ex in ex_store.list_by_profile(profile.profile_id):
            print(f"  [{ex.label}] {ex.url}")
    elif args.action == "sync":
        opp_store = OpportunityStore(args.db)
        existing_urls: set[str] = {e.url for e in ex_store.list_by_profile(profile.profile_id)}
        added = 0
        for url in profile.example_urls:
            if url not in existing_urls:
                ex_store.add(profile.profile_id, url, "good")
                added += 1
                existing_urls.add(url)
        for url in profile.bad_fit_urls:
            if url not in existing_urls:
                ex_store.add(profile.profile_id, url, "bad")
                added += 1
        print(f"Synced {added} new examples from profile (good: {len(profile.example_urls)}, bad: {len(profile.bad_fit_urls)})")


def _run_score(args: argparse.Namespace) -> None:
    """Run score command. When using --db, runs filter first to score only passed opportunities."""
    from rfp_finder.filtering import FilterEngine
    from rfp_finder.models.opportunity import NormalizedOpportunity
    from rfp_finder.models.profile import UserProfile
    from rfp_finder.scoring import score_opportunities
    from rfp_finder.store import AttachmentCacheStore, ExampleStore, OpportunityStore

    profile = UserProfile.from_yaml(args.profile)
    if args.input:
        data = json.loads(args.input.read_text())
        opportunities = [NormalizedOpportunity.model_validate(o) for o in data]
    else:
        store = OpportunityStore(args.db)
        raw = store.get_by_status("open")
        engine = FilterEngine(profile)
        results = engine.filter_many(raw)
        opportunities = [r.opportunity for r in results if r.passed]
    if not opportunities:
        print("No opportunities to score.", file=__import__("sys").stderr)
        raise SystemExit(1)
    ex_store = ExampleStore(args.db)
    cache_store = AttachmentCacheStore(args.db) if getattr(args, "enrich_top", 0) > 0 else None
    scored = score_opportunities(
        profile=profile,
        opportunities=opportunities,
        example_store=ex_store,
        top_k=args.top,
        enrich_top_n=getattr(args, "enrich_top", 0),
        cache_dir=getattr(args, "cache_dir", None),
        attachment_cache_store=cache_store,
    )
    output = json.dumps(scored, indent=2, default=str)
    if args.output:
        args.output.write_text(output, encoding="utf-8")
        print(f"Scored {len(scored)} opportunities (wrote to {args.output})")
    else:
        print(output)


def _run_run(args: argparse.Namespace) -> None:
    """Run full pipeline: filter → score."""
    from rfp_finder.models.profile import UserProfile
    from rfp_finder.pipeline import run_pipeline

    profile = UserProfile.from_yaml(args.profile)
    show_stats = getattr(args, "stats", False)

    result = run_pipeline(
        profile=profile,
        db_path=args.db,
        status="open",
        top_k=args.top,
        enrich_top_n=getattr(args, "enrich_top", 5),
        cache_dir=getattr(args, "cache_dir", None),
        return_filter_results=show_stats,
    )

    if show_stats:
        scored, filter_results = result
        _print_filter_stats(filter_results)
    else:
        scored = result

    if not scored:
        print("No opportunities passed filters.", file=__import__("sys").stderr)
        raise SystemExit(1)

    output = json.dumps(scored, indent=2, default=str)
    if args.output:
        args.output.write_text(output, encoding="utf-8")
        print(f"Scored {len(scored)} opportunities (wrote to {args.output})")
    else:
        print(output)


def _run_enrich(args: argparse.Namespace) -> None:
    """Run enrich command: fetch and extract PDF attachments for top opportunities."""
    from rfp_finder.attachments import enrich_opportunity
    from rfp_finder.models.opportunity import NormalizedOpportunity
    from rfp_finder.store import AttachmentCacheStore, OpportunityStore

    store = OpportunityStore(args.db)
    opps = store.get_by_status("open")[: args.top]
    cache_store = AttachmentCacheStore(args.db)
    cache_dir = args.cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    enriched = 0
    for opp in opps:
        if opp.attachments:
            text = enrich_opportunity(opp, cache_dir, cache_store, fetch_missing=True)
            if "[Attachment:" in text:
                enriched += 1
    print(f"Enriched {enriched} opportunities with attachment text (cache: {cache_dir})")


if __name__ == "__main__":
    main()
