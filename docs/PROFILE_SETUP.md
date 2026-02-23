# Profile Setup Guide

Your profile controls filtering and scoring. Edit `profiles/my-profile.yaml` (or create your own) and customize the settings below.

## Quick Start

```bash
# 1. Copy the template
cp profiles/my-profile.yaml profiles/amanda.yaml

# 2. Edit with your preferences
# 3. Run full pipeline (filter → score)
poetry run rfp-finder run --profile profiles/amanda.yaml --db rfp_finder.db --output scored.json
```

---

## Filters

### `regions`
Provinces/territories you can bid in. CanadaBuys values include:
- **National** — Federal tenders open across Canada
- **ON**, **QC**, **BC**, **AB**, **MB**, **SK**, **NS**, **NB**, **NL**, **PE**, **YT**, **NT**, **NU**

Example: `["ON", "National"]` — Ontario and federal tenders.

### `keywords_mode`
- `required` — At least one keyword must match (strict).
- `preferred` — No keyword requirement; pass more to scoring (recommended).
- `exclude_only` — Only apply exclude_keywords; no keyword requirement.

### `keywords`
Terms used for scoring (and filtering when `keywords_mode=required`). Searches: title, summary, categories, commodity codes.

Example: `["AI", "machine learning", "software development"]`

### `exclude_keywords`
Deal-breakers for **filtering** (hard exclude). Scoring uses structured penalties (category, title phrases) instead of free-text matching.

### `max_days_to_close`
Only include tenders closing in **at least** N days.

- `60` — At least 60 days to prepare
- `null` — No deadline filter

### `min_budget` / `max_budget`
Budget range in CAD. Tenders without budget info pass through.

- `max_budget: 500000` — Cap at $500K
- `null` — No budget filter

---

## Eligibility

Set these to match your firm. If a tender doesn't include eligibility info, it's not excluded (eligibility = "unknown").

| Field | Options |
|-------|---------|
| `citizenship_required` | `canadian`, `none`, or `null` |
| `security_clearance` | `secret`, `reliability`, or `null` |
| `local_vendor_only` | `true`, `false`, or `null` |

---

## Example Profiles

**Software consultant (Ontario + federal):**
```yaml
filters:
  regions: ["ON", "National"]
  keywords: [software, "IT services", consulting]
  exclude_keywords: [construction, printing]
  max_days_to_close: 30
  max_budget: 250000
```

**General services (all Canada):**
```yaml
filters:
  regions: ["National"]
  keywords: []
  exclude_keywords: []
  max_days_to_close: null
```

**YAML tip:** Use quotes for values that could be parsed as booleans: `"ON"` instead of `ON` (YAML parses unquoted `ON` as true).

---

## Scoring

Scoring uses your `keywords`, `preferred_categories`, and good/bad examples. See [SCORING.md](./SCORING.md) for the heuristic model and optional LLM setup.
