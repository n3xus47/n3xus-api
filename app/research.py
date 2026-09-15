import asyncio
import json
from urllib.parse import urlparse

from app.llm import LlmError, generate
from app.models import Page, SearchResult, WebsiteScrapeRequest
from app.scraper import scrape_website
from app.search import build_search_variants, relevance_score, search_web_fused

MIN_RESEARCH_HIT_RELEVANCE = 3.0

MAX_EVIDENCE_PAGES = 8
MAX_RESULTS_PER_QUERY = 8
MAX_SEARCH_PLAN_QUERIES = 6
MAX_EVIDENCE_EXCERPT_CHARS = 2_500
RESEARCH_SCRAPE_MAX_CHARS = 40_000


async def plan_search_queries(query: str, context: str | None) -> list[str]:
    prompt = f"""Plan 2 to 4 diverse web searches to research a public question from different angles.
Return JSON only: {{"queries":["..."]}}. Each query must be concise and distinct.
Question: {query}
Context: {context or ""}"""
    try:
        payload = json.loads(await generate(prompt, json_mode=True))
        queries = payload.get("queries")
        if isinstance(queries, list):
            cleaned = [item.strip() for item in queries if isinstance(item, str) and item.strip()]
            if 2 <= len(cleaned) <= 4 and len(set(cleaned)) == len(cleaned):
                return cleaned
    except (json.JSONDecodeError, TypeError, LlmError):
        pass
    return []


def merge_search_plan(query: str, planned: list[str]) -> list[str]:
    """Universal open-web plan: anchor question + LLM angles + fusion variants."""
    anchor = query.strip()
    merged: list[str] = []
    for candidate in [anchor, *planned, *build_search_variants(anchor, limit=5)]:
        item = candidate.strip()
        if item and item not in merged:
            merged.append(item)
        if len(merged) >= MAX_SEARCH_PLAN_QUERIES:
            break
    return merged or [query]


def _registrable_domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _hit_relevance_score(query: str, hit: dict) -> float:
    result = SearchResult(
        title=hit.get("title") or hit["url"],
        url=hit["url"],
        snippet=hit.get("snippet"),
    )
    queries = [query, *(hit.get("searchQueries") or [])]
    return max(relevance_score(item, result) for item in queries)


def filter_relevant_hits(query: str, hits: list[dict], *, min_score: float = MIN_RESEARCH_HIT_RELEVANCE) -> list[dict]:
    return [hit for hit in hits if _hit_relevance_score(query, hit) >= min_score]


def merge_search_hits(planned_queries: list[str], batches: list[tuple[str, list[SearchResult]]]) -> list[dict]:
    by_url: dict[str, dict] = {}
    for search_query, results in batches:
        if search_query not in planned_queries:
            continue
        for result in results:
            item = by_url.setdefault(
                result.url,
                {"url": result.url, "title": result.title, "snippet": result.snippet, "searchQueries": []},
            )
            if search_query not in item["searchQueries"]:
                item["searchQueries"].append(search_query)
    return list(by_url.values())


def pick_source_urls(
    candidates: list[dict],
    limit: int = MAX_EVIDENCE_PAGES,
    query: str | None = None,
) -> list[str]:
    if not candidates:
        return []

    def rank_key(item: dict) -> tuple:
        relevance = _hit_relevance_score(query, item) if query else 0.0
        return (-relevance, -len(item["searchQueries"]), item["url"])

    ranked = sorted(candidates, key=rank_key)
    chosen: list[str] = []
    seen_domains: set[str] = set()
    for item in ranked:
        domain = _registrable_domain(item["url"])
        if domain in seen_domains and len(chosen) >= 2:
            continue
        chosen.append(item["url"])
        seen_domains.add(domain)
        if len(chosen) >= limit:
            return chosen
    for item in ranked:
        if item["url"] not in chosen:
            chosen.append(item["url"])
        if len(chosen) >= limit:
            break
    return chosen


def assess_completeness(
    *,
    planned_queries: int,
    queries_with_results: int,
    selected_urls: int,
    pages_with_content: int,
    distinct_domains: int,
) -> str:
    if pages_with_content == 0:
        return "empty"
    if queries_with_results < planned_queries or pages_with_content < selected_urls or distinct_domains < 2:
        return "partial"
    return "complete"


def _page_text(page: Page) -> str:
    return (page.markdown or page.text or "").strip()


def _page_has_content(page: Page) -> bool:
    return bool(_page_text(page))


def _collection_state(text: str, status: str) -> str:
    if text and status == "returned":
        return "complete"
    if text:
        return "partial"
    return "empty"


def build_evidence(
    selected_hits: list[dict],
    pages: list[Page],
    url_outcomes: list[dict[str, str]] | None,
) -> list[dict]:
    """Evidence from scraped pages; fall back to search snippets when scrape is empty or blocked."""
    pages_by_url = {page.url: page for page in pages}
    outcome_by_url = {item["url"]: item for item in (url_outcomes or [])}
    evidence: list[dict] = []
    for index, hit in enumerate(selected_hits, start=1):
        url = hit["url"]
        page = pages_by_url.get(url)
        text = _page_text(page) if page else ""
        outcome = outcome_by_url.get(url, {})
        status = outcome.get("status", "returned" if text else "not_returned")
        snippet = (hit.get("snippet") or "").strip()
        if text:
            excerpt = text[:MAX_EVIDENCE_EXCERPT_CHARS]
            collection_state = _collection_state(text, status)
        elif snippet:
            excerpt = snippet[:MAX_EVIDENCE_EXCERPT_CHARS]
            collection_state = "partial"
        else:
            excerpt = None
            collection_state = "empty"
        evidence.append(
            {
                "index": index,
                "url": url,
                "title": (page.title if page else None) or hit.get("title"),
                "searchQueries": hit.get("searchQueries", []),
                "excerpt": excerpt,
                "collectionState": collection_state,
            }
        )
    return evidence


async def _search_batch(search_query: str) -> tuple[str, list[SearchResult]]:
    try:
        fusion = await search_web_fused(search_query, MAX_RESULTS_PER_QUERY)
        return search_query, fusion.results
    except Exception:
        return search_query, []


async def research(
    query: str,
    context: str | None,
    *,
    instructions: str | None = None,
    mode: str = "raw",
) -> dict:
    llm_plan = await plan_search_queries(query, context)
    search_plan = merge_search_plan(query, llm_plan)

    batches = await asyncio.gather(*[_search_batch(item) for item in search_plan])
    queries_with_results = sum(1 for _, results in batches if results)

    hits = filter_relevant_hits(query, merge_search_hits(search_plan, list(batches)))
    selected_urls = pick_source_urls(hits, query=query)
    hit_by_url = {item["url"]: item for item in hits}
    selected_hits = [hit_by_url[url] for url in selected_urls if url in hit_by_url]

    pages: list[Page] = []
    outcomes: list[dict[str, str]] | None = None
    if selected_urls:
        pages, outcomes, _ = await scrape_website(
            WebsiteScrapeRequest(urls=selected_urls, contentFormat="markdown", maxChars=RESEARCH_SCRAPE_MAX_CHARS)
        )

    evidence = build_evidence(selected_hits, pages, outcomes)
    pages_with_content = sum(1 for item in evidence if item.get("collectionState") in {"complete", "partial"} and item.get("excerpt"))
    distinct_domains = len({_registrable_domain(item["url"]) for item in evidence if item.get("excerpt")})
    completeness = assess_completeness(
        planned_queries=len(search_plan),
        queries_with_results=queries_with_results,
        selected_urls=len(selected_urls),
        pages_with_content=pages_with_content,
        distinct_domains=distinct_domains,
    )

    numbered = "\n\n".join(
        f"[{item['index']}] {item['url']}\n{item.get('excerpt') or ''}" for item in evidence if item.get("excerpt")
    )
    if mode == "raw":
        answer = numbered or "No public evidence could be collected for this question with the current search configuration."
    else:
        synthesis_prompt = (
            "Answer the research question using only the numbered evidence below. "
            "Every factual claim must cite one or more evidence numbers like [1]. "
            "If the evidence is insufficient, say so explicitly and do not invent facts.\n"
            f"Question: {query}\nContext: {context or ''}\n"
            f"Instructions: {instructions or ''}\n\nEvidence:\n{numbered or '(no evidence collected)'}"
        )
        try:
            answer = await generate(synthesis_prompt)
        except LlmError:
            if not evidence:
                answer = "No public evidence could be collected for this question with the current search configuration."
            else:
                answer = (
                    "Local LLM is unavailable; summarized evidence only:\n\n"
                    + numbered
                    + "\n\nConfigure Ollama and pull the model named in N3XUS_API_OLLAMA_MODEL for a synthesized answer."
                )

    sources = [{"url": item["url"], "title": item.get("title")} for item in evidence]
    return {
        "answer": answer,
        "sources": sources,
        "searchPlan": search_plan,
        "evidence": evidence,
        "completeness": completeness,
        "mode": mode,
    }


def research_collection_state(completeness: str) -> str:
    if completeness == "complete":
        return "complete"
    if completeness == "empty":
        return "empty"
    return "partial"
