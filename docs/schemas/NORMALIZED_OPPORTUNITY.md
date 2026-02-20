# Normalized Opportunity Schema

Reference schema for the canonical opportunity record. All connectors must map their native format to this structure.

## Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `id` | string | ✓ | `{source}:{source_id}` |
| `source` | string | ✓ | `canadabuys` \| `merx` |
| `source_id` | string | ✓ | Native tender/notice ID |
| `title` | string | | |
| `summary` | string \| null | | Plain-text abstract |
| `url` | string \| null | | Canonical opportunity URL |
| `buyer` | string \| null | | Organization name |
| `buyer_id` | string \| null | | Source-provided ID when available |
| `published_at` | datetime \| null | | ISO 8601 |
| `closing_at` | datetime \| null | | Submission deadline |
| `amended_at` | datetime \| null | | Last amendment |
| `categories` | list[string] | | UNSPSC, keywords, etc. |
| `commodity_codes` | list[string] | | e.g. GSIN |
| `trade_agreements` | list[string] \| null | | |
| `region` | string \| null | | Province or "National" |
| `locations` | list[string] \| null | | |
| `budget_min` | Decimal \| null | | |
| `budget_max` | Decimal \| null | | |
| `budget_currency` | string \| null | | e.g. CAD |
| `attachments` | list[AttachmentRef] | | |
| `status` | string | | `open` \| `closed` \| `amended` \| `unknown` |
| `first_seen_at` | datetime | ✓ | Set by store |
| `last_seen_at` | datetime | ✓ | Set by store |
| `content_hash` | string \| null | | For change detection |

## AttachmentRef

| Field | Type | Notes |
|-------|------|-------|
| `url` | string | |
| `label` | string \| null | Display label |
| `mime_type` | string \| null | e.g. `application/pdf` |
| `size_bytes` | int \| null | When available |
