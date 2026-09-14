# Search fusion change — measurement plan

Date: 2026-09-14

## Assumption under test

Multi-query SearxNG fusion (5 variants, URL dedupe) improves recall vs a single query, matching DeepAPI agent guidance without paid search APIs.

## How to measure

```bash
docker compose up --build -d
docker compose exec ollama ollama pull qwen3:8b   # research synthesis only
npm run eval -- --fixtures evals/m1-baseline.json --output docs/evals/latest-after-fusion.md
```

Compare `search.web` and `research.deep` success rates to `docs/evals/m1-baseline.md` (2026-09-14).

## Code changes

- `app/search.py`: `build_search_variants`, `search_web_fused`
- `/v1/search/web` uses fusion by default
- `research.deep` uses fusion per planned query; LLM optional for plan/synthesis

## Remaining gaps vs DeepAPI (require product decision)

| Area | Local path | DeepAPI |
| --- | --- | --- |
| SEO volume/CPC | null unless operator approves commercial adapter | Paid keyword API |
| Google Places ratings | OSM only | Maps backend |
| Amazon/social at scale | Public fetch; blocks → `blocked` | Managed collectors |
| Email verify/enrich | syntax / unavailable | Brokers |

See `docs/deepapi-parity-audit.md` backlog P0–P2.
