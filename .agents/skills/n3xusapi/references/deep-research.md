# Research with n3xusAPI

Use this reference for `POST /v1/search/web`, `POST /v1/research/deep`, and `POST /v1/scrape/deep`.

Before the first research call in a session, run `scripts/ensure-local-stack.sh` from `N3XUS_API_REPO`. It starts the local services and verifies that `N3XUS_API_OLLAMA_MODEL` is present and current. The default is `qwen3.5:27b`; set the environment variable before startup to use another Ollama model.

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
  "mode": "clean"
}
```

`mode: "raw"` is the default and returns numbered evidence excerpts. `mode: "clean"` asks the configured local model to synthesize a sourced brief. The output includes `searchPlan`, `evidence`, and `completeness`; treat `partial` and `empty` as limitations of the collected evidence, not as confidence scores.

## Dossiers

Use `/v1/scrape/deep` for a compact dossier when the user wants a subject collected across public sources. It is a local research workflow, not a source-specific people, company, or social data provider. Preserve the returned evidence and source URLs.

## Evidence rules

Search snippets are leads, not page content. Scrape the candidate URL with `/v1/scrape/website` before treating a result as proof. Keep source URLs in the answer and state when a page was blocked, empty, or represented only by a search snippet.

## Recovery

For a failed request, inspect `error.code`, `error.hint`, and `error.retryable`. Retry only when the hint supports it. Use a new `Idempotency-Key` for a new POST attempt; use the same key only to recover a request whose response was lost.
