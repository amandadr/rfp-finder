# User Profile Schema

Config structure for user preferences, eligibility, and notification settings.

## Fields

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `profile_id` | string | — | Unique identifier |
| `keywords_mode` | string | `required` | `required` \| `preferred` \| `exclude_only` |
| `keywords` | list[string] | [] | Terms for scoring (and filtering when mode=required) |
| `exclude_keywords` | list[string] | [] | Deal-breakers |
| `preferred_categories` | list[string] | [] | |
| `example_urls` | list[string] | [] | "Good fit" examples |
| `bad_fit_urls` | list[string] | [] | "Bad fit" examples |
| `eligible_regions` | list[string] | [] | e.g. `["ON", "National"]` |
| `exclude_regions` | list[string] | [] | |
| `citizenship_required` | string \| null | null | `canadian` \| `none` \| null |
| `security_clearance` | string \| null | null | `secret` \| `reliability` \| null |
| `local_vendor_only` | bool \| null | null | |
| `min_budget` | Decimal \| null | null | |
| `max_budget` | Decimal \| null | null | |
| `max_days_to_close` | int \| null | null | Only if closing >= N days out |
| `cadence` | string | `daily` | `daily` \| `weekly` \| `custom` |
| `schedule_cron` | string \| null | null | For custom schedules |
| `notification_channel` | string | `email` | |
| `email` | string \| null | null | |

## Guardrails

- `null` or unset = no filter / unknown eligibility; do not guess.
- Use explicit values only when user or source provides them.
