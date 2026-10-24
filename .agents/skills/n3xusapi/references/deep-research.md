# Research with n3xusAPI

Use this reference for `POST /v1/search/web`, `POST /v1/research/deep`, and `POST /v1/scrape/deep`.

Before the first research call, check `/v1/health`. If the default local API is unavailable, run `npm start` from `N3XUS_API_REPO`; it starts the already configured services without network updates or builds. The default local model is `qwen3.5:4b`. If the stack has not been initialized or the model is missing, run `npm run setup` once to fetch current images and the latest configured model.

## Search

Send a focused query to `/v1/search/web`:

```json
{
  "query": "specific question or search phrase",
  "maxResults": 10
}
```

The response is an n3xusAPI envelope. Read `output.results`, preserve each result's `title`, `url`, and `snippet`, and use `source` to report the provider and `collectionState`. `collectionState: "empty"` is a successful search with no useful results; it is different from a failed request.

n3xusAPI fuses SearxNG and DuckDuckGo locally. Do not issue five near-duplicate searches merely to imitate a hosted search workflow. Increase `maxResults` or use deep research when broader coverage is needed.

## Deep research

Use `/v1/research/deep` for a question that needs multiple sources:

```json
{
  "query": "What are the current tradeoffs between ...?",
  "context": "Relevant scope or user constraints",
  "instructions": "Cite every factual claim and call out missing evidence.",
  "mode": "raw"
}
```

Use `mode: "raw"` for the skill's normal workflow. It returns numbered evidence without waiting for local-model planning or synthesis; write the concise cited answer from those excerpts. `mode: "clean"` invokes the local model and is experimental. Use it only when the user specifically wants API-generated synthesis, and accept its answer only when factual claims cite valid evidence numbers. If it returns the evidence fallback, synthesize from `evidence` yourself. The output includes `searchPlan`, `evidence`, and `completeness`; treat `partial` and `empty` as collection limits, not confidence scores.

## Dossiers

Use `/v1/scrape/deep` for a compact dossier when the user wants a subject collected across public sources. It is a local research workflow, not a source-specific people, company, or social data provider. Preserve the returned evidence and source URLs.

## Evidence rules

Search snippets are leads, not page content. Scrape the candidate URL with `/v1/scrape/website` before treating a result as proof. For official or domain-specific sourcing, use a `site:<domain>` query with `/v1/search/web` or scrape a known official URL directly; broad `/v1/research/deep` can return only secondary sources. Its `complete` state describes collection coverage, not relevance or authority. Claim primary-source support only after confirming the returned page URL and content. Keep source URLs in the answer and state when a page was blocked, empty, or represented only by a search snippet.

## Recovery

For a failed request, inspect `error.code`, `error.hint`, and `error.retryable`. Retry only when the hint supports it. Use a new `Idempotency-Key` for a new POST attempt; use the same key only to recover a request whose response was lost.
