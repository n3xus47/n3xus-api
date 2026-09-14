import asyncio
import re
from dataclasses import dataclass

import httpx

from app.config import settings
from app.models import SearchResult


class SearchError(Exception):
    pass


# Engines that tend to work on self-hosted SearxNG without paid keys (see searxng/settings.yml).
SEARXNG_ENGINE_CHAIN = ("bing", "startpage")

_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "for",
        "to",
        "of",
        "in",
        "on",
        "with",
        "what",
        "how",
        "why",
        "when",
        "who",
        "site",
        "latest",
        "top",
        "official",
        "explained",
        "documentation",
    }
)


@dataclass(frozen=True)
class SearchFusionOutcome:
    results: list[SearchResult]
    answer: str | None
    providers: tuple[str, ...]


async def _searxng_search(query: str, max_results: int) -> tuple[list[SearchResult], str | None]:
    async with httpx.AsyncClient(timeout=settings.request_timeout_secs) as client:
        response = await client.get(
            f"{settings.searxng_url.rstrip('/')}/search",
            params={
                "q": query,
                "format": "json",
                "categories": "general",
                "language": "en",
                "engines": ",".join(SEARXNG_ENGINE_CHAIN),
            },
        )
        response.raise_for_status()
        payload = response.json()

    results = [
        SearchResult(
            title=item.get("title") or item["url"],
            url=item["url"],
            snippet=item.get("content") or None,
            dateText=item.get("publishedDate") or None,
        )
        for item in payload.get("results", [])[:max_results]
        if item.get("url")
    ]
    answers = payload.get("answers") or []
    answer = answers[0] if answers else None
    return results, answer


async def _searxng_search_optional(query: str, max_results: int) -> tuple[list[SearchResult], str | None]:
    try:
        return await _searxng_search(query, max_results)
    except (httpx.HTTPError, ValueError, SearchError):
        return [], None


def _ddg_search_sync(query: str, max_results: int) -> list[SearchResult]:
    import time

    from ddgs import DDGS

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            rows = DDGS().text(query, max_results=max_results)
            results: list[SearchResult] = []
            for item in rows:
                url = item.get("href") or item.get("url")
                if not url:
                    continue
                results.append(
                    SearchResult(
                        title=item.get("title") or url,
                        url=url,
                        snippet=item.get("body") or item.get("snippet") or None,
                        dateText=None,
                    )
                )
            return results
        except Exception as error:
            last_error = error
            time.sleep(0.4 * (attempt + 1))
    if last_error:
        raise last_error
    return []


async def _ddg_search_optional(query: str, max_results: int) -> list[SearchResult]:
    if not settings.search_ddg_enabled:
        return []
    try:
        return await asyncio.to_thread(_ddg_search_sync, query, max_results)
    except Exception:
        return []


def query_tokens(query: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", query.lower())
        if len(token) > 2 and token not in _STOP_WORDS
    ]


def _token_surface_forms(token: str) -> tuple[str, ...]:
    if len(token) > 3 and token.endswith("s"):
        return (token, token[:-1])
    return (token,)


def _token_in_text(token: str, text: str) -> bool:
    return any(form in text for form in _token_surface_forms(token))


def relevance_score(query: str, result: SearchResult) -> float:
    tokens = query_tokens(query)
    if not tokens:
        return 0.0
    title = result.title.lower()
    snippet = (result.snippet or "").lower()
    url = result.url.lower()
    hay = f"{title} {snippet} {url}"
    score = 0.0
    for token in tokens:
        forms = _token_surface_forms(token)
        if not any(form in hay for form in forms):
            continue
        score += 1.0
        if any(form in title for form in forms):
            score += 2.0
        if any(form in url for form in forms):
            score += 1.5
        if any(form in snippet for form in forms):
            score += 0.5
    for index in range(len(tokens) - 1):
        phrase = f"{tokens[index]} {tokens[index + 1]}"
        if phrase in hay:
            score += 4.0
    matched = sum(1 for token in tokens if _token_in_text(token, hay))
    if len(tokens) >= 2 and matched < max(2, len(tokens) // 2):
        score *= 0.35
    return score


def rank_search_results(query: str, results: list[SearchResult]) -> list[SearchResult]:
    if not results:
        return []
    scored = sorted(((relevance_score(query, item), item) for item in results), reverse=True, key=lambda pair: pair[0])
    return [item for _, item in scored]


async def search_web(query: str, max_results: int) -> tuple[list[SearchResult], str | None]:
    outcome = await search_web_fused(query, max_results, variant_limit=1)
    return outcome.results, outcome.answer


def build_search_variants(query: str, *, limit: int = 5) -> list[str]:
    """Diverse query variants (DeepAPI-style multi-search) for better recall."""
    base = " ".join(query.split())
    if not base:
        return [query]
    variants: list[str] = []
    for candidate in (
        base,
        f"{base} official site",
        f"{base} documentation",
        f"latest {base}",
        f"{base} explained",
    ):
        if candidate not in variants:
            variants.append(candidate)
        if len(variants) >= limit:
            break
    return variants


def merge_search_results(batches: list[list[SearchResult]], max_results: int) -> list[SearchResult]:
    by_url: dict[str, SearchResult] = {}
    for batch in batches:
        for item in batch:
            existing = by_url.get(item.url)
            if existing is None:
                by_url[item.url] = item
                continue
            if len(item.snippet or "") > len(existing.snippet or ""):
                by_url[item.url] = item
    return list(by_url.values())[: max_results * 3]


async def search_web_fused(
    query: str,
    max_results: int,
    *,
    variant_limit: int | None = None,
) -> SearchFusionOutcome:
    """Run SearxNG variants and DuckDuckGo in parallel, merge, dedupe, and rank by relevance."""
    limit = variant_limit if variant_limit is not None else settings.search_variant_limit
    variants = build_search_variants(query, limit=limit)
    per_variant = max(max_results, 10)
    providers: list[str] = []

    searxng_tasks = [_searxng_search_optional(variant, per_variant) for variant in variants]
    ddg_task = _ddg_search_optional(query, max(max_results, 15))
    gathered = await asyncio.gather(*searxng_tasks, ddg_task, return_exceptions=True)
    searxng_outcomes = gathered[: len(searxng_tasks)]
    ddg_outcome = gathered[len(searxng_tasks)]

    batches: list[list[SearchResult]] = []
    answers: list[str] = []
    for item in searxng_outcomes:
        if isinstance(item, Exception):
            continue
        if not isinstance(item, tuple):
            continue
        results, answer = item
        if results:
            batches.append(results)
            providers.append("searxng")
        if answer and answer not in answers:
            answers.append(answer)

    if isinstance(ddg_outcome, list) and ddg_outcome:
        batches.append(ddg_outcome)
        providers.append("duckduckgo")

    merged = merge_search_results(batches, max_results)
    ranked = rank_search_results(query, merged)[:max_results]
    if ranked:
        unique_providers = tuple(dict.fromkeys(providers))
        return SearchFusionOutcome(ranked, answers[0] if answers else None, unique_providers)

    if settings.search_ddg_enabled:
        ddg_only = await _ddg_search_optional(query, max_results)
        if ddg_only:
            return SearchFusionOutcome(
                rank_search_results(query, ddg_only)[:max_results],
                None,
                ("duckduckgo",),
            )

    raise SearchError("Web search is unavailable (no results from configured providers)")
