# Canadian AI-Driven RFP Finder — Full Solutions Approach

This document expands each phase of the development plan with concrete technical solutions, data models, architecture decisions, and implementation guidance.

---

## Table of Contents

1. [Phase 0 — Definition and Guardrails](#phase-0--definition-and-guardrails)
2. [Phase 1 — Source Ingestion (v1)](#phase-1--source-ingestion-v1)
3. [Phase 2 — Storage, Dedupe, and Change Tracking](#phase-2--storage-dedupe-and-change-tracking)
4. [Phase 3 — Profile-Based Filtering](#phase-3--profile-based-filtering-non-ai-baseline)
5. [Phase 4 — AI Relevance Scoring](#phase-4--ai-relevance-scoring-using-examples)
6. [Phase 5 — Document Handling (PDFs/Attachments)](#phase-5--document-handling-pdfsattachments-as-enrichment)
7. [Phase 6 — Notifications and Digest Delivery](#phase-6--notifications-and-digest-delivery)
8. [Phase 7 — Shareability and Colleague Onboarding](#phase-7--shareability-and-colleague-onboarding)
9. [Phase 8 — Expansion and Hardening](#phase-8--expansion-and-hardening)
10. [Appendix: Data Models](#appendix-data-models)

---

## Phase 0 — Definition and Guardrails

### 0.1 Sources in Scope (v1)

**Decision: Start with CanadaBuys only ( Phase 1 implementation )**

| Source | Type | Rationale | Coverage |
|--------|------|-----------|----------|
| **CanadaBuys** | Federal + cross-jurisdictional | Official Government of Canada portal; open data CSV files; PSPC, Crown corps, broader public sector. Refreshed daily (open tenders) and every 2 hours (new tenders). | Federal government |

**Deferred for later phases:** MERX, provincial-only portals (SEAO, Purchasing Connection, etc.).

---

### 0.2 Normalized Opportunity Record

Every source connector must map its native format into this schema. All fields are optional except `id`, `source_id`, and `source`.

```python
# NormalizedOpportunity (Python dataclass / Pydantic model)
@dataclass
class NormalizedOpportunity:
    # Identity
    id: str                    # Deterministic: {source}:{native_id}
    source: str                # "canadabuys" | "merx"
    source_id: str             # Native tender/notice ID
    
    # Core metadata
    title: str
    summary: str | None        # Plain-text abstract/description
    url: str | None            # Canonical opportunity URL
    
    # Parties
    buyer: str | None          # Organization name
    buyer_id: str | None       # When source provides structured ID
    
    # Timing
    published_at: datetime | None
    closing_at: datetime | None
    amended_at: datetime | None
    
    # Classification
    categories: list[str]      # UNSPSC codes, keywords, or source categories
    commodity_codes: list[str] # e.g. UNSPSC, GSIN
    trade_agreements: list[str] | None
    
    # Location & scope
    region: str | None         # Province, territory, or "National"
    locations: list[str] | None
    
    # Budget (when available)
    budget_min: Decimal | None
    budget_max: Decimal | None
    budget_currency: str | None
    
    # Attachments
    attachments: list[AttachmentRef]
    
    # Lifecycle (managed by store)
    status: str = "open"       # "open" | "closed" | "amended" | "unknown"
    first_seen_at: datetime
    last_seen_at: datetime
    content_hash: str | None   # For change detection

@dataclass
class AttachmentRef:
    url: str
    label: str | None
    mime_type: str | None
    size_bytes: int | None
```

**Implementation:** Use Pydantic for validation and JSON serialization. Store as JSON Lines or in SQLite/PostgreSQL.

---

### 0.3 User Profile + Constraints Model

```python
@dataclass
class UserProfile:
    profile_id: str
    
    # Skills & preferences (for AI scoring)
    keywords: list[str]         # Must-have terms
    exclude_keywords: list[str] # Deal-breakers
    preferred_categories: list[str]
    example_urls: list[str]     # "Good fit" examples
    bad_fit_urls: list[str]     # "Bad fit" examples
    
    # Geography
    eligible_regions: list[str]  # e.g. ["ON", "National"]
    exclude_regions: list[str]
    
    # Eligibility (explicit only; no inference)
    citizenship_required: str | None   # "canadian" | "none" | None (unknown)
    security_clearance: str | None     # "secret" | "reliability" | None
    local_vendor_only: bool | None     # True/False/None (unknown)
    
    # Filters
    min_budget: Decimal | None
    max_budget: Decimal | None
    max_days_to_close: int | None      # e.g. 30 = only if closing >= 30 days out
    
    # Notification
    cadence: str = "daily"      # "daily" | "weekly" | "custom"
    schedule_cron: str | None  # For custom schedules
    notification_channel: str = "email"
    email: str | None
```

**Guardrail:** If a field is not set or is `None`, treat as "no filter" or "unknown eligibility" rather than guessing.

---

### 0.4 Success Outputs (Digest Content)

Each digest item must include:

| Section | Content |
|---------|---------|
| **Top matches** | Ranked opportunities with score (0–100), short rationale, evidence quotes, key dates, buyer, link |
| **Maybe** | Lower confidence; uncertain eligibility; "needs PDF review" |
| **Amended since last digest** | Items with status `amended`, with prior close date if changed |
| **Per-item fields** | Score, rationale, risks/dealbreakers to check, evidence snippet (traceable), confidence label |
| **Confidence labels** | `high` \| `medium` \| `low` \| `insufficient_text` \| `unknown_eligibility` |

---

## Phase 1 — Source Ingestion (v1)

### 1.1 Connector Framework

**Interface (abstract base):**

```python
# Connector interface
class BaseConnector(ABC):
    source_id: str  # e.g. "canadabuys"
    
    @abstractmethod
    def search(self, query: str | None, filters: dict) -> list[RawOpportunity]:
        """List/search opportunities; returns raw format."""
        pass
    
    @abstractmethod
    def fetch_details(self, raw_id: str) -> RawOpportunity:
        """Fetch full details for one opportunity."""
        pass
    
    @abstractmethod
    def normalize(self, raw: RawOpportunity) -> NormalizedOpportunity:
        """Convert raw to NormalizedOpportunity."""
        pass
    
    def fetch_incremental(self, since: datetime) -> list[NormalizedOpportunity]:
        """Override for sources with incremental APIs (e.g. RSS)."""
        raise NotImplementedError
```

**Implementation strategy:**

- Each connector lives in `connectors/<source_id>/` (e.g. `connectors/canadabuys/`, `connectors/merx/`).
- Connectors use `httpx` for HTTP with retries and rate limiting.
- Raw responses cached temporarily for debugging; normalization happens in-memory.
- `RawOpportunity` is a flexible dict or TypedDict; only `normalize()` enforces the schema.

---

### 1.2 First Canadian Source Connector (CanadaBuys)

**Approach:**

1. **Primary path:** CanadaBuys provides RSS/ATOM feeds. Use `feedparser` to consume them for incremental discovery.
2. **Detail fetch:** Each feed item links to a detail page. Scrape or use any available JSON/API endpoint.
3. **Fallback:** If no official API, use structured HTML scraping with `beautifulsoup4` + `selectolax` (fast parser).

**Fields to extract:**

- Title, description, reference number, closing date
- Organization (buyer)
- Commodity codes (UNSPSC/GSIN if present)
- Region, trade agreements
- Attachment links from the detail page

**Error handling:** Log fetch failures, retry with exponential backoff, mark run as partial on connector failure.

---

### 1.3 Incremental Fetching

| Source | Strategy |
|--------|----------|
| CanadaBuys | RSS feed returns recent items; fetch only items newer than `last_run_at`. |
| MERX | If API supports date filter, use it; else fetch full list and diff against last run. |

**Local tracking (fallback):**

- Store `last_successful_run_at` per source.
- Fetch all items (or recent window).
- Rely on Phase 2 store to dedupe and detect new/amended.

---

### 1.4 Attachment Discovery

- Parse HTML/JSON for links matching common patterns: `.pdf`, `/document/`, `attachment`, etc.
- Store `AttachmentRef` with `url`, `label`, `mime_type` (from `Content-Type` or extension), `size_bytes` (when available).
- **No download or parsing in Phase 1**—only metadata.

---

### 1.5 Phase 1 Deliverable

- `ConnectorRegistry` that discovers and instantiates connectors.
- `CanadaBuysConnector` returning `NormalizedOpportunity` list.
- CLI: `rfp-finder ingest --source canadabuys` runs once and prints normalized JSON.
- Optional: `--since YYYY-MM-DD` for incremental hint.

---

## Phase 2 — Storage, Dedupe, and Change Tracking

### 2.1 Local Opportunity Store

**Technology:** SQLite for v1 (single-user, no setup). Schema supports PostgreSQL later.

**Tables:**

```
opportunities
  - id (PK), source, source_id, content_hash, status
  - JSON blob or normalized columns for full record
  - first_seen_at, last_seen_at

runs
  - id (PK), source, started_at, finished_at, status, items_fetched, items_new, items_amended
```

**Operations:**

- `upsert(opp)` — insert or update by `(source, source_id)`; set `last_seen_at`, compute `content_hash`.
- `get_all()`, `get_by_status()`, `get_modified_since()`.

---

### 2.2 Deduplication

**Deterministic ID:**

```
id = f"{source}:{source_id}"
```

Example: `canadabuys:WS123456`, `merx:12345678`.

**Cross-source dedupe (Phase 8):**

- Compare `title`, `buyer`, `closing_at` within a time window.
- Use embedding similarity or Jaccard on normalized text for near-duplicate detection.
- Store `canonical_id` to merge duplicates; v1 can skip this.

---

### 2.3 Amendment/Change Detection

**Content hash:**

```python
def content_hash(opp: NormalizedOpportunity) -> str:
    key_fields = (opp.title, opp.summary, opp.closing_at, opp.amended_at,
                  [a.url for a in opp.attachments])
    return hashlib.sha256(json.dumps(key_fields, sort_keys=True).encode()).hexdigest()
```

**Logic:**

1. On upsert, compare new `content_hash` to stored one.
2. If different and record exists → set `status = "amended"`, store `prior_hash` or prior version in `opportunity_amendments` table.
3. If new → `status = "open"`, `first_seen_at = now`.
4. If not seen this run and past `closing_at` → `status = "closed"`.

---

### 2.4 Lifecycle Status Model

| Status | Meaning |
|--------|---------|
| `open` | Active opportunity, before close date |
| `closed` | Past closing date |
| `amended` | Content changed since last run |
| `unknown` | Cannot determine (e.g. missing close date) |

**Close date handling:** If `closing_at` is None, leave as `open` or `unknown`. Run a nightly job to re-check and set `closed` when date passes.

---

### 2.5 Phase 2 Deliverable

- SQLite store with migrations (e.g. `alembic` or simple `schema.sql`).
- Dedupe by `(source, source_id)`.
- Hash-based change detection and amendment tracking.
- CLI: `rfp-finder ingest --source canadabuys` persists to store and reports new/amended counts.

**Implementation:** `OpportunityStore` in `src/rfp_finder/store/`; `--store DB_PATH` flag; `store list/count` subcommand. Run tracking in `runs` table.

---

## Phase 3 — Profile-Based Filtering (Non-AI Baseline)

### 3.1 Hard Filters

Applied in order; each filter produces an explanation.

| Filter | Implementation | Explanation format |
|--------|----------------|-------------------|
| Region | `opp.region in profile.eligible_regions` or "National" | `"Matches region: ON"` or `"Excluded: region QC not in eligible"` |
| Categories/keywords | Substring or token match in title/summary/categories | `"Matches keyword: AI"` |
| Deadline window | `closing_at >= today` and `closing_at <= today + max_days_to_close` | `"Closing in 45 days (within window)"` |
| Budget | `opp.budget_max <= profile.max_budget` when both present | `"Within budget range"` |

**Guardrail:** If a filter field is missing from the opportunity (e.g. no budget), do not reject—mark as "filter not applicable" and pass through.

---

### 3.2 Eligibility Rules Engine (v1)

**Explicit only:**

- If opportunity has `citizenship_required = "canadian"` and profile has `citizenship_required = None` → `eligibility = "unknown"`, do not exclude.
- If both are set and they match → `eligibility = "eligible"`.
- If both set and they conflict → `eligibility = "ineligible"`, attach reason.

**Unknown eligibility:** Add to "maybe" section in digest; do not hide.

---

### 3.3 Explanations

Every filter decision appends to a list:

```python
@dataclass
class FilterResult:
    passed: bool
    explanations: list[str]
    eligibility: str  # "eligible" | "ineligible" | "unknown"
```

---

### 3.4 Phase 3 Deliverable

- `FilterEngine` with pluggable rules.
- Each rule returns `(passed, explanation)`.
- Filtered list with full explanation trail for digest transparency.

---

## Phase 4 — AI Relevance Scoring Using Examples

### 4.1 Example Ingestion

**Input:**

- URLs of past opportunities (good fit / bad fit).
- Or pasted text blobs.

**Process:**

1. Fetch or accept text.
2. Store in `examples/` table or JSON files: `{ "profile_id", "url", "text", "label": "good" | "bad" }`.
3. Chunk long text; store chunks with metadata.

---

### 4.2 Similarity Layer (First-Pass)

**Options:**

1. **Embedding-based:** Use `sentence-transformers` or OpenAI `text-embedding-3-small` to embed examples and opportunities. Compute cosine similarity; shortlist top-k.
2. **BM25/keyword:** Good for exact term overlap; faster, no API cost.

**Recommendation:** Start with embeddings; cache embeddings for examples. For each new opportunity, embed once and compare to example embeddings. Shortlist e.g. top 50 by similarity for LLM pass.

---

### 4.3 LLM Ranking + Rationale

**Prompt structure:**

```
Given:
- User profile: {keywords, preferred categories, ...}
- Opportunity: {title, summary, ...}

Produce:
1. Score 0-100
2. Reasons it matches profile (bullet list)
3. Key risks / dealbreakers to check
4. Evidence snippets (verbatim quotes from opportunity text)
```

**Output schema (structured):**

```python
@dataclass
class LLMScoringResult:
    score: int
    match_reasons: list[str]
    risks_dealbreakers: list[str]
    evidence_snippets: list[str]
```

**Model:** Use local (Ollama) or API (OpenAI, Anthropic). Keep prompts under token limits; truncate long summaries if needed.

---

### 4.4 Confidence + Uncertainty Labeling

| Label | When to use |
|-------|-------------|
| `high` | Ample text, eligibility known, strong match |
| `medium` | Adequate text, some unknowns |
| `low` | Weak match or thin evidence |
| `insufficient_text` | Very short summary, no attachments parsed |
| `unknown_eligibility` | Eligibility field missing or unclear |

---

### 4.5 Phase 4 Deliverable

- Example ingestion CLI: `rfp-finder examples add --url URL --label good`.
- Similarity shortlist; LLM scoring for shortlist.
- Ranked list with score, rationale, evidence, confidence label.
- Configurable LLM provider and model via env vars.

---

## Phase 5 — Document Handling (PDFs/Attachments) as Enrichment

### 5.1 Attachment Fetch + Caching

- Download attachments to `cache/attachments/{content_hash_or_id}.pdf`.
- Skip if already cached and not stale.
- Rate limit: 1–2 requests/second per domain.
- Store `(url, local_path, fetched_at, extraction_status)` in DB.

---

### 5.2 Text Extraction Pipeline

**Libraries:**

- `pypdf` or `pdfplumber` for embedded text.
- `pymupdf` (fitz) for complex layouts.
- Track: `extraction_success`, `text_length`, `page_count`, `error_message`.

---

### 5.3 Selective Enrichment Policy

- Extract PDFs only for:
  - Top N by score (e.g. top 20), or
  - Items with `unknown_eligibility`, or
  - Items with `insufficient_text`.
- Config: `extract_pdfs_for_top_n: 20`, `extract_when_eligibility_unknown: true`.

---

### 5.4 Evidence Harvesting

- Append extracted text to opportunity content before LLM scoring.
- LLM returns evidence snippets; ensure snippets reference "from opportunity" vs "from attachment" when traceable.
- Store snippet with `source: "main" | "attachment:filename"`.

---

### 5.5 Phase 5 Deliverable

- Attachment downloader with caching.
- Extraction pipeline with success/failure tracking.
- Configurable enrichment policy.
- Enriched opportunities with better scoring and fewer unknowns.

---

## Phase 6 — Notifications and Digest Delivery

### 6.1 Digest Generator

**Template structure:**

```
Subject: RFP Digest — [Date] — X matches

--- Top matches ---
[For each: title, buyer, close date, score, rationale, evidence, link]

--- Maybe (review eligibility) ---
[Same format, with uncertainty note]

--- Amended since last digest ---
[Title, what changed if known, link]
```

**Format:** HTML and plain-text fallback for email; also support markdown file output for dry run.

---

### 6.2 Cadence Scheduler

- Use `APScheduler` or `schedule` for in-process scheduling.
- Or external: cron + `rfp-finder run` for daily/weekly.
- Log each run: start, end, sources run, items fetched, digest sent.
- Store `last_digest_sent_at` per profile.

---

### 6.3 Multi-Recipient Support

- Config file per user: `profiles/{user_id}.yaml` or `profiles/{user_id}.json`.
- Shared codebase; `main.py` or CLI iterates over configs.
- Each run loads one profile, runs pipeline, generates and sends one digest.

---

### 6.4 Phase 6 Deliverable

- Digest template with top/maybe/amended sections.
- Scheduler integrated or documented for cron.
- Multi-user config loading and per-user digests.
- Email sending via SMTP (env vars for credentials).

---

## Phase 7 — Shareability and Colleague Onboarding

### 7.1 Config Packaging

- **Template configs:** `config.example.yaml` with placeholders.
- **Env vars:** `RFP_FINDER_API_KEY`, `RFP_FINDER_SMTP_PASSWORD`, etc.
- **Defaults:** Cadence daily, max 50 items per digest, no aggressive keyword filters.

---

### 7.2 Validation + Diagnostics

- **Config validator:** `rfp-finder validate --config path` checks required fields, file paths, API connectivity.
- **Dry run:** `rfp-finder run --dry-run` produces digest to stdout/file without sending.
- **Health summary:** After run, log: sources reachable Y/N, items found, PDFs extracted, email sent Y/N.

---

### 7.3 Feedback Capture (Lightweight)

- Add `feedback` table: `(opportunity_id, profile_id, label, created_at)`.
- CLI: `rfp-finder feedback --opp-id X --label good`.
- Use in Phase 4 retraining or prompt tuning (store as examples).

---

### 7.4 Phase 7 Deliverable

- Example config and env var documentation.
- Validator and dry-run mode.
- Feedback capture for future model improvement.

---

## Phase 8 — Expansion and Hardening

### 8.1 Additional Source Connectors

- One connector at a time; same `BaseConnector` interface.
- MERX as second source.
- Cross-source dedupe: compare title, buyer, dates; optional embedding similarity.

---

### 8.2 Better Amendment Understanding

- Store diff of key fields (title, summary, closing_at).
- Use `difflib` or structured diff for text.
- Digest: "Amended: closing date moved from X to Y."

---

### 8.3 Role-Based Tuning

- Multiple profiles per person: `profile_id: amanda-data`, `profile_id: amanda-ai-strategy`.
- Separate configs or multi-profile in one config.
- Separate digest per profile.

---

### 8.4 Operational Resilience

| Measure | Implementation |
|---------|----------------|
| Rate limiting | `httpx` with limits; 1 req/s per host default |
| Backoff | Exponential backoff on 429/5xx |
| Connector isolation | Try/except per connector; one failure doesn’t stop others |
| Alerting | Log failures; optional webhook or email on repeated failures |
| Source change detection | Compare response structure hash; alert on schema change |

---

### 8.5 Phase 8 Deliverable

- MERX connector and cross-source dedupe.
- Amendment diff and clearer digest messaging.
- Multi-profile support.
- Resilient runs with logging and optional alerting.

---

## Appendix: Data Models

### A.1 Project Layout (Suggested)

```
rfp-finder/
├── pyproject.toml / requirements.txt
├── config.example.yaml
├── .env.example
├── src/
│   rfp_finder/
│   ├── __init__.py
│   ├── models/
│   │   ├── opportunity.py
│   │   ├── profile.py
│   │   └── digest.py
│   ├── connectors/
│   │   ├── base.py
│   │   ├── canadabuys/
│   │   └── merx/
│   ├── store/
│   │   ├── sqlite_store.py
│   │   └── schema.sql
│   ├── filtering/
│   │   ├── engine.py
│   │   └── rules/
│   ├── scoring/
│   │   ├── similarity.py
│   │   └── llm.py
│   ├── documents/
│   │   ├── fetch.py
│   │   └── extract.py
│   ├── digest/
│   │   ├── generator.py
│   │   └── templates/
│   └── cli/
│       └── main.py
├── profiles/
│   └── example.yaml
├── docs/
│   └── SOLUTIONS_APPROACH.md (this file)
└── tests/
```

### A.2 Config Schema (YAML)

```yaml
# profiles/amanda.yaml
profile_id: amanda
sources:
  - canadabuys
  - merx

filters:
  regions: [ON, National]
  keywords: [AI, machine learning, data]
  exclude_keywords: [construction, hardware]
  max_days_to_close: 60
  min_budget: null
  max_budget: 500000

eligibility:
  citizenship_required: canadian
  security_clearance: null
  local_vendor_only: false

scoring:
  example_urls: []
  bad_fit_urls: []
  llm_provider: openai
  llm_model: gpt-4o-mini

notifications:
  cadence: daily
  channel: email
  email: amanda@example.com

digest:
  top_n: 10
  maybe_n: 5
```

### A.3 Risk Mitigation Summary

| Risk | Mitigation |
|------|------------|
| Source connectors brittle | Abstract interface; RSS first for CanadaBuys; retries and backoff |
| PDF extraction fragile | Track success/failure; fallback to main text; selective enrichment only |
| Eligibility inference wrong | No inference in v1; explicit rules only; "unknown" passed to maybe |
| Dedupe/amendment complex | Start simple: hash + status; defer cross-source to Phase 8 |

---

*Document version: 1.0 | Last updated: 2025-02*
