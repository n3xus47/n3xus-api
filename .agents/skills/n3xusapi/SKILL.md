---
name: n3xusapi
description: Configure and use n3xusAPI from an AI agent for public-web search, scraping, research, platform data, browser tasks, transcription, email, image generation, and local memory. Use the API's configured base URL and report source provenance and support limits.
metadata:
  skill-version: "local-14"
---

# n3xusAPI

This file is a compact router. The `references/` files are organized by user workflow — research, scraping, email, browser automation, image generation, and agent state — not by platform. Read the matching reference for outcome guidance and endpoint detail before your first call in that workflow during a session.

## Configuration and startup

- Read [references/setup.md](references/setup.md) before the first API call in a session or whenever the base URL, repository path, or authentication is unclear. It contains the agent environment template and startup steps.
- Use the configured `N3XUS_API_BASE_URL`; the default is `http://127.0.0.1:8000`. Use `N3XUS_API_REPO` for the checkout path, or infer the repository root from this skill's `.agents/skills/n3xusapi/` location.
- After cloning, initialize or refresh the local stack with `npm run setup`; it checks for current Docker images and the latest configured Ollama model, then builds the API. For routine starts, use `npm start` or `scripts/ensure-local-stack.sh`; this fast path uses only local images and models. Read [references/setup.md](references/setup.md) for the first setup and update flow.
- For a custom or already running API, check `/v1/health` and use it without starting another stack. For the default local service, run `scripts/ensure-local-stack.sh` from the repository only when health is unavailable. If the local setup is missing, the script exits quickly and points to `npm run setup`.
- Local mode needs no API key by default. If the configured API returns `401`, read `N3XUS_API_API_KEY` from the environment and send `Authorization: Bearer $N3XUS_API_API_KEY`; never print, log, or expose the key.
- Fetch public web pages through n3xusAPI routes such as `POST /v1/scrape/website` and `POST /v1/search/web` so the API's public-target protections and provenance are retained.

## Request Rules

- Call `$N3XUS_API_BASE_URL` + route, e.g. `POST $N3XUS_API_BASE_URL/v1/search/web`.
- Optional: send `X-N3xusAPI-Skill-Version` from `VERSION.txt` in this skill folder.
- Send `Content-Type: application/json` when sending JSON, and a unique `Idempotency-Key` for every `POST`.
- Build request bodies from the matching reference and the live `/openapi.json` schema. On validation errors, read the returned `error` or FastAPI validation details; do not assume the server returns a repair schema.
- Local calls are free and return `debitMicrousd: 0`. Use `dryRun: true` when checking a request shape without fetching data.
- Size supported result caps such as `maxItems`, `maxResults`, `maxPages`, and `maxChars` to the task.

## Picking the Right Endpoint

Choose local dossier mode (`POST /v1/scrape/deep`) to collect a compact multi-source dossier. Choose n3xus research (`POST /v1/research/deep`, `mode: "raw"`) to collect multi-source evidence, then synthesize the answer with citations in your response. Use website or platform scraping when the task only needs that source. Read `references/scraping.md` for the dossier recipe.

Before using `POST /v1/search/web`, check whether the target has a dedicated route in this skill's table (GitHub, YouTube, X/Twitter, Instagram, TikTok, Threads, Amazon, or open-business). Prefer that route for source-specific records. Use web search for the open web or when no dedicated route exists; for example, find repositories through `POST /v1/scrape/github/search`, not a `site:github.com` query. One focused search call is normally enough because n3xusAPI fuses local providers; use `POST /v1/research/deep` when the task needs multiple search angles and cited evidence.

When the user requires official or domain-specific sources, use a `site:<domain>` query with `/v1/search/web` or scrape a known official URL directly with `/v1/scrape/website`. Broad `/v1/research/deep` collection can return useful secondary sources without finding the requested primary source; `completeness: "complete"` describes collection coverage, not source quality. Do not claim primary-source support unless a returned source URL belongs to the requested domain and its page content supports the claim.

**Search hits are leads.** A title or snippet is not page evidence. Scrape a candidate URL with `/v1/scrape/website` before using its page content to support an answer. Keep the search and scrape `requestId`s when both calls inform the result.

| Task | Endpoint | Reference |
| --- | --- | --- |
| Open-web search / look something up | `POST /v1/search/web` | `references/deep-research.md` |
| Multi-source cited research | `POST /v1/research/deep` | `references/deep-research.md` |
| Read any webpage | `POST /v1/scrape/website` | `references/scraping.md` |
| Fetch a public image file | `POST /v1/scrape/image` | `references/scraping.md` |
| Ingest a recipe from a blog | `POST /v1/scrape/website` — read `output[].recipe` (`recipeIngredient`), not the page markdown | `references/scraping.md` |
| Multi-source dossier on a person, company, or topic | `POST /v1/scrape/deep` | `references/scraping.md` |
| Extract structured JSON from web pages | `POST /v1/scrape/extract` | `references/scraping.md` |
| Extract PDF text | `POST /v1/scrape/pdf` | `references/scraping.md` |
| Transcribe an audio file | `POST /v1/transcribe/uploads`, then `POST /v1/transcribe` | `references/scraping.md` |
| GitHub repos, issues, PRs, code, commits, profiles | `POST /v1/scrape/github[/profile|/repo|/issues|/pulls|/search|/contents|/commits]` | `references/scraping.md` |
| X/Twitter posts, users, replies | `POST /v1/scrape/twitter[/search|/user|/replies]` | `references/scraping.md` |
| YouTube transcripts, channels, video search, shorts, thumbnails | `POST /v1/scrape/youtube[/transcript|/channel|/search|/shorts|/thumbnail]` | `references/scraping.md` |
| Instagram profiles, posts, comments, hashtag search | `POST /v1/scrape/instagram[/profile|/posts|/comments|/hashtag]` | `references/scraping.md` |
| Facebook group posts and Meta ad library | `POST /v1/scrape/facebook/{groups,ads}` | `references/scraping.md` |
| Open business search from OpenStreetMap | `POST /v1/scrape/open-business/search` (`/v1/scrape/google/places` is a compatibility alias) | `references/scraping.md` |
| TikTok video search, profiles, posts, comments, transcripts | `POST /v1/scrape/tiktok[/search|/profile|/posts|/comments|/transcript]` | `references/scraping.md` |
| Amazon products, search, and reviews | `POST /v1/scrape/amazon/{product,search,reviews}` | `references/scraping.md` |
| Exact Meta Threads posts by URL | `POST /v1/scrape/threads/posts` | `references/scraping.md` |
| Keyword data, search rankings, search competitors | `POST /v1/seo[/keyword|/rank|/competitors]` | `references/seo.md` |
| Plan or improve content for search and AI answers | `POST /v1/seo[/audit|/optimize]` | `references/seo.md` |
| Navigate, click, and extract from a public website | `POST /v1/browser/act` | `references/browse-web.md` |
| Run scripts, shell tools, tests, or Docker in a virtual machine | `POST /v1/vm/run` | `references/browse-web.md` |
| Email workflows, contact data, and company enrichment | `GET/POST /v1/email/*`, `POST /v1/company/enrich` | `references/send-email.md` |
| Generate an image with the configured local image server | `POST /v1/generate/image` | `references/generate-image.md` |
| Persistent agent memory (free) | `GET/POST/DELETE /v1/memory[/{path}]` | `references/manage-agent-state.md` |
| Account: balance, key info, capabilities, usage | `GET /v1/balance`, `/v1/me`, `/v1/capabilities`, `/v1/usage` | `references/manage-agent-state.md` |
| Recover the result of a recent request (free) | `GET /v1/requests`, then `GET /v1/requests/{requestId}` | `references/manage-agent-state.md` |
| Send feedback to the n3xusAPI team (free) | `POST /v1/feedback` | `references/manage-agent-state.md` |

## Execution Loop

1. Choose the narrowest endpoint that matches the task, read its reference file if you haven't this session, and build the request from its schema and examples.
2. Run the request with the required headers.
3. Read the final response. For `status: "succeeded"`, use `output` and any `source` block; report `requestId` and status when useful. Treat `partial`, `blocked`, and `empty` as meaningful collection results, not as complete data.
4. On a failed call, inspect `error.code`, `error.hint`, and `error.retryable` (or the framework validation details). Correct the request before retrying. If the response includes `retryAfterSecs`, wait that long before a retryable call. Use a fresh idempotency key for a new operation; reuse the same key only to recover an identical call whose response was lost.
5. Local calls should report `debitMicrousd: 0`. If the service reports billing or an unexpected account response, stop and verify the configured base URL before continuing.
6. If the service is unexpectedly unavailable, check `GET $N3XUS_API_BASE_URL/v1/health`. Start the local stack only when using the default local service and health is unavailable; do not replace the API with raw requests to target sites.
7. Send `POST /v1/feedback` only when the user asks you to report feedback. Include a relevant `requestId` when available, and omit secrets and private page data.

## Fresh Contract On Demand

If a reference seems outdated or an endpoint is missing, use `GET /openapi.json` for route schemas and `GET /v1/capabilities` for registered capability support levels, adapters, and limitations. A filtered `GET /v1/capabilities?capability=<slug>` returns one capability entry; it does not replace the OpenAPI schema. Prefer the live API contract over stale examples.

## Staying up to date

- This skill is maintained in the n3xus-api repo under `.agents/skills/n3xusapi/`.
- Contract truth: `GET $N3XUS_API_BASE_URL/v1/capabilities` and `GET $N3XUS_API_BASE_URL/openapi.json` (or `/docs`).
- Support levels and parity gaps: repo `README.md` and `docs/deepapi-parity-audit.md`.
