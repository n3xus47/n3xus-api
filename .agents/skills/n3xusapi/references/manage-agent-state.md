# Requests, capabilities, memory, and feedback

## Contract discovery

Use `GET /v1/capabilities` to list supported slugs and support levels. Use `GET /v1/capabilities?capability=<slug>` for one route's adapter and limitations. Treat `structured`, `best_effort`, `experimental`, and `unavailable` as meaningful output quality signals. The live OpenAPI contract is available at `/openapi.json` and `/docs`.

## Request recovery

Every successful non-dry-run POST returns a local `requestId` and is stored. Use `GET /v1/requests` to list recent calls or `GET /v1/requests/{requestId}` to recover one response. A local request is normally settled immediately; follow a returned `next` only when the response explicitly provides it.

## Memory

Use `GET /v1/memory` to list files, `GET /v1/memory/{path}` to read, `POST /v1/memory/{path}` with `{ "content": "...", "ifVersion": 3 }` to write, and `DELETE` to remove. Writes are limited to 256 KiB and use optimistic version checks. Preserve existing content by reading and merging when a version conflict occurs.

## Usage and feedback

`GET /v1/usage` reports local usage with zero debit; `/v1/balance` and `/v1/me` describe local mode rather than a hosted account. Send one concise `POST /v1/feedback` after a reproducible failure or a concrete product idea, including the relevant `requestId` when available. Do not send secrets, page credentials, or raw private data in feedback.
