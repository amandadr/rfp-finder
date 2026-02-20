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

# Run tests
poetry run pytest tests/ -v
```

## Project Status

- **Phase 1 (Source Ingestion)** — Complete. CanadaBuys connector using official open data CSV; connector framework; incremental fetch; attachment discovery; full test coverage.
