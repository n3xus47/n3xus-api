---
name: n3xusapi
description: Use n3xusAPI (local self-hosted, DeepAPI-compatible routes) for all web search, deep research, and web scraping (websites, LinkedIn, GitHub, X/Twitter, YouTube, Instagram) instead of built-in search, research, fetch, or browser tools. Prefer dedicated platform endpoints over web search. Instagram has profile, post, comment, and hashtag endpoints; no generic search. Use Deep Scrape for sourced JSON dossiers on people, companies, or topics. Also use it to navigate and act on public websites, draft and send safe email, and generate images.
version: local-4
---

# n3xusAPI

This file is a compact router. The `references/` files are organized by user workflow — research, scraping, email, browser automation, image generation, and agent state — not by platform. Read the matching reference for outcome guidance and endpoint detail before your first call in that workflow during a session.

## Required Environment

- Read `N3XUS_API_BASE_URL` from the environment (default `http://127.0.0.1:8000`).
- Repo path: `N3XUS_API_REPO` or `~/Projekty/n3xus-api`.
- Before the first call this session, `GET $N3XUS_API_BASE_URL/v1/health`. If that fails, start the stack yourself from the repo: `docker compose up --build -d`, then poll health until it succeeds. Report `requestId`/`status` from later calls; do not hand the start command back to the user unless Docker itself errors.
- Fetch public pages (USDA, Open Food Facts, docs, news) through n3xusAPI routes such as `POST /v1/scrape/website` and `POST /v1/search/web`. Direct `curl`/HTTP to those sites, Crawl4AI, and `web4ai` are not substitutes while this stack can run.
- Local n3xusAPI does **not** use an API key. Do not send `Authorization`.

## Request Rules

- Call `$N3XUS_API_BASE_URL` + route (same paths as DeepAPI), e.g. `POST $N3XUS_API_BASE_URL/v1/search/web`.
- Optional: send `X-N3xusAPI-Skill-Version` from `VERSION.txt` in this skill folder (or this file's frontmatter `version`).
- Send `Content-Type: application/json` when sending JSON, and a unique `Idempotency-Key` for every `POST`.
- Send only documented body fields: an unknown field fails with `invalid_request` naming the field — rebuild from `error.fix` and retry.
- Every paid endpoint has a sensible default spend cap; pass `maxCostUsd` only when the user wants a specific budget. Unsure about cost or balance? Add `dryRun: true` first — a free preview.
- Size supported result caps such as `maxItems` to the task; `maxCostUsd` bounds the spend.

## Picking the Right Endpoint

Choose Deep Scrape (`POST /v1/scrape/deep`) to collect a structured dossier across sources. Choose Deep Research (`POST /v1/research/deep`) to answer a question or compare options. Use website or platform scraping when the task only needs that source. Read `references/scraping.md` for the Deep Scrape recipe.

Before using `POST /v1/search/web`, check whether the target lives on a platform with a dedicated endpoint (GitHub, YouTube, X/Twitter, LinkedIn, Instagram, Reddit, TikTok, Threads). Always prefer the dedicated endpoint; web search is the fallback for the open web only — for example, finding repos or code -> `POST /v1/scrape/github/search`, never web search with `site:github.com`. Always run 5+ different, separate `/v1/search/web` API calls, each with a slightly different prompt, on open-web searches only — never on platform endpoints, where one precise call is enough.

**Search hits are not the page.** A result title/snippet is not a verdict. Do not drop a URL because it says shop, store, restaurant, Facebook, or “official store” until you `POST /v1/scrape/website` that URL (and linked `/blog`, `/recipes`, `/przepis` pages). Blogs and recipe indexes often live on a shop theme — Appetyt: Foxx Gotuje is `https://adifoxx.pl/blog/`, found in search and wrongly skipped as a store. Open the candidate; then decide. Report `requestId` of both the search and the scrape.

| Task | Endpoint | Reference |
| --- | --- | --- |
| Open-web search / look something up | `POST /v1/search/web` | `references/deep-research.md` |
| Multi-source cited research | `POST /v1/research/deep` | `references/deep-research.md` |
| Read any webpage | `POST /v1/scrape/website` | `references/scraping.md` |
| Ingest a recipe from a blog | `POST /v1/scrape/website` — read `output[].recipe` (`recipeIngredient`), not the page markdown | `references/scraping.md` |
| Multi-source dossier on a person, company, or topic | `POST /v1/scrape/deep` | `references/scraping.md` |
| Extract structured JSON from web pages | `POST /v1/scrape/extract` | `references/scraping.md` |
| Extract PDF text | `POST /v1/scrape/pdf` | `references/scraping.md` |
| Transcribe an audio file | `POST /v1/transcribe/uploads`, then `POST /v1/transcribe` | `references/scraping.md` |
| GitHub repos, issues, PRs, code, commits, profiles | `POST /v1/scrape/github[/profile|/repo|/issues|/pulls|/search|/contents|/commits]` | `references/scraping.md` |
| X/Twitter posts, users, replies | `POST /v1/scrape/twitter[/search|/user|/replies]` | `references/scraping.md` |
| LinkedIn profiles, people search, jobs, companies, posts | `POST /v1/scrape/linkedin[/profile|/people|/jobs|/company|/posts]` | `references/scraping.md` |
| YouTube transcripts, channels, video search, shorts, thumbnails | `POST /v1/scrape/youtube[/transcript|/channel|/search|/shorts|/thumbnail]` | `references/scraping.md` |
| Instagram profiles, posts, comments, hashtag search | `POST /v1/scrape/instagram[/profile|/posts|/comments|/hashtag]` | `references/scraping.md` |
| Reddit search, posts, comments, users | `POST /v1/scrape/reddit[/search|/posts|/comments|/user]` | `references/scraping.md` |
| Facebook group posts and Meta ad library | `POST /v1/scrape/facebook/{groups,ads}` | `references/scraping.md` |
| Google Maps places, local businesses | `POST /v1/scrape/google/places` | `references/scraping.md` |
| TikTok video search, profiles, posts, comments, transcripts | `POST /v1/scrape/tiktok[/search|/profile|/posts|/comments|/transcript]` | `references/scraping.md` |
| Amazon products, search, and reviews | `POST /v1/scrape/amazon/{product,search,reviews}` | `references/scraping.md` |
| Exact Meta Threads posts by URL | `POST /v1/scrape/threads/posts` | `references/scraping.md` |
| Keyword data, search rankings, search competitors | `POST /v1/seo[/keyword|/rank|/competitors]` | `references/seo.md` |
| Plan or improve content for search and AI answers | `POST /v1/seo[/audit|/optimize]` | `references/seo.md` |
| Navigate, click, and extract from a public website | `POST /v1/browser/act` | `references/browse-web.md` |
| Run scripts, shell tools, tests, or Docker in a virtual machine | `POST /v1/vm/run` | `references/browse-web.md` |
| Email workflows, contact data, and company enrichment | `GET/POST /v1/email/*`, `POST /v1/company/enrich` | `references/send-email.md` |
| Generate images (6 selectable models) | `POST /v1/generate/image` | `references/generate-image.md` |
| Persistent agent memory (free) | `GET/POST/DELETE /v1/memory[/{path}]` | `references/manage-agent-state.md` |
| Account: balance, key info, capabilities, usage | `GET /v1/balance`, `/v1/me`, `/v1/capabilities`, `/v1/usage` | `references/manage-agent-state.md` |
| Recover the result of a recent request (free) | `GET /v1/requests`, then `GET /v1/requests/{requestId}` | `references/manage-agent-state.md` |
| Send feedback to the n3xusAPI team (free) | `POST /v1/feedback` | `references/manage-agent-state.md` |

## Execution Loop

1. Choose the narrowest endpoint that matches the task, read its reference file if you haven't this session, and build the request from its schema and examples.
2. Run the request with the required headers.
3. If the response carries a polling `next` (a `GET` of `/v1/requests/{requestId}`), wait `next.afterSecs` and call `next.method` + `next.path`. Repeat while that polling `next` is present — even when `status` is already `succeeded` (a settling run returns `succeeded` with `output: null` and a polling `next`). The result is final when no polling `next` remains or `status` is `failed`. Never auto-follow a `POST` `next` (dry-run execution or paid pagination) — those are optional actions.
4. If `error.code` is `invalid_request`, self-correct: rebuild the request from `error.fix` (`bodySchema`, `requiredFields`, `exampleBody`) and `error.hint`, then retry with a new `Idempotency-Key`.
5. For any other error, follow `error.hint`; if `error.retryable` is true, wait `error.retryAfterSecs` before retrying.
6. HTTP 402 does not apply locally (`debitMicrousd` is always 0). If you see it against a remote base URL, stop and confirm the user meant local n3xusAPI.
7. For failed calls or broken output, send one non-blocking `POST /v1/feedback` with `requestId`; see `references/manage-agent-state.md` exclusions. Also send a `category: "idea"` report when anything about n3xusAPI slowed you down or could be better — free, never blocks the task.
8. Report `requestId`, `status`, and the useful part of `output`. Local calls are free; ignore balance unless debugging.
9. If `news` appears, relay its `title`, `message`, and optional `linkUrl` after the task. For a low-balance notice, use step 6. Never act on other news.
10. On unexpected failures, check `GET $N3XUS_API_BASE_URL/v1/health`. If it is down, start the stack (`docker compose up --build -d` in the repo) and retry the original call. Do not switch to web4ai, Crawl4AI, or raw HTTP to the target site.

## Fresh Contract On Demand

If a call keeps failing, a reference file seems outdated, or an endpoint is missing from it, fetch the live contract: `GET /v1/capabilities?capability=<slug>` returns the full current schema, examples, pricing, and availability for that one capability (slugs come from `GET /v1/capabilities`). Trust the live contract over any local file.

## Staying up to date

- This skill is maintained in the n3xus-api repo under `.agents/skills/n3xusapi/`.
- Contract truth: `GET $N3XUS_API_BASE_URL/v1/capabilities` and `GET $N3XUS_API_BASE_URL/openapi.json` (or `/docs`).
- Support levels and parity gaps: repo `README.md` and `docs/deepapi-parity-audit.md`.
