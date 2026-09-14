#!/usr/bin/env bash
# One-shot: create ordered Sandcastle GitHub issues for n3xusAPI quality sprint.
set -euo pipefail
REPO="${1:-n3xus47/n3xus-api}"

create() {
  local title="$1"
  local body="$2"
  gh issue create --repo "$REPO" --label Sandcastle --title "$title" --body "$body"
}

create "Search fusion: integration tests for SearxNG+ddgs merge and provenance" "$(cat <<'EOF'
## Context (already implemented — verify, do not rewrite)

Prior session landed on `main`:

- `app/search.py`: parallel SearxNG + DuckDuckGo (`ddgs`), URL dedupe, `relevance_score` / `rank_search_results`
- `app/main.py`: `source.name` e.g. `searxng+duckduckgo`
- `app/capabilities.py`: adapter `searxng+duckduckgo`
- `pyproject.toml`: dependency `ddgs`
- `searxng/settings.yml`: DuckDuckGo engine enabled (lower weight)
- `tests/test_search_fusion.py`: unit tests (merge, variants)

## Problem

Unit tests pass but **live** queries still return junk (e.g. „top 10 chefs” → Zara). Harness marks `collectionState: complete` without checking relevance.

## Task

1. Add **integration/contract tests** (mock HTTP for SearxNG + ddgs) proving merge + ranking order for a fixture where SearxNG returns noise and DDG returns on-topic URLs.
2. Assert `/v1/search/web` envelope: `source.name` contains expected providers when mocked.
3. Document in issue comment any gap found in Docker (ddgs import).

## Acceptance

- [ ] New tests in `tests/test_search_fusion.py` or `tests/test_api.py` (no network)
- [ ] `npm run test` and `npm run typecheck` green
- [ ] RALPH commit closes this issue

**Priority:** Tracer bullet
EOF
)"

create "Search: filter low-relevance results (agent-safe web search)" "$(cat <<'EOF'
## Problem

E2E „przepisy” test: `/v1/search/web` returns `succeeded` + irrelevant URLs (Transfermarkt „Gordon”, Zara „top”). Eval M1 search success ~10% (many `empty`, some junk).

## Task

1. After `rank_search_results`, **drop** results below a documented relevance floor OR return **empty** `results` with honest `source.collectionState` (prefer new state `low_relevance` if backward compatible, else `empty` + log).
2. Never return high-volume junk when top score is below threshold.
3. **Red-green tests** with crafted `SearchResult` lists (chef query vs footballer).

## Acceptance

- [ ] Behavior tests for Gordon Ramsay recipe query fixture (mocked results)
- [ ] Contract documented in `app/capabilities.py` limitations if needed
- [ ] `npm run test` green

**Priority:** Bug fix  
**Depends on:** previous issue (fusion tests) optional
EOF
)"

create "Search: support site: operator via post-filter on merged results" "$(cat <<'EOF'
## Problem

Queries like `carbonara site:jamieoliver.com` ignore `site:` — Bing/SearxNG returns unrelated domains.

## Task

1. Parse `site:domain` from query (simple regex); strip from text sent to engines if helpful.
2. After merge/rank, **filter** `results` to URLs whose host matches (include subdomains).
3. If filter removes all rows, return empty results (not unfiltered junk).

## Acceptance

- [ ] Unit tests: parser + filter in `app/search.py`
- [ ] API test with mocked fusion returning mixed hosts
- [ ] `npm run test` green

**Priority:** Bug fix
EOF
)"

create "Search: agent-realism eval fixture (chef/recipe queries)" "$(cat <<'EOF'
## Problem

`evals/m1-baseline.json` search cases check field presence only, not topical URLs.

## Task

1. Add `evals/search-agent-realism.json` (≥5 cases): e.g. Gordon Ramsay recipe, Jamie Oliver site, Python site:python.org.
2. Extend `app/evaluate.py` (or fixture schema) with optional `expectUrlPattern` / keyword checks on first N results.
3. Run locally once; commit `docs/evals/search-agent-realism.md` + JSON snapshot if harness supports it.

## Acceptance

- [ ] Fixture committed, documented in `docs/evals/WORKFLOW.md` one line
- [ ] Harness run command documented in issue close comment
- [ ] Tests for evaluator rules if new fields added

**Priority:** Tracer bullet
EOF
)"

create "Search: tune fusion variants (drop harmful latest prefix)" "$(cat <<'EOF'
## Problem

`build_search_variants` adds `latest {query}` which pollutes results (dictionary „latest”, news).

## Task

1. Adjust variants: omit `latest` unless query signals recency (regex: 2024|2025|2026|news|today|current).
2. Add unit test on variant list for chef vs news queries.

## Acceptance

- [ ] `tests/test_search_fusion.py` covers variant policy
- [ ] No regression on existing tests

**Priority:** Polish
EOF
)"

create "Research deep: reject off-topic evidence before answer" "$(cat <<'EOF'
## Problem

Live call „top 10 celebrity chefs” returned evidence from unrelated PL sites; answer correctly refused but wasted work. M1 research eval 0% success.

## Task

1. In `app/research.py`, score evidence URLs/titles/snippets against `query_tokens`; drop below threshold before synthesis.
2. Set `output.completeness` appropriately when too few sources remain.
3. Tests with fake evidence list (on-topic vs noise).

## Acceptance

- [ ] `tests/test_research.py` new cases
- [ ] `npm run test` green

**Priority:** Bug fix
EOF
)"

create "Research deep: resilient pipeline when SearxNG returns empty" "$(cat <<'EOF'
## Problem

M1 eval shows `ReadError` / empty search for many research cases when SearxNG fails mid-run.

## Task

1. Ensure research uses same fused search path as `/v1/search/web` (ddgs fallback).
2. Do not fail entire request on single variant error; surface partial evidence with `completeness: partial`.

## Acceptance

- [ ] Tests with mocked empty SearxNG + non-empty ddgs
- [ ] At least one research fixture passes in unit/integration test

**Priority:** Bug fix
EOF
)"

create "Scrape website: Playwright fallback for Wikipedia eval case" "$(cat <<'EOF'
## Problem

`evals/m1-baseline.json` website-04 (`en.wikipedia.org/wiki/HTTP`) → `urlOutcomes: blocked`, empty output. Blocks „full” local scrape story.

## Task

1. When httpx fetch is blocked/challenge, retry with existing Playwright path if `browser_fallback` enabled.
2. Test with mocked HTML or mark integration test `@pytest.mark.integration` hitting Wikipedia once.

## Acceptance

- [ ] `tests/test_scraper.py` or eval case documented
- [ ] website-04 passes when API+deps up OR explicit skip reason in eval report

**Priority:** Tracer bullet
EOF
)"

create "Scrape website: contract tests for urlOutcomes statuses" "$(cat <<'EOF'
## Problem

Clients must read `urlOutcomes` before trusting empty `output` (sitemap XML → `non_html`, wiki → `blocked`).

## Task

1. Add API tests in `tests/test_api.py` for: success page, blocked page (mock scraper), non-HTML URL.
2. Assert `list.listState` matches README contract.

## Acceptance

- [ ] Three cases with monkeypatched `scrape_website`
- [ ] `npm run test` green

**Priority:** Polish
EOF
)"

create "Eval: rerun M1 baseline and commit report if search/research improved" "$(cat <<'EOF'
## Task

1. `docker compose up --build -d`
2. `npm run eval -- --fixtures evals/m1-baseline.json --output docs/evals/latest.md --timeout 180`
3. If search.web or research.deep success rate improved vs `docs/evals/latest-after-fusion.md`, commit `docs/evals/latest.md` + adjacent JSON.

## Acceptance

- [ ] Issue comment with success rate table
- [ ] Committed eval artifacts only if materially better (avoid noise-only diffs)

**Priority:** Tracer bullet  
**Depends on:** search + research issues above
EOF
)"

create "Docs: search troubleshooting for self-hosted SearxNG" "$(cat <<'EOF'
## Task

Short section in README (≤15 lines): engines in `searxng/settings.yml`, ddgs fallback, when `collectionState` is empty vs complete, link `docs/evals/WORKFLOW.md`.

Do **not** bloat AGENTS.md.

## Acceptance

- [ ] README only, factual, matches code
- [ ] `npm run test` unchanged

**Priority:** Polish  
**Depends on:** search quality issues
EOF
)"

echo "Created Sandcastle backlog issues."
