# Development Plan — Canadian AI-Driven RFP Finder

High-level phased plan. See **[SOLUTIONS_APPROACH.md](./SOLUTIONS_APPROACH.md)** for full technical solutions and implementation details.

---

## Phase 0 — Definition and Guardrails

* **Define "sources in scope" (v1)**: CanadaBuys + MERX (see Solutions doc for rationale).
* **Define the normalized opportunity record**: See Appendix A in SOLUTIONS_APPROACH.
* **Define user profile + constraints model**: See §0.3 in SOLUTIONS_APPROACH.
* **Define "success outputs"**: See §0.4 — digest structure and confidence labels.

---

## Phase 1 — Source Ingestion (v1) ✅

**Solutions:** Connector framework, CanadaBuys connector, incremental fetching, attachment discovery.  
**Deliverable:** Repeatable run producing normalized opportunities from first source.  
**Status:** Complete.

---

## Phase 2 — Storage, Dedupe, and Change Tracking ✅

**Solutions:** SQLite store, deterministic IDs, content-hash amendment detection, lifecycle status.  
**Deliverable:** Daily runs without spam; only new/amended items for digest.  
**Status:** Complete. See `src/rfp_finder/store/`; `rfp-finder ingest --store DB`; `rfp-finder store list/count`.

---

## Phase 3 — Profile-Based Filtering (Non-AI Baseline) ✅

**Solutions:** Hard filters (region, keywords, deadline, budget), eligibility rules engine, filter explanations.  
**Deliverable:** Obviously irrelevant results removed before AI.  
**Status:** Complete. See `src/rfp_finder/filtering/`; `rfp-finder filter --profile YAML --db DB`.

---

## Phase 4 — AI Relevance Scoring Using Examples ✅

**Solutions:** Example ingestion, similarity shortlist, LLM ranking + rationale, confidence labels.  
**Deliverable:** Ranked, personalized, explainable opportunities.  
**Status:** Complete. See `src/rfp_finder/scoring/`; `rfp-finder examples add/list/sync`; `rfp-finder score`.

---

## Phase 5 — Document Handling (PDFs/Attachments) as Enrichment

**Solutions:** Attachment fetch/cache, text extraction pipeline, selective enrichment policy, evidence harvesting.  
**Deliverable:** Higher accuracy, fewer "unknown eligibility" cases.

---

## Phase 6 — Notifications and Digest Delivery

**Solutions:** Digest generator (top/maybe/amended), cadence scheduler, multi-recipient configs.  
**Deliverable:** Consistent digests on desired cadence.

---

## Phase 7 — Shareability and Colleague Onboarding

**Solutions:** Config templates, env vars, validator, dry run, health summary, feedback capture.  
**Deliverable:** Colleagues can clone, configure, and receive digests without deep troubleshooting.

---

## Phase 8 — Expansion and Hardening

**Solutions:** Additional connectors, cross-source dedupe, amendment diffs, multi-profile, rate limiting, alerting.  
**Deliverable:** Reliable tool as sources and needs grow.

---

## Risk Map

| Level | Items | Mitigation |
|-------|-------|------------|
| **Highest** | Source connectors, PDF extraction, eligibility inference, dedupe/amendment | See SOLUTIONS_APPROACH §A.3 |
| **Lowest** | Config management, digest formatting, scheduling, local storage | Standard patterns |
