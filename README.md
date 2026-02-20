# Canadian AI-Driven RFP Finder

A tool that finds and ranks Canadian government and public-sector RFP/tender opportunities using AI, with configurable filters, eligibility rules, and digest delivery.

## Documentation

| Document | Purpose |
|----------|---------|
| [DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md) | High-level phased plan |
| [SOLUTIONS_APPROACH.md](docs/SOLUTIONS_APPROACH.md) | Full technical solutions, data models, and implementation approach per phase |

## Quick Start

```bash
# Install (use virtual env)
poetry install

# Ingest from CanadaBuys (writes to stdout or --output file)
poetry run rfp-finder ingest --source canadabuys
poetry run rfp-finder ingest --source canadabuys --output opportunities.json

# Incremental fetch (new tenders only)
poetry run rfp-finder ingest --source canadabuys --incremental

# Ingest and persist to SQLite store
poetry run rfp-finder ingest --source canadabuys --store rfp_finder.db

# Query the store
poetry run rfp-finder store count --db rfp_finder.db
poetry run rfp-finder store list --db rfp_finder.db --status open

# Filter by profile
poetry run rfp-finder filter --profile profiles/example.yaml --db rfp_finder.db
poetry run rfp-finder filter --profile profiles/example.yaml --db rfp_finder.db --show-explanations --output filtered.json

# Run full pipeline (filter → score) — recommended
poetry run rfp-finder run --profile profiles/example.yaml --db rfp_finder.db --output scored.json
poetry run rfp-finder run --profile profiles/example.yaml --db rfp_finder.db --stats  # show filter breakdown

# Run tests
poetry run pytest tests/ -v
```

## LLM Scoring (Optional)

To use OpenAI for AI-powered scoring instead of heuristics:

```bash
poetry install -E llm   # installs openai package
cp .env.example .env
# Add OPENAI_API_KEY=sk-... and RFP_FINDER_LLM_PROVIDER=openai to .env
```

## Secrets

Store API keys and other secrets in a `.env` file (gitignored):

```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

Used when `RFP_FINDER_LLM_PROVIDER=openai` for AI scoring. Never commit `.env`.

## Project Status

- **Phase 1 (Source Ingestion)** — Complete. CanadaBuys connector; connector framework; incremental fetch; attachment discovery.
- **Phase 2 (Storage, Dedupe, Change Tracking)** — Complete. SQLite store with upsert, deduplication by (source, source_id), content-hash amendment detection, lifecycle status, run tracking.
- **Phase 3 (Profile-Based Filtering)** — Complete. FilterEngine with region, keywords, deadline, budget, eligibility rules; full explanation trail; `filter` CLI.
