# Local SEO workflows

Use the SEO routes for local search visibility checks:

- `POST /v1/seo/keyword` with `keywords` (1–100 strings)
- `POST /v1/seo/rank` with `keyword`, `domain`, and optional `depth`
- `POST /v1/seo/competitors` with `domain` and optional `limit`
- `POST /v1/seo/audit` with `keyword` and optional `domain`
- `POST /v1/seo/optimize` with `keyword` and `text`

These routes use the local SearxNG adapter and, for optimization, the configured local model. They do not provide commercial keyword volume, CPC, difficulty, trend, or overlap metrics; those fields remain `null` or are omitted. Report the adapter and `source` provenance instead of presenting local SERP observations as paid SEO analytics.

Use `dryRun: true` to validate a body without searching or invoking the local model. For a real call, include a unique `Idempotency-Key`.
