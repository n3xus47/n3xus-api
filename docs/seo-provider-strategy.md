# SEO provider strategy (issue #8)

Commercial keyword metrics (volume, CPC, difficulty, trend, intent) and paid SERP APIs require an explicit maintainer approval before n3xusAPI may populate those fields. This document records researched options and the current decision.

## Researched options

| Source | Licence / ToS | Configuration | Rate limits | Privacy impact | Fields realistically available |
| --- | --- | --- | --- | --- | --- |
| **SearxNG (self-hosted)** | AGPL-3.0; aggregates public search engines configured by the operator | Built-in (`N3XUS_API_SEARXNG_URL`) | Depends on upstream engines; local instance should stay on localhost | Queries leave the operator network to configured engines; no third-party SaaS account | Organic SERP rows: title, URL, snippet, optional date — **not** volume/CPC/difficulty |
| **Google Ads Keyword Planner API** | Google Ads API Terms; requires an Ads account | Operator Google Ads credentials | Google quota per developer token | Google processes keywords and account metadata | Volume ranges, CPC estimates, competition — **not approved** until maintainer documents account + retention policy |
| **DataForSEO** | Commercial API agreement | Operator API login + payment | Per-task billing and concurrency caps | Keywords and domains sent to DataForSEO | Volume, CPC, SERP, backlinks — **candidate only** |
| **SerpApi / similar SERP SaaS** | Vendor ToS | Operator API key | Monthly search caps per plan | Full queries stored/processed by vendor | Parsed SERP features — **candidate only** |
| **Moz / Ahrefs / SEMrush APIs** | Commercial | Operator subscription key | Vendor-specific | Domains/keywords exposed to vendor | Authority, backlinks, keyword metrics — **candidate only** |
| **Google Trends (public site)** | Google ToS; no official free API | Not integrated | Aggressive anti-automation | Query text to Google | Relative interest over time — **not** search volume or CPC |

## Decision (2026-09-14)

1. **Approved for default local use:** `searxng-local-serp` — rank, audit SERP sections, and competitor domain discovery from organic results only.
2. **Commercial metrics:** remain `null` with `metricsUnavailableReason: no_approved_commercial_source` until a row above moves to `approved` in code (`app/seo_adapters.py`) and this file is updated with the chosen source, licence link, and env vars.
3. **Optional adapters:** may be added only when listed as `approved` in the registry and documented here; `candidate` entries must not be wired to live endpoints.

## Operator checklist before approving a new adapter

- Link to primary licence / API terms.
- List required env vars and what data leaves the host.
- Document rate limits and expected cost.
- Map each response field to an adapter id (no inferred volume/CPC).
- Add eval fixtures that assert nulls stay null when the adapter is disabled.

Re-run SEO eval slice: `npm run eval -- --fixtures evals/m1-baseline.json --suite seo --output docs/evals/seo-latest.md`
