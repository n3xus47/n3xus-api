# DeepAPI data-parity audit

## Goal

Make n3xusAPI a free, local-first open-source tool that is genuinely useful as a source of current public-web data. It is personal/self-hosted software, not a hosted multi-tenant platform.

**Parity means:** for a supported capability, return equally useful, normalized, current data with transparent provenance and failure states. Identical billing, tenancy, hosted inboxes, or cloud execution are explicitly out of scope.

## Evidence

- DeepAPI endpoint contract supplied by the project owner on 2026-03-02.
- n3xusAPI source and tests inspected on 2026-03-02.
- This is an implementation audit, not a claim that either provider succeeds on every live target. Each change needs recorded live evaluations before it is declared complete.

## Principles

1. Local-first is the default; no data broker, credential, cookie, CAPTCHA bypass, login, or covert tracking.
2. A capability must expose source provenance, collection time, and a truthful blocked/empty/partial state. Never return guessed data as observed data.
3. A free optional provider adapter is acceptable only when its licence, rate limits, privacy implications, and output provenance are documented.
4. Paid providers may be optional adapters, never a hidden requirement or the only implementation of a capability marketed as free.
5. Do not make a capability appear `available` until it passes its acceptance evaluation.

## Current verdict

n3xusAPI has broad route coverage, but several routes are generic webpage fetches behind a source-specific name. Those routes do not yet provide the structured data users expect. The first product milestone is therefore **truthful capability contracts and measurable data quality**, not additional endpoint names.

## Capability matrix

| Capability | Current state | Parity gap | Priority |
|---|---|---|---|
| Website scrape | Readability extraction, crawl, Chromium fallback | Block/source state, robust JS path, crawl observability | P1 |
| Web search | SearxNG results | Result fusion, dedupe, provenance, quality evaluation | P1 |
| Deep research | 5 search results + pages + Ollama | Query planning, source diversity, evidence quality/completeness | P1 |
| GitHub | Public GitHub REST adapter | Pagination tokens, normalized issue/PR semantics, rate-limit handling | P1 |
| YouTube | yt-dlp + transcript API | Normalized channel/video records, multi-channel support, fallback/evals | P1 |
| PDF | Public text-layer extraction | Error and metadata consistency | P2 |
| Browser act | Playwright + local LLM | Reliable planner/executor, structured trace, evaluation suite | P2 |
| VM | Local Docker execution | Docker mode, timeout/truncation state, isolation hardening | P2 |
| Transcription | local faster-whisper | GPU option, quality/latency benchmark, correct upload contract | P2 |
| Image | local A1111 | Model capability discovery, output metadata, evals | P3 |
| X / Instagram / TikTok / Threads | Mostly page-level generic scraping | Structured posts/profiles/comments/search and reliable public collection | P0 |
| Facebook Ads / Groups | Search/page fetch | Ads Library records and normalized public group posts | P0 |
| Amazon | Search/page fetch | Product, listing and review records across marketplaces | P0 |
| Google Places | Nominatim, not Google Places | Business records incl. phone/site/rating/reviews; explicit source naming | P0 |
| SEO keyword / competitors | Mostly null fields / SearxNG | Volume, CPC, difficulty, trends, meaningful competitor overlap | P0 |
| Email find / verify / enrich | Public-page exact match; syntax only | Verified mailboxes and professional enrichment cannot be claimed local-only | P2 |
| Company enrich | Home-page metadata | Structured company profile and source coverage | P2 |
| Email delivery | Local SMTP and drafts | Delivery/reply observability and policy controls; hosted inbox lifecycle out of scope | P3 |
| Memory | Local SQLite storage | Mostly suitable; add quotas/usage only if needed | P3 |

## What can reach parity locally

- Website, PDF, GitHub, YouTube, research, browser, VM and transcription can reach practical parity through better adapters, normalization, retries, observability, and evaluations.
- Image generation can reach quality parity when the user provides a capable local GPU/model.
- Email drafts and SMTP delivery can be excellent local tooling, but not a replacement for a hosted email platform.

## What requires an explicit source strategy

No generic scraper can reliably equal commercial data collection for the following sources without a legally compliant data source, a source-specific public adapter, or both:

1. X, Instagram, TikTok, Threads and Facebook.
2. Amazon products and reviews.
3. Google Places ratings, review counts, phones and websites.
4. SEO volume, CPC, difficulty and SERP data.
5. Mailbox verification and person/company enrichment.

For these capabilities, “free” must mean either a documented public/free source with known limits, or a user-configured optional provider. It must not mean evasion of platform protections.

## Milestone 1 — truthful contracts and data-quality baseline

### Outcome

Every advertised capability has a machine-readable support level and an evidence-backed evaluation baseline. A caller can distinguish structured data from a best-effort page fetch before using it.

### Deliverables

1. A capability registry that replaces the flat `CAPABILITIES` map. Each entry defines:
   - endpoint route and capability slug;
   - support level: `structured`, `best_effort`, `experimental`, or `unavailable`;
   - provider/adapter name;
   - source provenance policy;
   - known limitations;
   - evaluation suite identifier.
2. `GET /v1/capabilities` returns that metadata. Unsupported or only generic-page adapters must not claim `available` structured support.
3. A stable `source` block in successful outputs where data originates externally: source name, URL(s), retrieved time, and collection state (`complete`, `partial`, `blocked`, `empty`).
4. Contract tests for the capability registry, envelope, idempotency and dry-run behavior.
5. A committed evaluation corpus with at least 10 legal, public test cases for each of: website, search, GitHub, YouTube, research, Google Places, Amazon, one social source, and SEO rank.
6. A reproducible evaluation command that records success rate, required-field coverage, latency and failure reason without secrets.
7. A baseline report in `docs/evals/` from a real local run. No source-specific route is upgraded to `structured` until it meets its documented threshold.

### Non-goals

- Cloud billing, user accounts, API-key scopes, DeepAPI spend semantics, hosted memory, hosted VM, or hosted email inboxes.
- Bypassing authentication, CAPTCHAs, access controls, rate limits, or website terms.
- Claiming commercial SEO/contact data without a documented source.

### Acceptance criteria

- `GET /v1/capabilities` truthfully classifies every current public capability.
- At least one end-to-end evaluation report exists and is reproducible locally.
- Tests prevent a generic page scraper from being advertised as structured source-specific data.
- README describes support levels and how to run evaluations.

## Ordered GitHub issue backlog

### M1: capability truthfulness and evaluation foundation

1. **Define the capability registry and support-level contract**
   - Replace `CAPABILITIES` with registry metadata.
   - Add support-level and limitation fields to `/v1/capabilities`.
   - Acceptance: contract tests cover every registered route.

2. **Add source provenance and collection states to external-data outputs**
   - Normalize `complete`, `partial`, `blocked`, and `empty`.
   - Acceptance: website, search, GitHub and Google Places emit provenance.

3. **Build the reproducible data-quality evaluation harness**
   - Fixtures, legal public targets, metrics and Markdown report generator.
   - Acceptance: one command runs without secrets and writes a report.

4. **Create and run the initial evaluation corpus**
   - Minimum 10 cases per named M1 capability.
   - Acceptance: baseline reports document required-field coverage and failures.

5. **Document local-first support levels and evaluation workflow**
   - README only after the previous behavior exists.
   - Acceptance: user can understand which outputs are structured versus best-effort.

### P0: close the highest-value data gaps

6. **Replace the Google Places misrepresentation with a structured open-business adapter**
   - Keep OSM source explicit; do not label it as Google data.
   - Add sources such as OpenStreetMap/Overpass where licence permits.
   - Acceptance: normalized business fields and source attribution; rating/reviews remain absent unless a lawful source exists.

7. **Build a normalized Amazon adapter with transparent marketplace coverage**
   - Product/listing/review schemas, source-specific blocked state and evaluations.
   - Acceptance: never return raw webpage text as a product/review record.

8. **Build source-specific public social adapters, starting with one source**
   - Choose the source from M1 success-rate evidence.
   - Acceptance: profile/post records are normalized and no login/CAPTCHA bypass is used.

9. **Build a public Meta Ads Library adapter**
   - Use officially accessible public data only.
   - Acceptance: normalized creative, copy, URL, dates and provenance where available.

10. **Design optional lawful SEO-data adapters**
    - Evaluate free sources and licences before implementation.
    - Acceptance: unavailable fields remain null unless a documented source supplies them.

### P1: improve dependable local capabilities

11. **Harden website crawl and JS rendering**
12. **Add GitHub pagination and normalized resource semantics**
13. **Normalize YouTube channel/search/Shorts records and fallbacks**
14. **Upgrade research into a source-diverse evidence pipeline**
15. **Improve browser act with structured trace and benchmark suite**
16. **Harden local VM execution contract and isolation**
17. **Benchmark and improve local transcription**

### P2: conditional capabilities

18. **Add an opt-in, policy-governed email verification adapter**
19. **Add source-backed company enrichment**
20. **Add local email delivery observability**
21. **Add local image model discovery and quality evaluation**

## Delivery rule

For every issue: design the adapter seam first, implement it behind the existing route, add contract tests, run the evaluation corpus, and only then change its support level. Do not widen claims based solely on unit tests.
